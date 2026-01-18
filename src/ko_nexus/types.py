from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import TypeAlias, TypeVar

T = TypeVar(name="T")

FactoryType: TypeAlias = Callable[..., T]
AsyncFactoryType: TypeAlias = Callable[..., Awaitable[T]]
CleanupType: TypeAlias = Callable[[T], None]
AsyncCleanupType: TypeAlias = Callable[[T], Awaitable[None]]

StackKey: TypeAlias = tuple[type[object], str | None]

# ======================================================================================
#   Generic
# ======================================================================================

ExcType: TypeAlias = type[BaseException] | None
ExcValue: TypeAlias = BaseException | None
ExcTraceback: TypeAlias = TracebackType | None
ExcInfo: TypeAlias = tuple[ExcType, ExcValue, ExcTraceback]
