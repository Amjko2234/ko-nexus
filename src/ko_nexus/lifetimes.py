import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, Literal, TypeAlias, TypeVar, cast, override

from .types import AsyncCleanupType, AsyncFactoryType, CleanupType, FactoryType

T = TypeVar(name="T")

Lifetime: TypeAlias = Literal[
    "singleton",
    "transient",
    "scoped",
]
"""Dependency lifetime strategies."""


@dataclass
class RegistrationMetadata:
    """Metadata for registered dependency."""

    lifetime: Lifetime
    factory: FactoryType[object] | AsyncFactoryType[object]
    cleanup: CleanupType[object] | AsyncCleanupType[object] | None = None
    instance: object | None = None
    is_async: bool = False
    resolved_params: dict[str, object] = field(default_factory=dict)


@dataclass
class NamedRegistrations:
    """Container for default and named registrations of an interface."""

    default: RegistrationMetadata | None = None
    named: dict[str, RegistrationMetadata] = field(default_factory=dict)

    def get(self, name: str | None = None, /) -> RegistrationMetadata | None:
        """Get registration by name, or default if name is `None`."""

        if name is None:
            return self.default
        return self.named.get(name)

    def has(self, name: str | None = None, /) -> bool:
        """Check if registration exists for a given name."""

        if name is None:
            return self.default is not None
        return name in self.named

    def set(
        self,
        metadata: RegistrationMetadata,
        name: str | None = None,
    ) -> None:
        """Set registration by name, or as default if name is `None`."""

        if name is None:
            self.default = metadata
        else:
            self.named[name] = metadata

    def all_metadata(self) -> list[RegistrationMetadata]:
        """Get all registered metadata (default + all named)."""

        result: list[RegistrationMetadata] = []
        if self.default is not None:
            result.append(self.default)
        result.extend(self.named.values())
        return result


# =====================================================================================
#   Strategies
# =====================================================================================


class LifetimeStrategy(ABC, Generic[T]):
    """Base strategy for dependency lifetime management."""

    @abstractmethod
    def resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T],
    ) -> T:
        """Resolve dependency according to lifetime strategy."""

        pass

    @abstractmethod
    async def async_resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T] | AsyncFactoryType[T],
    ) -> T:
        """Async resolve dependency according to lifetime strategy."""

        pass


class SingletonStrategy(LifetimeStrategy[T]):
    """Singleton lifetime allows one instance per container."""

    @override
    def resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T],
    ) -> T:
        if metadata.instance is None:
            metadata.instance = resolver()
        return cast(T, metadata.instance)

    @override
    async def async_resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T] | AsyncFactoryType[T],
    ) -> T:
        if metadata.instance is None:
            if inspect.iscoroutinefunction(resolver):
                metadata.instance = await resolver()
            else:
                metadata.instance = resolver()
        return cast(T, metadata.instance)


class TransientStrategy(LifetimeStrategy[T]):
    """Transient lfietime means new instance per resolve."""

    @override
    def resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T],
    ) -> T:
        return resolver()

    @override
    async def async_resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T] | AsyncFactoryType[T],
    ) -> T:
        if inspect.iscoroutinefunction(resolver):
            return cast(T, await resolver())
        return cast(T, resolver())


class ScopedStrategy(LifetimeStrategy[T]):
    """Scoped lfietime means one instance per scope."""

    def __init__(self) -> None:
        self._scoped_instances: dict[int, object] = {}

    @override
    def resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T],
    ) -> T:
        scope_id: int = id(metadata.resolved_params)
        if scope_id not in self._scoped_instances:
            self._scoped_instances[scope_id] = resolver()
        return cast(T, self._scoped_instances[scope_id])

    @override
    async def async_resolve(
        self,
        metadata: RegistrationMetadata,
        resolver: FactoryType[T] | AsyncFactoryType[T],
    ) -> T:
        scope_id: int = id(metadata.resolved_params)
        if scope_id not in self._scoped_instances:
            if inspect.iscoroutinefunction(resolver):
                self._scoped_instances[scope_id] = await resolver()
            else:
                self._scoped_instances[scope_id] = resolver()
        return cast(T, self._scoped_instances[scope_id])

    def clear_scope(self) -> None:
        """Clear all scoped instances."""

        self._scoped_instances.clear()
