import inspect
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Generic, Literal, TypeVar, overload, override

from ._sentinels import UNSET as _UNSET
from ._sentinels import UnsetType as _UnsetT
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
    PASSES

    Note:
        If the object itself is a singleton, then omit the implementation if it is only
        accessed by other systems through the dependency container. Although, it is not
        harmful, it is just more boilerplate.

    Raises:
        * `RuntimeError`: Internal unexpected bugs.
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], T], /) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: FactoryType[T] = factory
        self._instance: T | _UnsetT = _UNSET
        self._resolved: bool = False

    @override
    def resolve(self) -> T:
        if not self._resolved:
            self._instance = _sync_catch_run(
                self.factory, get_return=True, err_svc_name=self.__class__.__name__
            )
            self._resolved = True

        if isinstance(self._instance, _UnsetT):
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._instance}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + f" is still `{self._instance}` after instantiating the factory."
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
    PASSES

    Note:
        If the object itself is a singleton, then omit the implementation if it is only
        accessed by other systems through the dependency container. Although, it is not
        harmful, it is just more boilerplate.

    Raises:
        * `RuntimeError`: Internal unexpected bugs.
        * `TypeError`: Factory does not have `__name__`.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], Awaitable[T]], /) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")

        self.factory: AsyncFactoryType[T] = factory
        self._instance: T | _UnsetT = _UNSET
        self._resolved: bool = False

    @override
    async def resolve(self) -> T:
        if not self._resolved:
            self._instance = await _async_catch_run(
                self.factory, get_return=True, err_svc_name=self.__class__.__name__
            )
            self._resolved = True

        if isinstance(self._instance, _UnsetT):
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._instance}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + f" is still `{self._instance}` after instantiating the factory."
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
    PASSES

    Note:
        The callable object itself SHOULD NOT be a singleton, as internally the
        `Factory` provider basically returns the called object.
        It does not handle the call.

    Raises:
        * `TypeError`: Factory does not have `__name__` or is a lambda function.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], T], /) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")
        if factory.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.factory: FactoryType[T] = factory

    @override
    def resolve(self) -> T:
        return _sync_catch_run(
            self.factory, get_return=True, err_svc_name=self.__class__.__name__
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
    PASSES

    Note:
        The callable object itself SHOULD NOT be a singleton, as internally the
        `Factory` provider basically returns the called object.
        It does not handle the call.

    Raises:
        * `TypeError`: Factory does not have `__name__`.
        * `DiCallableError`: An unexpected error occured when calling the factory.
    """

    def __init__(self, factory: Callable[[], Awaitable[T]], /) -> None:
        if not hasattr(factory, "__name__"):
            raise TypeError(f"`factory` must be a function, not type `{type(factory)}`")

        self.factory: AsyncFactoryType[T] = factory

    @override
    async def resolve(self) -> T:
        return await _async_catch_run(
            self.factory, get_return=True, err_svc_name=self.__class__.__name__
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
        # Ensure initializer callable is not a lambda
        if not hasattr(initializer, "__name__"):
            raise TypeError(
                f"`factory` must be a function, not type `{type(initializer)}`"
            )
        if initializer.__name__ == "<lambda>":
            raise TypeError("`Lambda` is not supported. Please use a named function")

        self.init_func: FactoryType[T] | AsyncFactoryType[T] = initializer

        # Ensure cleanup callable is not a lambda
        if cleanup is not None:
            if not hasattr(cleanup, "__name__"):
                raise TypeError(
                    f"`factory` must be a function, not type `{type(cleanup)}`"
                )
            if cleanup.__name__ == "<lambda>":
                raise TypeError(
                    "`Lambda` is not supported. Please use a named function"
                )

        self.cleanup_func: CleanupType[T] | AsyncCleanupType[T] = cleanup

        self.resource: T | _UnsetT = _UNSET
        self.async_resource: Awaitable[T] | None = None

        self._singleton: bool = singleton
        self._resolved: bool = False

    def is_resolved(self) -> bool:
        return self._resolved

    def get(self) -> T:
        if (self._singleton and self._resolved) and not isinstance(
            self.resource, _UnsetT
        ):
            return self.resource
        elif not isinstance(self.resource, _UnsetT):
            return self.resource
        else:
            raise DiUninitializedResourceError(
                f"Resource `{self.resource.__class__.__name__}` is not initialized",
            )

    @override
    def resolve(self) -> T:
        """
        Initialize and return the resource (sync only).

        Raises:
            * `TypeError`: Using sync methods on an async factory.
            * `RuntimeError`:
               Internal unexpected bugs or using sync-only method on async resources.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if self._singleton and not isinstance(self.resource, _UnsetT):
            return self.resource

        if inspect.iscoroutinefunction(self.init_func):
            raise TypeError(
                "Cannot call sync `resolve()` on an async `Resource`."
                + " Use `await Resource.async_resolve()` instead."
            )

        self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
            self.init_func,
            get_return=True,
            err_svc_name=self.__class__.__name__,
        )

        if self._singleton and not self._resolved:
            self._resolved = True

        if isinstance(self.resource, _UnsetT):
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self.resource.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + f" is still `{self.resource}` after instantiating the factory."
            )
        return self.resource

    async def async_resolve(self) -> T:
        """
        Initialize and return the resource (sync and async).

        Raises:
            * `RuntimeError`: Internal unexpected bugs.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if self._singleton and not isinstance(self.resource, _UnsetT):
            return self.resource

        if inspect.iscoroutinefunction(self.init_func):
            self.resource = await _async_catch_run(
                self.init_func,
                get_return=True,
                err_svc_name=self.__class__.__name__,
            )
        else:
            self.resource = _sync_catch_run(  # pyright: ignore[reportAttributeAccessIssue]
                self.init_func,
                get_return=True,
                err_svc_name=self.__class__.__name__,
            )

        if self._singleton and not self._resolved:
            self._resolved = True

        if isinstance(self.resource, _UnsetT):
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self.resource.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + f" is still `{self.resource}` after instantiating the factory."
            )
        return self.resource

    def shutdown(self) -> None:
        """
        Shut down the resource (sync only).

        Raises:
            * `TypeError`: Attempt to call an async `Resource` in a synchronous context.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if inspect.iscoroutinefunction(self.cleanup_func):
            raise TypeError(
                "Cannot call sync `shutdown()` on an async `Resource`."
                + " Use `await Resource.async_shutdown()` instead."
            )

        if (self.cleanup_func is not None) and not isinstance(self.resource, _UnsetT):
            _sync_catch_run(
                lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                get_return=False,
                err_svc_name=self.__class__.__name__,
            )

        if self._singleton and self._resolved:
            self._resolved = False
        self.resource = _UNSET

    async def async_shutdown(self) -> None:
        """
        Shut down the resource (sync and async).

        Raises:
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        if (self.cleanup_func is not None) and not isinstance(self.resource, _UnsetT):
            if inspect.iscoroutinefunction(self.cleanup_func):
                # Basedpyright somehow still thinks that `cleanup_func()` is either
                # sync or async callable
                await _async_catch_run(  # pyright: ignore[reportCallIssue]
                    lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                    get_return=False,
                    err_svc_name=self.__class__.__name__,
                )
            else:
                _sync_catch_run(
                    lambda: self.cleanup_func(self.resource),  # pyright: ignore[reportOptionalCall, reportArgumentType]
                    get_return=False,
                    err_svc_name=self.__class__.__name__,
                )

        if self._singleton and self._resolved:
            self._resolved = False
        self.resource = _UNSET


class Dependency(_Provider[T]):
    """
    Provider placeholder for external dependencies that must be injected.
    No usage example is provided, as dependencies are injected by the `Container`.
    """

    def __init__(self, name: str | None = None) -> None:
        self._value: T | _UnsetT = _UNSET
        self._provided: bool = False
        self.name: str | None = name

    def provide(self, value: T) -> None:
        """Inject the dependency value."""

        self._value = value
        self._provided = True

    def is_provided(self) -> bool:
        return self._provided

    @override
    def resolve(self) -> T:
        """
        Returns injected value by it's parent container.

        Raises:
            * `RuntimeError`: Internal unexpected bugs.
            * `DiDependencyError`:
            Attempt to acquire value before initializing the dependencies.
        """

        if not self._provided:
            raise DiDependencyError(
                f"Dependency `{self.name or 'unnamed'}` has not been provided",
            )

        if isinstance(self._value, _UnsetT):
            raise RuntimeError(
                f"For unknown reasons, internal instance `{self._value.__class__.__name__}`"
                + f" of dependency container `{self.__class__.__name__}`"
                + f" is still `{self._value}` after instantiating the factory."
            )
        return self._value


# =====================================================================================
#   Helper providers
# =====================================================================================


def singleton(factory: Callable[[], T], /) -> Singleton[T]:
    """Create a `Singleton` provider."""

    return Singleton[T](factory)


def async_singleton(factory: Callable[[], Awaitable[T]], /) -> AsyncSingleton[T]:
    """Create an `AsyncSingleton` provider."""

    return AsyncSingleton[T](factory)


def factory(factory_func: Callable[[], T], /) -> Factory[T]:
    """Create a `Factory` provider."""

    return Factory[T](factory_func)


def async_factory(factory_func: Callable[[], Awaitable[T]], /) -> AsyncFactory[T]:
    """Create an `AsyncFactory` provider."""

    return AsyncFactory[T](factory_func)


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
    """
    Allow lazy references of objects to delay the resolution of the object.

    Intended to be used in cases that require the object to be defined inside the scope
    of a class or a class instance without yet instantiating the object. Reasons may
    vary as to why the object must be instantiated later, but most common whilst
    testing is wanting the object's resources to be initialized later--not as soon
    as the class's `__init__` run.

    Example Usage:
    >>> class Service:
    >>>     def __init__(self) -> None:
    >>>         self.container = ServiceContainer()
    >>>         self.log_container = self.container.logger
    >>>         # or `self.container.logger()` depending on how you configured it
    >>>
    >>>         # Define later the actual logger to avoid initializing its resources
    >>>         # on the spot
    >>>         self.log = LazyRef[Logger]()
    >>>
    >>>     def start(self) -> None:
    >>>         # Start lifecycle of logging system because the `logger` container
    >>>         # is responsible for its resources
    >>>         self.logger.init_resources()
    >>>         # Set boot logger
    >>>         self.log.set(v=self.logger.boot())
    >>>
    >>>     def do_something(self) -> None:
    >>>         log: Logger = self.log.get()
    >>>         log.info("Did something")
    [YYYY:MM:DD HH:MM:SS] [INFO    ] [19  @BOOT::do_something] Did something
    """

    def __init__(self) -> None:
        self._value: T | _UnsetT = _UNSET

    def set(self, v: T, /) -> T:
        """Set the value."""

        self._value = v
        return self._value

    def get(self) -> T:
        """
        Get the value.

        Raises:
        * RuntimeError: Failure to get value before it's initialized
        """

        if isinstance(self._value, _UnsetT):
            raise RuntimeError(
                f"Tried to access `{self._value}` when it's still `{self._value}`"
            )
        return self._value


# =====================================================================================
#   Private helpers
# =====================================================================================


@overload
def _sync_catch_run(
    func: Callable[[], T],
    /,
    get_return: Literal[True],
    err_svc_name: str = ...,
) -> T: ...
@overload
def _sync_catch_run(
    func: Callable[[], T],
    /,
    get_return: Literal[False],
    err_svc_name: str = ...,
) -> None: ...
def _sync_catch_run(
    func: Callable[[], T],
    /,
    get_return: bool,
    err_svc_name: str = "unknown",
) -> None | T:
    """Run the callable and translate any errors from it to `DiCallableError`."""

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
    /,
    get_return: Literal[True],
    err_svc_name: str = ...,
) -> T: ...
@overload
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    /,
    get_return: Literal[False],
    err_svc_name: str = ...,
) -> None: ...
async def _async_catch_run(
    func: Callable[[], Awaitable[T]],
    /,
    get_return: bool,
    err_svc_name: str = "unknown",
) -> None | T:
    """Run the callable and translate any errors from it to `DiCallableError`."""

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
