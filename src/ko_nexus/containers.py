from typing import override

from .exceptions import DiCallableError, DiContainerError, DiDependencyError
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
            * `DiDependencyError`:
            Required dependencies are missing (unpassed) or are not declared
            dependencies.
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
                    f"Object `{name}` is not a declared dependency of Container"
                    + f" `{self.__name__}`"
                )
            instance_dependencies[name].provide(value)

        # Validate all dependencies that are provided
        missing: list[str] = []
        for name, dep in instance_dependencies.items():
            if not dep.is_provided():
                missing.append(name)

        if missing:
            raise DiDependencyError(
                f"Container `{self.__name__}` has missing"
                + f" dependencies: {', '.join(missing)}"
            )

    def init_resources(self) -> None:
        """
        Initialize all sync `Resource` providers in this container.
        This forces lazy resources to immediately initialize.

        It calls `resolve()` of all `Resource` providers.

        Raises:
            * `DiContainerError`:
               Failure to initialize resources due to underying errors.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                try:
                    attr.resolve()  # Trigger intialization
                except (TypeError, RuntimeError) as exc:
                    raise DiContainerError(
                        "Failed to initialize resources",
                        service=self.__class__.__name__,
                    ) from exc
                except DiCallableError:
                    raise

    async def async_init_resources(self) -> None:
        """
        Initialize all async/sync `Resource` providers in this container.
        This forces lazy resources to immediately initialize.

        It calls `async_resolve()` of all `Resource` providers.

        Raises:
            * `DiContainerError`:
               Failure to initialize resources due to underying errors.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                try:
                    await attr.async_resolve()  # Trigger intialization
                except RuntimeError as exc:
                    raise DiContainerError(
                        "Failed to initialize resources",
                        service=self.__class__.__name__,
                    ) from exc
                except DiCallableError:
                    raise

    def shutdown_resources(self) -> None:
        """
        Shutdown all sync `Resource` providers in this container.

        Calls the cleanup function for each initialized resource.
        Should be called when the container is no longer needed.

        Raises:
            * `DiContainerError`:
               Failure to initialize resources due to underying errors.
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                try:
                    attr.shutdown()
                except TypeError as exc:
                    raise DiContainerError(
                        "Failed to shutdown resources",
                        service=self.__class__.__name__,
                    ) from exc
                except DiContainerError:
                    raise

    async def async_shutdown_resources(self) -> None:
        """
        Shutdown all async/sync `Resource` providers in this container.

        Calls the cleanup function for each initialized resource.
        Should be called when the container is no longer needed.

        Raises:
            * `DiCallableError`: An unexpected error occured when calling the factory.
        """

        for name in dir(self):
            if name.startswith("_"):
                continue
            attr: object | None = getattr(self, name, None)
            if isinstance(attr, Resource):
                try:
                    await attr.async_shutdown()
                except DiCallableError:
                    raise
