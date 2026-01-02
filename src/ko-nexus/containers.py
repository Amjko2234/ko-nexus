import inspect
from typing import override

from .exceptions import DiDependencyError
from .providers import Dependency, Resource


class Container:
    """Base class for dependency injection."""

    __name__: str = "Container"

    @override
    def __str__(self) -> str:
        return self.__repr__()

    @override
    def __repr__(self) -> str:
        return f"{self.__name__}"

    def __init__(self, **dependencies: object) -> None:
        """
        Initialize container and inject dependencies.

        Raises:
        * DiContainerError: The container failed to initialize
        * DiDependencyError:
          Required dependencies are missing (unpassed) or are not declared dependencies.
        """

        # Collect dependencies from instance
        instance_dependencies: dict[str, Dependency[object]] = {}
        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Dependency):
                instance_dependencies[name] = attr

        # Inject provided dependency values
        for name, value in dependencies.items():
            if name not in instance_dependencies:
                raise DiDependencyError(
                    f"Name `{name}` is not a declared dependency"
                    + f" {self.__class__.__name__}"
                )
            instance_dependencies[name].provide(value)

        # Validate all dependencies that are provided
        missing: list[str] = [
            name for name, dep in instance_dependencies.items() if not dep.is_provided()
        ]
        if missing:
            raise DiDependencyError(
                f"Container `{self.__class__.__name__}` has missing"
                + f" dependencies: {', '.join(missing)}"
            )

    def init_resources(self) -> None:
        """
        Initialize all sync `Resource` providers in this container.
        This forces lazy resources to immediately initialize.

        It calls `resolve()` of all `Resource` providers.

        Raises:
        * RuntimeError: Attempt to call an async `Resource` in a synchronous context.
        * *Exceptions:
          Propagates any exception raised from the callback to initialize resource.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                if inspect.iscoroutinefunction(attr.resolve):
                    raise RuntimeError(
                        f"Cannot use sync `init_resources()` when resource `{name}` "
                        + " has an async initializer function."
                        + " Use `await Container.async_init_resources()` instead."
                    )
                attr.resolve()  # Trigger intialization

    async def async_init_resources(self) -> None:
        """
        Initialize all async/sync `Resource` providers in this container.
        This forces lazy resources to immediately initialize.

        It calls `async_resolve()` of all `Resource` providers.

        Raises:
        * *Exceptions:
          Propagates any exception raised from the callback to initialize resource.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                await attr.async_resolve()  # Trigger intialization

    def shutdown_resources(self) -> None:
        """
        Shutdown all sync `Resource` providers in this container.

        Calls the cleanup function for each initialized resource.
        Should be called when the container is no longer needed.

        Raises:
        * RuntimeError: Attempt to call an async `Resource` in a synchronous context.
        * *Exceptions:
          Propagates any exception raised from the callback to shutdown resource.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                if inspect.iscoroutinefunction(attr.shutdown):
                    raise RuntimeError(
                        f"Cannot use sync `shutdown_resources()` when resource `{name}` "
                        + " has an async cleanup function."
                        + " Use `await Container.async_shutdown_resources()` instead."
                    )
                attr.shutdown()

    async def async_shutdown_resources(self) -> None:
        """
        Shutdown all async/sync `Resource` providers in this container.

        Calls the cleanup function for each initialized resource.
        Should be called when the container is no longer needed.

        * *Exceptions:
          Propagates any exception raised from the callback to shutdown resource.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                await attr.async_shutdown()
