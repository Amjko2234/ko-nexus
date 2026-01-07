from ko_nexus import Container

from ._classes import Config, Database, InMemoryRepository, IRepository, SQLRepository


def test_resolve_interface_to_implementation(container: Container) -> None:
    """Test resolving interface returns implementation."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(IRepository, implementation=SQLRepository, lifetime="scoped")

    repo: object = container.resolve(IRepository)

    assert isinstance(repo, SQLRepository)
    assert isinstance(repo.db, Database)


def test_swap_implementation(container: Container) -> None:
    """Test swapping implementation for same interface."""

    container.register(
        IRepository, implementation=InMemoryRepository, lifetime="singleton"
    )
    repo1: object = container.resolve(IRepository)

    assert isinstance(repo1, InMemoryRepository)

    # Re-register with different implementation
    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(IRepository, implementation=SQLRepository, lifetime="singleton")
    repo2: object = container.resolve(IRepository)

    assert isinstance(repo2, SQLRepository)
