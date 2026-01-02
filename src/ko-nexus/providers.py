import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Generic, Literal, TypeVar, overload, override

from ._types import AsyncCleanupType, AsyncFactoryType, CleanupType, FactoryType
from .exceptions import DiCallableError, DiDependencyError, DiUninitializedResourceError

T = TypeVar(name="T")


# =====================================================================================
#   Base providers
# =====================================================================================


class _AsyncProvider(ABC, Generic[T]):
    """Base async provider interface."""

    async def __call__(self) -> T:
        """Allow calling provider directly to resolve."""
        return await self.resolve()

    @abstractmethod
    async def resolve(self) -> T:
        """Resolve and return the provided value."""
        pass


class _Provider(ABC, Generic[T]):
    """Base provider interface."""

    def __call__(self) -> T:
        """Allow calling provider directly to resolve."""
        return self.resolve()

    @abstractmethod
    def resolve(self) -> T:
        """Resolve and return the provided value."""
        pass


# =====================================================================================
#   Main providers
# =====================================================================================


class Singleton(_Provider[T]):
    """
    Provider that lazily creates a single instance and reuses it (sync only).

    Usage:
    >>> def create_service() -> Service:
    >>>     return Service()
    >>>
    >>> service_singleton: Singleton[Service] = singleton(factory=create_service)
    >>>
    >>> svc1: Service = container.service_singleton()
    >>> svc2: Service = container.service_singleton()
    >>> assert svc1 is svc2
    >>> # PASSES

    Note:
        If the object itself is a singleton, then omit the implementation if it is only
        accessed by other systems through the dependency container. Although, it is not
        harmful, it is just more boilerplate.

    Raises:
        * `RuntimeError`: Internal unexpected bugs.
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], T]) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: FactoryType[T] = factory
        self._instance: T | None = None
        self._resolved: bool = False

    @override
    def __call__(self) -> T:
        return self.resolve()

    @override
    def resolve(self) -> T:
        if not self._resolved:
            self._instance = _sync_catch_run(
                func=self.factory, err_svc_name=self.__class__.__name__
            )
            self._resolved = True

        if self._instance is None:
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._instance}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + " is still `None` after instantiating the factory."
            )
        return self._instance


class AsyncSingleton(_AsyncProvider[T]):
    """
    Provider that lazily creates a single instance and reuses it (async only).

    Usage:
    >>> def create_async_service() -> AsyncService:
    >>>     return await AsyncService()
    >>>
    >>> async_svc_singleton: AsyncSingleton[AsyncService] = async_singleton(
    >>>     factory=create_async_service
    >>> )
    >>>
    >>> svc1: AsyncService = await container.async_svc_singleton()
    >>> svc2: AsyncService = await container.async_svc_singleton()
    >>> assert svc1 is svc2
    >>> # PASSES

    Note:
        If the object itself is a singleton, then omit the implementation if it is only
        accessed by other systems through the dependency container. Although, it is not
        harmful, it is just more boilerplate.

    Raises:
        * `RuntimeError`: Internal unexpected bugs.
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], Awaitable[T]]) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: AsyncFactoryType[T] = factory
        self._instance: T | None = None
        self._resolved: bool = False

    @override
    async def __call__(self) -> T:
        return await self.resolve()

    @override
    async def resolve(self) -> T:
        if not self._resolved:
            self._instance = await _async_catch_run(
                func=self.factory, err_svc_name=self.__class__.__name__
            )
            self._resolved = True

        if self._instance is None:
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._instance}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + " is still `None` after instantiating the factory."
            )
        return self._instance


class Factory(_Provider[T]):
    """
    Provider that lazily creates a new instance on each resolution (sync only).

    Usage:
    >>> def create_service() -> Service:
    >>>     return Serice()
    >>>
    >>> service_factory: Factory[Service] = factory(factory_func=create_service)
    >>>
    >>> svc1: Service = container.service_factory()
    >>> svc2: Service = container.service_factory()
    >>> assert svc1 is not svc2
    >>> # PASSES

    Note:
        The callable object itself SHOULD NOT be a singleton, as internally the
        `Factory` provider basically returns the called object.
        It does not handle the call.

    Raises:
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], T]) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: FactoryType[T] = factory

    @override
    def __call__(self) -> T:
        return self.resolve()

    @override
    def resolve(self) -> T:
        return _sync_catch_run(
            func=self.factory, get_return=True, err_svc_name=self.__class__.__name__
        )


class AsyncFactory(_AsyncProvider[T]):
    """
    Provider that lazily creates a new instance on each resolution (async only).

    Usage:
    >>> def create_async_service() -> AsyncService:
    >>>     return await AsyncService()
    >>>
    >>> async_svc_factory: AsyncFactory[AsyncService] = async_factory(
    >>>     factory_func=create_async_service
    >>> )
    >>>
    >>> svc1: AsyncService = await container.async_svc_factory()
    >>> svc2: AsyncService = await container.async_svc_factory()
    >>> assert svc1 is not svc2
    >>> # PASSES

    Note:
        The callable object itself SHOULD NOT be a singleton, as internally the
        `Factory` provider basically returns the called object.
        It does not handle the call.

    Raises:
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], Awaitable[T]]) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: AsyncFactoryType[T] = factory

    @override
    async def __call__(self) -> T:
        return await self.resolve()

    @override
    async def resolve(self) -> T:
        return await _async_catch_run(
            func=self.factory, get_return=True, err_svc_name=self.__class__.__name__
        )


class Resource(_Provider[T]):
    """
    Provider for resources that require initialization and cleanup.

    Singleton by default.
    Supports both sync and async initialization and cleanup functions.
    Resources are singletons with explicit lifecycle management.

    Raises:
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `RuntimeError`: Internal unexpected bugs.
        * `DiUninitializedResourceError`:
        Attempt to acquire value before initializing the `resource`.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(
        self,
        initializer: Callable[[], T] | Callable[[], Awaitable[T]],
        cleanup: Callable[[T], None] | Callable[[T], Awaitable[None]] | None = None,
        *,
        singleton: bool = True,
    ) -> None:
        if not hasattr(initializer, "__name__"):
            raise TypeError(
                f"`factory` must be a function, not type `{type(initializer)}`"
            )
        if initializer.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.init_func: FactoryType[T] | AsyncFactoryType[T] = initializer
        self.cleanup_func: CleanupType[T] | AsyncCleanupType[T] = cleanup
        self.resource: T | None = None
        self.async_resource: Awaitable[T] | None = None

        self._singleton: bool = singleton
        self._resolved: bool = False

    def is_resoved(self) -> bool:
        return self._resolved

    def get(self) -> T:
        if not self._resolved or self.resource is None:
            raise DiUninitializedResourceError(
                f"Resource `{self.resource.__class__.__name__}` is not initialized",
            )
        return self.resource

    @override
    def resolve(self) -> T:
        """
        Initialize and return the resource (sync only).

        Raises:
            * `RuntimeError`:
               Internal unexpected bugs or using sync-only method on async resources.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if inspect.iscoroutinefunction(self.init_func):
            raise RuntimeError(
                "Cannot use sync `resolve()` on an async `Resource`."
                + " Use `await Resource.async_resolve()` instead."
            )

        if self._singleton:
            if not self._resolved:
                self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
                    func=self.init_func,
                    get_return=True,
                    err_svc_name=self.__class__.__name__,
                )
                self._resolved = True
        else:
            self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
                func=self.init_func,
                get_return=True,
                err_svc_name=self.__class__.__name__,
            )

        if self.resource is None:
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self.resource.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + " is still `None` after instantiating the factory."
            )
        return self.resource

    async def async_resolve(self) -> T:
        """
        Initialize and return the resource (sync and async).

        Raises:
            * `RuntimeError`: Internal unexpected bugs.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if self._singleton:
            if not self._resolved:
                if inspect.iscoroutinefunction(self.init_func):
                    self.resource = await _async_catch_run(
                        func=self.init_func,
                        get_return=True,
                        err_svc_name=self.__class__.__name__,
                    )
                else:
                    self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
                        func=self.init_func,
                        get_return=True,
                        err_svc_name=self.__class__.__name__,
                    )
                self._resolved = True
        else:
            if inspect.iscoroutinefunction(self.init_func):
                self.resource = await _async_catch_run(
                    func=self.init_func,
                    get_return=True,
                    err_svc_name=self.__class__.__name__,
                )
            else:
                self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
                    func=self.init_func,
                    get_return=True,
                    err_svc_name=self.__class__.__name__,
                )

        if self.resource is None:
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self.resource.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + " is still `None` after instantiating the factory."
            )
        return self.resource

    def shutdown(self) -> None:
        """
        Shut down the resource (sync only).

        Raises:
            * `RuntimeError`: Using sync-only method on async resources.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """
        if inspect.iscoroutinefunction(self.cleanup_func):
            raise RuntimeError(
                "Cannot use sync `shutdown()` on an async `Resource`."
                + " Use `await Resource.async_shutdown()` instead."
            )

        if self._resolved and self.resource is not None:
            if self.cleanup_func is not None:
                _sync_catch_run(
                    func=lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                    err_svc_name=self.__class__.__name__,
                )
            self.resource = None
            self._resolved = False

    async def async_shutdown(self) -> None:
        """
        Shut down the resource (sync and async).

        Raises:
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if self._resolved and self.resource is not None:
            if self.cleanup_func is not None:
                if inspect.iscoroutinefunction(self.cleanup_func):
                    await _async_catch_run(
                        func=lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                        err_svc_name=self.__class__.__name__,
                    )
                else:
                    _sync_catch_run(
                        func=lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                        err_svc_name=self.__class__.__name__,
                    )
            self.resource = None
            self._resolved = False


class Dependency(_Provider[T]):
    """
    Provider placeholder for external dependencies that must be injected.

    Raises:
    * RuntimeError: Internal unexpected bugs.
    * DiDependencyError:
      Attempt to acquire value before initializing the dependencies.
    """

    def __init__(self, name: str | None = None) -> None:
        self._value: T | None = None
        self._provided: bool = False
        self.name: str | None = name

    @override
    def __call__(self) -> T:
        return self.resolve()

    def provide(self, value: T) -> None:
        """Inject the dependency value."""

        self._value = value
        self._provided = True

    def is_provided(self) -> bool:
        return self._provided

    @override
    def resolve(self) -> T:
        if not self._provided:
            raise DiDependencyError(
                f"Dependency `{self.name or 'unnamed'}` has not been provided",
            )

        if self._value is None:
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._value.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + " is still `None` after instantiating the factory."
            )
        return self._value


# =====================================================================================
#   Helper providers
# =====================================================================================


def singleton(factory: Callable[[], T]) -> Singleton[T]:
    """Create a `Singleton` provider."""
    return Singleton[T](factory)


def async_singleton(factory: Callable[[], Awaitable[T]]) -> AsyncSingleton[T]:
    """Create an `AsyncSingleton` provider."""
    return AsyncSingleton[T](factory)


def factory(factory_func: Callable[[], T]) -> Factory[T]:
    """Create a `Factory` provider."""
    return Factory[T](factory=factory_func)


def async_factory(factory_func: Callable[[], Awaitable[T]]) -> AsyncFactory[T]:
    """Create an `AsyncFactory` provider."""
    return AsyncFactory[T](factory=factory_func)


def resource(
    initializer: Callable[[], T] | Callable[[], Awaitable[T]],
    cleanup: Callable[[T], None] | Callable[[T], Awaitable[None]] | None = None,
    *,
    singleton: bool = True,
) -> Resource[T]:
    """Create a `Resource` provider."""
    return Resource[T](initializer, cleanup, singleton=singleton)


def dependency(name: str = "") -> Dependency[T]:
    """Create a `Dependency` placeholder."""
    return Dependency[T](name)


# =====================================================================================
#   Lazy referencing
# =====================================================================================


class LazyRef(Generic[T]):
    def __init__(self) -> None:
        self._value: T | None = None

    def set(self, v: T) -> T:
        self._value = v
        return self._value

    def get(self) -> T:
        """
        Raises:
        * RuntimeError: Failure to get value before it's initialized
        """
        if self._value is None:
            raise RuntimeError(
                f"Tried to access `{self._value}` when it's still undefined"
            )
        return self._value


# =====================================================================================
#   Private helper
# =====================================================================================


@overload
def _sync_catch_run(
    func: Callable[[], T],
    *,
    get_return: Literal[True],
    err_svc_name: str = ...,
) -> T: ...
@overload
def _sync_catch_run(
    func: Callable[[], T],
    *,
    get_return: Literal[False],
    err_svc_name: str = ...,
) -> None: ...
@overload
def _sync_catch_run(
    func: Callable[[], T],
    *,
    err_svc_name: str = ...,
) -> None: ...
def _sync_catch_run(
    func: Callable[[], T],
    *,
    get_return: bool = False,
    err_svc_name: str = "unknown",
) -> None | T:
    """
    Run the `Callable` and raise `DiCallableError` if the callable raises any errors.
    """
    try:
        if get_return:
            return func()
        else:
            _ = func()
            return None
    except Exception as exc:
        raise DiCallableError(
            f"An error occured whilst calling the factory `{func.__name__}`",
            service=err_svc_name,
        ) from exc


@overload
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    *,
    get_return: Literal[True],
    err_svc_name: str = ...,
) -> T: ...
@overload
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    *,
    get_return: Literal[False],
    err_svc_name: str = ...,
) -> None: ...
@overload
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    *,
    err_svc_name: str = ...,
) -> None: ...
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    *,
    get_return: bool = False,
    err_svc_name: str = "unknown",
) -> None | T:
    """
    Run the `Callable` and raise `DiCallableError` if the callable raises any errors.
    """
    try:
        if get_return:
            return await func()
        else:
            _ = await func()
            return None
    except Exception as exc:
        raise DiCallableError(
            f"An error occured whilst calling the factory `{func.__name__}`",
            service=err_svc_name,
        ) from exc
