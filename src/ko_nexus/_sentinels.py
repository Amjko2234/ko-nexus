from __future__ import annotations

from typing import Final, NoReturn, Self, final, override

# =====================================================================================
#   Base Sentinel
# =====================================================================================


class SentinelType:
    """Base sentinel type. Inherit for component-specific sentinels."""

    def __init__(self, name: str) -> None:
        self._name: str = name

    def __bool__(self) -> NoReturn:
        raise TypeError("Sentinels cannot be used in boolean context")

    def __copy__(self) -> Self:
        return self

    @override
    def __eq__(self, other: object) -> bool:
        return self is other

    @override
    def __hash__(self) -> int:
        return id(self)

    def __or__(self, other: object) -> object:
        return other

    def __ror__(self, other: object) -> object:
        return other

    @override
    def __repr__(self) -> str:
        if self._name:
            return f"<{self._name}>"
        return f"<{self.__class__.__name__}>"

    @override
    def __str__(self) -> str:
        return repr(self)


# =====================================================================================
#   Public Sentinels
# =====================================================================================


@final
class UnsetType(SentinelType):
    """A sentinel type for unset values."""

    pass


UNSET: Final[UnsetType] = UnsetType(name="UNSET")
