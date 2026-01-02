from collections.abc import Awaitable, Callable
from typing import TypeAlias, TypeVar

T = TypeVar(name="T")

FactoryType: TypeAlias = Callable[[], T]
AsyncFactoryType: TypeAlias = Callable[[], Awaitable[T]]
CleanupType: TypeAlias = Callable[[T], None] | None
AsyncCleanupType: TypeAlias = Callable[[T], Awaitable[None]] | None
