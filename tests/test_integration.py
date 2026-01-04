# pyright: reportPrivateUsage=false

import pytest

from ko_nexus import Container, Dependency, DiDependencyError

from ._class import APIClient, ContainerWithDependency, Database, MixedContainer


@pytest.mark.asyncio
async def test_container_with_dependency_injection() -> None:
    """Test basic dependency injection through container."""

    container_dep: MixedContainer = MixedContainer()
    container_with_dep: ContainerWithDependency = ContainerWithDependency(
        mixed_container=container_dep
    )

    assert container_with_dep.mixed_container_dep.is_provided()
    assert container_with_dep.mixed_container_dep.resolve() is container_dep
    assert container_with_dep.mixed_container_dep() is container_dep

    # Test resources
    _ = await container_with_dep.mixed_container_dep().async_init_resources()
    db: object = container_with_dep.mixed_container_dep().db.get()
    apiclient: object = container_with_dep.mixed_container_dep().apiclient.get()
    assert isinstance(db, Database)
    assert isinstance(apiclient, APIClient)
    _ = await container_with_dep.mixed_container_dep().async_shutdown_resources()


def test_container_missing_dependency_raises() -> None:
    """Test error when dependency is not provided to container."""

    class ContainerWithMissingDependency(Container):
        __name__: str = "ContainerWithMissingDependency"

        def __init__(self, mixed_container: MixedContainer) -> None:
            self.mixed_container_dep: Dependency[MixedContainer] = Dependency[
                MixedContainer
            ](name="mixed_container_dependency")
            # Not specified `__init__(mixed_container_dep=mixed_container)`
            # means that it isn't injected
            super().__init__()

    container_dep: MixedContainer = MixedContainer()
    with pytest.raises(
        DiDependencyError,
        match="Container `ContainerWithMissingDependency` has missing dependencies",
    ):
        _ = ContainerWithMissingDependency(mixed_container=container_dep)


def test_container_undeclared_dependency_raises() -> None:
    """Test error raised when providing an undeclared dependency to the container."""

    class ContainerWithUndeclaredDependency(Container):
        __name__: str = "ContainerWithUndeclaredDependency"

        def __init__(self, mixed_container: MixedContainer) -> None:
            super().__init__(mixed_container_dep=mixed_container)

    container_dep: MixedContainer = MixedContainer()
    with pytest.raises(
        DiDependencyError,
        match="Object `mixed_container_dep` is not a declared dependency",
    ):
        _ = ContainerWithUndeclaredDependency(mixed_container=container_dep)
