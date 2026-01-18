from __future__ import annotations

import importlib
import inspect
import pkgutil
from collections.abc import Callable
from inspect import Parameter, Signature
from types import ModuleType, UnionType
from typing import (
    Self,
    TypeVar,
    # Union is used only for runtime type checking
    Union,  # pyright: ignore[reportDeprecated]
    cast,
    get_args,
    get_origin,
    get_type_hints,
)

from .exceptions import (
    DiAutoRegistrationError,
    DiCallableError,
    DiCircularDependencyError,
    DiResolutionError,
    DiValidationError,
)
from .lifetimes import (
    Lifetime,
    LifetimeStrategy,
    NamedRegistrations,
    RegistrationMetadata,
    ScopedStrategy,
    SingletonStrategy,
    TransientStrategy,
)
from .types import (
    AsyncCleanupType,
    AsyncFactoryType,
    CleanupType,
    ExcTraceback,
    ExcType,
    ExcValue,
    FactoryType,
    StackKey,
)

T = TypeVar(name="T")


class Container:
    """
    Auto-wiring dependency injection container.
    Resolves dependencies based on type hints.
    Designed for centralized registration in composition root.
    """

    def __init__(self) -> None:
        self._registry: dict[type[object], NamedRegistrations] = {}
        self._strategies: dict[Lifetime, LifetimeStrategy[object]] = {
            "singleton": SingletonStrategy[object](),
            "transient": TransientStrategy[object](),
            "scoped": ScopedStrategy[object](),
        }
        self._resolution_stack: list[StackKey] = []

    # ----------------------------------------------------------------------------------
    #   Context manager
    # ----------------------------------------------------------------------------------

    def __enter__(self) -> Self:
        """
        Enter the context and automatically cleanup all resources (sync only)
        upon exit.
        """

        return self

    def __exit__(
        self, exc_type: ExcType, exc_val: ExcValue, exc_tb: ExcTraceback
    ) -> None:
        """Cleanup all resources (sync-only) on context exit."""

        self.shutdown_resources()

    async def __aenter__(self) -> Self:
        """
        Enter the context and automatically cleanup all resources (sync and async)
        upon exit.
        """

        return self

    async def __aexit__(
        self, exc_type: ExcType, exc_val: ExcValue, exc_tb: ExcTraceback
    ) -> None:
        """Cleanup all resources (async & sync) on context exit."""

        await self.async_shutdown_resources()

    # ----------------------------------------------------------------------------------
    #   Registering
    # ----------------------------------------------------------------------------------

    def register(
        self,
        interface: type[T],
        /,
        implementation: type[T] | FactoryType[T] | AsyncFactoryType[T] | None = None,
        name: str | None = None,
        cleanup: CleanupType[T] | AsyncCleanupType[T] | None = None,
        lifetime: Lifetime = "transient",
    ) -> None:
        """Register a type or factory with the container."""

        if implementation is None:
            implementation = interface

        is_async: bool = inspect.iscoroutinefunction(implementation)
        metadata: RegistrationMetadata = RegistrationMetadata(
            lifetime=lifetime,
            factory=implementation,
            cleanup=cleanup,  # pyright: ignore[reportArgumentType]
            is_async=is_async,
        )
        self._set_in_registry(interface, metadata, name)

    def register_instance(
        self,
        interface: type[T],
        /,
        instance: T,
        name: str | None = None,
    ) -> None:
        """Register a pre-existing instance (always a singleton)."""

        metadata: RegistrationMetadata = RegistrationMetadata(
            lifetime="singleton",
            factory=lambda: instance,
            instance=instance,
        )
        self._set_in_registry(interface, metadata, name)

    def register_factory(
        self,
        interface: type[T],
        /,
        factory: FactoryType[T] | AsyncFactoryType[T],
        name: str | None = None,
        lifetime: Lifetime = "transient",
    ) -> None:
        """Register a factory function for creating instances."""

        self.register(interface, implementation=factory, name=name, lifetime=lifetime)

    def auto_register_module(
        self,
        module_path: str,
        lifetime: Lifetime = "transient",
        predicate: Callable[[type[object]], bool] | None = None,
        exclude_abstract: bool = True,
    ) -> None:
        """
        Auto-register all classes from a module.

        Raises:
            * `DiAutoRegistrationError`: If module can not be imported
        """

        try:
            module: ModuleType = importlib.import_module(name=module_path)
        except ImportError as exc:
            raise DiAutoRegistrationError(
                f"Failed to import module from path `{module_path}`",
                service=self.__class__.__name__,
            ) from exc

        for name, object in inspect.getmembers(module, inspect.isclass):
            # Skip if not defined in this module
            if object.__module__ != module.__name__:
                continue
            # Skip private classes
            if name.startswith("_"):
                continue
            # Skip abstract classes
            if exclude_abstract and inspect.isabstract(object):
                continue
            # Apply predicate filter
            if (predicate is not None) and (not predicate(object)):
                continue

            self.register(object, implementation=object, lifetime=lifetime)

    def auto_register_package(
        self,
        package_path: str,
        lifetime: Lifetime = "transient",
        predicate: Callable[[type[object]], bool] | None = None,
        exclude_abstract: bool = True,
        recursive: bool = True,
    ) -> None:
        """
        Auto-register all classes from a package (multiple modules).

        Raises:
            * `DiAutoRegistrationError`: If package can not be imported
        """

        try:
            package: ModuleType = importlib.import_module(name=package_path)
        except ImportError as exc:
            raise DiAutoRegistrationError(
                f"Failed to import package from path `{package_path}`",
                service=self.__class__.__name__,
            ) from exc

        if not hasattr(package, "__path__"):
            raise DiAutoRegistrationError(
                f"Package path `{package_path}` is not a real package, as it has no `__path__`",
                service=self.__class__.__name__,
            )

        # Register classes from package's `__init__.py`
        self.auto_register_module(
            module_path=package_path,
            lifetime=lifetime,
            predicate=predicate,
            exclude_abstract=exclude_abstract,
        )

        for finder, name, is_package in pkgutil.walk_packages(
            path=package.__path__, prefix=package.__name__ + "."
        ):
            if not recursive and is_package:
                continue

            try:
                self.auto_register_module(
                    module_path=name,
                    lifetime=lifetime,
                    predicate=predicate,
                    exclude_abstract=exclude_abstract,
                )
            except DiAutoRegistrationError:
                # Skip modules that fail to be imported
                continue

    # ----------------------------------------------------------------------------------
    #   Resolving
    # ----------------------------------------------------------------------------------

    def resolve(self, interface: type[T], /, name: str | None = None) -> T:
        """
        Resolve a dependency by type (sync-only).

        Raises:
            * `DiResolutionError`: If type can not be resolved
            * `DiCircularDependencyError`: If circular dependency detected
        """

        if interface not in self._registry:
            raise DiResolutionError(
                f"Interface type `{interface.__name__}` is not registered",
                service=self.__class__.__name__,
            )

        if not self._registry[interface].has(name):
            name_str: str = f" with name `{name}`" if name else ""
            raise DiResolutionError(
                f"Interface type `{interface.__name__}`{name_str} is not registered",
                service=self.__class__.__name__,
            )

        stack_key: StackKey = (interface, name)
        if stack_key in self._resolution_stack:
            cycle: str = " -> ".join(
                f"{t.__name__}({n or 'default'})" for t, n in self._resolution_stack
            )
            raise DiCircularDependencyError(
                f"Circular dependency detected: `{cycle} ->"
                + f" {interface.__name__}({name or 'default'})`",
                service=self.__class__.__name__,
            )

        self._resolution_stack.append(stack_key)
        try:
            metadata: RegistrationMetadata = self._registry[interface]
            strategy: LifetimeStrategy[object] = self._strategies[metadata.lifetime]

            def resolver() -> object:
                return self._construct(metadata)

            result: object = strategy.resolve(metadata, resolver)
            return cast(T, result)
        finally:
            _ = self._resolution_stack.pop()

    async def async_resolve(self, interface: type[T], /, name: str | None = None) -> T:
        """
        Resolve a dependency by type (sync & async).

        Raises:
            * `DiResolutionError`: If type can not be resolved
            * `DiCircularDependencyError`: If circular dependency detected
        """

        if interface not in self._registry:
            raise DiResolutionError(
                f"Interface type `{interface.__name__}` is not registered",
                service=self.__class__.__name__,
            )

        if not self._registry[interface].has(name):
            name_str: str = f" with name `{name}`" if name else ""
            raise DiResolutionError(
                f"Interface type `{interface.__name__}`{name_str} is not registered",
                service=self.__class__.__name__,
            )

        stack_key: StackKey = (interface, name)
        if stack_key in self._resolution_stack:
            cycle: str = " -> ".join(
                f"{t.__name__}({n or 'default'})" for t, n in self._resolution_stack
            )
            raise DiCircularDependencyError(
                f"Circular dependency detected: `{cycle} ->"
                + f" {interface.__name__}({name or 'default'})`",
                service=self.__class__.__name__,
            )

        self._resolution_stack.append(stack_key)
        try:
            metadata: RegistrationMetadata = self._registry[interface]
            strategy: LifetimeStrategy[object] = self._strategies[metadata.lifetime]

            async def resolver() -> object:
                return await self._async_construct(metadata)

            result: object = await strategy.async_resolve(metadata, resolver)
            return cast(T, result)
        finally:
            _ = self._resolution_stack.pop()

    def _construct(self, metadata: RegistrationMetadata) -> object:
        """
        Auto-wire dependencies (sync-only).

        Raises:
            * `DiResolutionError`: If construction fails
        """

        factory: FactoryType[object] | AsyncFactoryType[object] = metadata.factory
        is_class: bool = inspect.isclass(object=factory)

        # Get type hints and signature
        if is_class:
            callable_for_hints: Callable[..., object] = factory.__init__
        else:
            callable_for_hints = factory

        try:
            type_hints: dict[str, type[object]] = get_type_hints(obj=callable_for_hints)
        except Exception:
            # Fallback for when `get_type_hints` somehow fails
            type_hints = getattr(callable_for_hints, "__annotations__", {})

        # Get signature for parameter iteration
        sig: Signature = inspect.signature(obj=callable_for_hints)

        # Just call the factory if there aren't any parameters
        params: list[Parameter] = [
            p for p in sig.parameters.values() if p.name != "self"
        ]
        if not params:
            return factory()

        # Arguments for the factory's parameters
        func_kwargs: dict[str, object] = {}

        # Otherwise, resolve dependencies from type hints
        for param in params:
            param_name: str = param.name

            # Skip if no annotation
            if param_name not in type_hints:
                if param.default is inspect.Parameter.empty:  # pyright: ignore[reportAny]
                    raise DiResolutionError(
                        f"Parameter `{param_name}` has no type hint and not defaults",
                        service=self.__class__.__name__,
                    )
                continue

            param_type: type[object] = type_hints[param_name]

            # ?OLD: Handle `Optional[Type]` or `(Union[Type, None )`
            # ?NEW: Handle `Type | None | ...`
            origin: object | None = get_origin(tp=param_type)
            if origin is Union:  # pyright: ignore[reportDeprecated]
                args: tuple[type[object], ...] = get_args(tp=param_type)

                if type(None) in args:
                    # Extract non-NoneTypes
                    non_none_types: list[type[object]] = [
                        t for t in args if t not in (type(None), None)
                    ]

                    if not non_none_types:
                        # Pure NoneTypes, use default or `None`
                        # func_kwargs[param_name] = self.resolve(non_none_types[0])
                        func_kwargs[param_name] = (
                            param.default  # pyright: ignore[reportAny]
                            if param.default is not Parameter.empty  # pyright: ignore[reportAny]
                            else None
                        )
                        continue

                    target_type: type[object] = non_none_types[0]

                    if target_type in self._registry:
                        resolved: object = self.resolve(target_type)
                        func_kwargs[param_name] = resolved
                    else:
                        # Not registered, so use the default or `None`
                        func_kwargs[param_name] = (
                            param.default  # pyright: ignore[reportAny]
                            if param.default is not Parameter.empty  # pyright: ignore[reportAny]
                            else None
                        )
                    continue

            # Resolve the non-NoneType dependencies
            if param_type in self._registry:
                func_kwargs[param_name] = self.resolve(param_type)
            elif param.default is not inspect.Parameter.empty:  # pyright: ignore[reportAny]
                func_kwargs[param_name] = param.default  # pyright: ignore[reportAny]
            else:
                raise DiResolutionError(
                    f"Cannot resolve parameter `{param_name}` of type `{param_type!s}`",
                    service=self.__class__.__name__,
                )

        return factory(**func_kwargs)

    async def _async_construct(self, metadata: RegistrationMetadata) -> object:
        """
        Auto-wire dependencies (sync & async).

        Raises:
            * `DiResolutionError`: If construction fails
        """

        factory: FactoryType[object] | AsyncFactoryType[object] = metadata.factory
        is_async: bool = inspect.iscoroutinefunction(obj=factory)
        is_class: bool = inspect.isclass(object=factory)

        # Get type hints and signature
        if is_class:
            callable_for_hints: Callable[..., object] = factory.__init__
        else:
            callable_for_hints = factory

        try:
            type_hints: dict[str, type[object]] = get_type_hints(obj=callable_for_hints)
        except Exception:
            # Fallback for when `get_type_hints` somehow fails
            type_hints = {}

        # Get signature for parameter iteration
        sig: Signature = inspect.signature(obj=callable_for_hints)

        # Just call the factory if there aren't any parameters
        params: list[Parameter] = [
            p for p in sig.parameters.values() if p.name != "self"
        ]
        if not params:
            if is_async:
                return await factory()  # pyright: ignore[reportAny]
            else:
                return factory()

        # Arguments for the factory's parameters
        func_kwargs: dict[str, object] = {}

        # Otherwise, resolve dependencies from type hints
        for param in params:
            param_name: str = param.name

            # Skip if no annotation
            if param_name not in type_hints:
                if param.default is inspect.Parameter.empty:  # pyright: ignore[reportAny]
                    raise DiResolutionError(
                        f"Parameter `{param_name}` has no type hint and not defaults",
                        service=self.__class__.__name__,
                    )
                continue

            param_type: type[object] = type_hints[param_name]

            # ?OLD: Handle `Optional[Type]` or `(Union[Type, None )`
            # ?NEW: Handle `Type | None | ...`
            origin: object | None = get_origin(tp=param_type)
            if isinstance(origin, UnionType):
                args: tuple[type[object], ...] = get_args(tp=param_type)

                if type(None) in args:
                    # If it's optional, then try to resolve non-NoneTypes
                    non_none_types: list[type[object]] = [
                        t for t in args if t not in (type(None), None)
                    ]
                    if non_none_types and non_none_types[0] in self._registry:
                        try:
                            func_kwargs[param_name] = await self.async_resolve(
                                non_none_types[0]
                            )
                        except DiResolutionError:
                            # If it can not resolve optional dependency, use `None`
                            func_kwargs[param_name] = None
                    else:
                        func_kwargs[param_name] = (
                            param.default  # pyright: ignore[reportAny]
                            if param.default is not Parameter.empty  # pyright: ignore[reportAny]
                            else None
                        )
                    continue

            # Resolve the non-NoneType dependencies
            if param_type in self._registry:
                func_kwargs[param_name] = await self.async_resolve(param_type)
            elif param.default is not inspect.Parameter.empty:  # pyright: ignore[reportAny]
                func_kwargs[param_name] = param.default  # pyright: ignore[reportAny]
            else:
                raise DiResolutionError(
                    f"Cannot resolve parameter `{param_name}` of type `{param_type!s}`",
                    service=self.__class__.__name__,
                )

        return factory(**func_kwargs)

    # ----------------------------------------------------------------------------------
    #   Lifecycle
    # ----------------------------------------------------------------------------------

    def shutdown_resources(self) -> None:
        """
        Shutdown all resources (sync-only) in reverse order of creation.

        Raises:
            * `DiCallableError`: If an exception occured from the cleanup callable
        """

        errors: list[str] = []
        for named_regs in reversed(list[NamedRegistrations](self._registry.values())):
            for metadata in reversed(
                list[RegistrationMetadata](named_regs.all_metadata())
            ):
                if (metadata.cleanup is not None) and (metadata.instance is not None):
                    if inspect.iscoroutinefunction(metadata.cleanup):
                        errors.append(
                            f"An awaitable resource cleanup for instance `{metadata.instance!s}`"
                            + " can not be called with `shutdown_resources`. Skipped it",
                        )
                        continue

                    try:
                        _ = metadata.cleanup(metadata.instance)
                    except Exception as exc:
                        errors.append(
                            "An exception occured when cleaning up resource for"
                            + f" instance `{metadata.instance!s}`: {exc}",
                        )

        if errors:
            err_msg: str = self._construct_shutdown_resource_err_msg(errors)
            raise DiCallableError(err_msg, service=self.__class__.__name__)

    async def async_shutdown_resources(self) -> None:
        """
        Shutdown all resources (sync & async) in reverse order of creation.

        Raises:
            * `DiCallableError`: If an exception occured from the cleanup callable
        """

        errors: list[str] = []
        for named_regs in reversed(list[NamedRegistrations](self._registry.values())):
            for metadata in reversed(
                list[RegistrationMetadata](named_regs.all_metadata())
            ):
                if (metadata.cleanup is not None) and (metadata.instance is not None):
                    try:
                        if inspect.iscoroutinefunction(metadata.cleanup):
                            _ = await metadata.cleanup(metadata.instance)  # pyright: ignore[reportAny]
                        else:
                            _ = metadata.cleanup(metadata.instance)
                    except Exception as exc:
                        errors.append(
                            "An exception occured when cleaning up resource for"
                            + f" instance `{metadata.instance!s}`: {exc}",
                        )

        if errors:
            err_msg: str = self._construct_shutdown_resource_err_msg(errors)
            raise DiCallableError(err_msg, service=self.__class__.__name__)

    def _construct_shutdown_resource_err_msg(self, errors: list[str], /) -> str:
        _errs: str = "Errors" if len(errors) > 1 else "Error"
        err_msg: str = f"{_errs} raised while shutting down resources:"
        for index, err in enumerate[str](errors):
            err_msg += f"\n    Error {index}: {err}"

        return err_msg

    # ----------------------------------------------------------------------------------
    #   Validation
    # ----------------------------------------------------------------------------------

    def validate(self) -> None:
        """
        Validate all registrations can be resolved.
        Useful to run at startup to catch configuration errors early.

        Raises:
            * `DiValidationError`: If any registration is invalid.
        """

        errors: list[str] = []
        for interface, named_regs in self._registry.items():
            if named_regs.default is not None:
                try:
                    self._validate_type(interface, name=None, visited=set[StackKey]())
                except (DiResolutionError, DiCircularDependencyError) as exc:
                    errors.append(f"Interface `{interface.__name__}`: {exc}")

        if errors:
            _errs: str = "Errors" if len(errors) > 1 else "Error"
            err_msg: str = f"{_errs} raised during container validation:\n"
            for index, err in enumerate[str](errors):
                err_msg += f"\n    Error {index}: {err}"

            raise DiValidationError(err_msg, service=self.__class__.__name__)

    def _validate_type(
        self,
        interface: type[object],
        name: str | None,
        visited: set[tuple[type[object], str | None]],
    ) -> None:
        """
        Validate a type can be resolved without actually constructing it.

        Raises:
            * `DiCircularDependencyError`: If circular dependency is detected
            * `DiResolutionError`: If type can not be resolved
        """
        stack_key: StackKey = (interface, name)

        if stack_key in visited:
            cycle: str = " -> ".join(
                f"{t.__name__}({n or 'default'})" for t, n in self._resolution_stack
            )
            raise DiCircularDependencyError(
                f"Circular dependency detected: `{cycle} ->"
                + f" {interface.__name__}({name or 'default'})`",
                service=self.__class__.__name__,
            )

        if interface not in self._registry:
            raise DiResolutionError(
                f"Interface type `{interface.__name__}` is not registered",
                service=self.__class__.__name__,
            )

        if not self._registry[interface].has(name):
            name_str: str = f" with name `{name}`" if name else ""
            raise DiResolutionError(
                f"Interface type `{interface.__name__}`{name_str} is not registered",
                service=self.__class__.__name__,
            )

        visited.add(stack_key)

        metadata: RegistrationMetadata = self._registry[interface].get(name)  # pyright: ignore[reportAssignmentType]
        factory: FactoryType[object] | AsyncFactoryType[object] = metadata.factory
        is_class: bool = inspect.isclass(object=factory)

        # Get type hitns and signature
        if is_class:
            callable_for_hints: Callable[..., object] = factory.__init__
        else:
            callable_for_hints = factory

        try:
            type_hints: dict[str, type[object]] = get_type_hints(obj=callable_for_hints)
        except Exception:
            # Fallback for when `get_type_hints` somehow fails
            type_hints = {}

        # Get signature for parameter iteration
        sig: Signature = inspect.signature(obj=callable_for_hints)

        # Just call the factory if there aren't any parameters
        params: list[Parameter] = [
            p for p in sig.parameters.values() if p.name != "self"
        ]
        for param in params:
            param_name: str = param.name

            # Skip if no annotation
            if param_name not in type_hints:
                if param.default is inspect.Parameter.empty:  # pyright: ignore[reportAny]
                    raise DiResolutionError(
                        f"Parameter `{param_name}` has no type hint and not defaults",
                        service=self.__class__.__name__,
                    )
                continue

            param_type: type[object] = type_hints[param_name]

            # Handle optional types
            origin: object | None = get_origin(tp=param_type)
            if isinstance(origin, UnionType):
                args: tuple[type[object], ...] = get_args(tp=param_type)

                if type(None) in args:
                    # If it's optional, then try to resolve non-NoneTypes
                    non_none_types: list[type[object]] = [
                        t for t in args if t not in (type(None), None)
                    ]
                    if non_none_types:
                        param_type = non_none_types[0]
                    else:
                        continue

            # Recursively validate dependencies
            if param_type in self._registry:
                self._validate_type(
                    interface=param_type, name=None, visited=visited.copy()
                )
            elif param.default is inspect.Parameter.empty:  # pyright: ignore[reportAny]
                raise DiResolutionError(
                    f"Cannot resolve parameter `{param_name}` of type"
                    + f" `{param_type.__name__}` for interface of type `{interface.__name__}`",
                    service=self.__class__.__name__,
                )

        visited.remove(stack_key)

    # ----------------------------------------------------------------------------------
    #   Public helper
    # ----------------------------------------------------------------------------------

    def clear_scoped(self) -> None:
        """Clear all scoped instances."""

        strategy: LifetimeStrategy[object] = self._strategies["scoped"]
        if isinstance(strategy, ScopedStrategy):
            strategy.clear_scope()

    # ----------------------------------------------------------------------------------
    #   Private helper
    # ----------------------------------------------------------------------------------

    def _set_in_registry(
        self, interface: type[T], metadata: RegistrationMetadata, name: str | None
    ) -> None:
        if interface not in self._registry:
            self._registry[interface] = NamedRegistrations()
        self._registry[interface].set(metadata, name)
