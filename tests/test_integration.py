from ko_nexus import Container

from ._classes import (
    Cache,
    Config,
    Database,
    InMemoryRepository,
    IRepository,
    UserService,
)


def test_composition_root_pattern() -> None:
    """Test typical composition root pattern."""

    def create_container() -> Container:
        container: Container = Container()

        # Register infrastructure
        container.register(Config, lifetime="singleton")
        container.register(Database, lifetime="singleton")
        container.register(Cache, lifetime="singleton")

        # Pre-resolve config for conditional registration
        config: object = container.resolve(Config)

        # Conditional registration based on config
        if config.value == "test_config":
            container.register(
                IRepository, implementation=InMemoryRepository, lifetime="singleton"
            )
        else:
            container.register(IRepository, lifetime="singleton")

        # Register services
        container.register(UserService, UserService, lifetime="scoped")

        container.validate()
        return container

    container: Container = create_container()
    service: object = container.resolve(UserService)

    assert isinstance(service, UserService)
    assert isinstance(service.db, Database)
    assert isinstance(service.cache, Cache)


def test_scope_isolation(container: Container) -> None:
    """Test scoped lifetime isolation."""

    container.register(Config, lifetime="scoped")

    # First scope
    config1: object = container.resolve(Config)
    config2: object = container.resolve(Config)
    assert config1 is config2

    # Clear and new scope
    container.clear_scoped()
    config3: object = container.resolve(Config)
    assert config3 is not config1


def test_mixed_lifetimes_complex_graph(container: Container) -> None:
    """Test complex dependency graph with mixed lifetimes."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="scoped")
    container.register(Cache, lifetime="transient")
    container.register(UserService, lifetime="scoped")

    service1: object = container.resolve(UserService)
    service2: object = container.resolve(UserService)

    # Same service instance (scoped)
    assert service1 is service2

    # Same database (scoped)
    assert service1.db is service2.db

    # Same config (singleton)
    assert service1.config is service2.config

    # Different cache (transient)
    # Note: `Cache` is resolved once during `UserService` construction
    # so they'll be the same within the same `UserService` instance
    assert service1.cache is service2.cache

    # Clear scope
    container.clear_scoped()
    service3: object = container.resolve(UserService)

    # Different service (new scope)
    assert service3 is not service1

    # Different database (new scope)
    assert service3.db is not service1.db

    # Same config (singleton across scopes)
    assert service3.config is service1.config
