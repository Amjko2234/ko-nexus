import json
from datetime import datetime, timezone
from typing import Literal, TypeAlias, override

# ======================================================================================
#   Models
# ======================================================================================

# fmt: off
Layer: TypeAlias = Literal[ # Literals based from: "Where did it happen?"
    # Container layer
    "CONTAINER",

    # Provider layer
    "CALLABLE",     # Any callable that is a dependency
    "DEPENDENCY",   # Missing/unspecified, required dependencies
    "RESOURCE",     # Improper lifecycle management of resources

    # Generic
    "UNKNOWN",
]
"""System layers for error categorization."""

Category: TypeAlias = Literal[ # Literals based from: "What type of problem?"
    # Resource & Data
    "MISSING",      # Expected data is missing

    # Usage
    "USAGE",        # Improper method usage

    # Generic
    "UNEXPECTED",   # Unexpected errors
    "UNKNOWN",          
]
"""Error categories for error classification."""

Severity: TypeAlias = Literal["WARNING", "ERROR", "CRITICAL"]
"""Error severity levels."""
# fmt: on


# ======================================================================================
#   Base
# ======================================================================================


class _BaseException(BaseException):
    msg: str
    default_layer: Layer = "UNKNOWN"
    default_service: str = "UNKNOWN"
    default_category: Category = "UNKNOWN"
    default_severity: Severity = "ERROR"
    recoverable: bool | None = None

    def __init__(
        self,
        message: str,
        /,
        user_message: str | None = None,
        description: str | None = None,
        document_url: str | None = None,
        cause: BaseException | None = None,
        *,
        context: dict[str, object] | None = None,
        service: str | None = None,
        layer: Layer | None = None,
        category: Category | None = None,
        severity: Severity | None = None,
        recoverable: bool | None = None,
    ) -> None:
        self.msg = message.strip()
        self.user_msg: str = user_message.strip() if user_message else ""

        layer_: Layer = layer or self.default_layer
        service_: str = service.strip().upper() if service else self.default_service
        category_: Category = category or self.default_category
        severity_: Severity = severity or self.default_severity
        self.code: str = self._generate_code(
            layer=layer_,
            service=service_,
            category=category_,
            severity=severity_,
        )
        self.msg_code: str = f"{self.msg} >> {self.code}"

        # Recoverability (value upon call has overwriting priority)
        if isinstance(recoverable, bool):
            self.recoverable = recoverable
        elif self.recoverable is None:
            self.recoverable = False

        # Context
        self.__cause__: BaseException | None = cause
        self._ctx: dict[str, object] | None = context
        self._tstamp: datetime = datetime.now(tz=timezone.utc)

        super().__init__(self.msg_code)

    @override
    def __str__(self) -> str:
        return f"{self.msg_code}"

    @override
    def __repr__(self) -> str:
        json_context: str = json.dumps(obj=self._ctx, indent=2, default=str)
        return f"{self.msg_code}:\n{json_context}"

    def _generate_code(
        self,
        layer: str,
        service: str,
        category: str,
        severity: str,
    ) -> str:
        code: str = f"{layer}::{service}::{category}::{severity}"
        if self.recoverable:
            return f"{code}::RECOVERABLE"
        else:
            return code


# ======================================================================================
#   Models
# ======================================================================================


class DiCallableError(_BaseException):
    default_layer: Layer = "CALLABLE"
    default_category: Category = "UNEXPECTED"
    default_severity: Severity = "ERROR"
    recoverable: bool | None = False


class DiContainerError(_BaseException):
    default_layer: Layer = "CONTAINER"
    default_category: Category = "USAGE"
    default_severity: Severity = "CRITICAL"
    recoverable: bool | None = False


class DiDependencyError(_BaseException):
    default_layer: Layer = "DEPENDENCY"
    default_category: Category = "MISSING"
    default_severity: Severity = "CRITICAL"
    recoverable: bool | None = False


class DiUninitializedResourceError(_BaseException):
    default_layer: Layer = "RESOURCE"
    default_category: Category = "USAGE"
    default_severity: Severity = "ERROR"
    recoverable: bool | None = False
