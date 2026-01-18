import pytest

from ko_nexus import Container, DiResolutionError

from ._classes import (
    Cache,
    Config,
    Database,
    InMemoryRepository,
    IRepository,
    SQLRepository,
)


def test_default_registration_unchanged(container: Container) -> None:
    """Test that default registration behavior is unchanged."""

    container.register(Config, lifetime="singleton")

    config1: object = container.resolve(Config)
    config2: object = container.resolve(Config)

    assert config1 is config2
    assert isinstance(config1, Config)


def test_named_registration_basic(container: Container) -> None:
    """Test basic named registration and resolution."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    # Register two named implementations of `IRepository`
    container.register(
        IRepository, implementation=SQLRepository, name="sql", lifetime="singleton"
    )
    container.register(
        IRepository,
        implementation=InMemoryRepository,
        name="inmemory",
        lifetime="singleton",
    )

    sql_repo: object = container.resolve(IRepository, name="sql")
    inmem_repo: object = container.resolve(IRepository, name="inmemory")

    assert isinstance(sql_repo, SQLRepository)
    assert isinstance(inmem_repo, InMemoryRepository)
    assert sql_repo is not inmem_repo


def test_default_and_named_coexist(container: Container) -> None:
    """Test that default and named registrations can coexist."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    # Default registration
    container.register(IRepository, implementation=SQLRepository, lifetime="singleton")

    # Named registration
    container.register(
        IRepository,
        implementation=InMemoryRepository,
        name="inmemory",
        lifetime="singleton",
    )

    default_repo: object = container.resolve(IRepository)
    named_repo: object = container.resolve(IRepository, name="inmemory")

    assert isinstance(default_repo, SQLRepository)
    assert isinstance(named_repo, InMemoryRepository)
    assert default_repo is not named_repo


def test_resolve_nonexistent_named_registration(container: Container) -> None:
    """Test resolving a name that doesn't exist raises error."""

    container.register(Config, lifetime="singleton")

    with pytest.raises(DiResolutionError, match="with name `nonexistent`"):
        _ = container.resolve(Config, name="nonexistent")


def test_resolve_named_when_only_default_exists(container: Container) -> None:
    """Test resolving named variant when only default exists."""

    container.register(Config, lifetime="singleton")

    with pytest.raises(DiResolutionError, match="with name `special`"):
        _ = container.resolve(Config, name="special")


def test_resolve_default_when_only_named_exists(container: Container) -> None:
    """Test resolving default when only named registrations exist."""

    container.register(Config, name="special", lifetime="singleton")

    with pytest.raises(DiResolutionError, match="not registered"):
        _ = container.resolve(Config)  # No default


def test_named_registration_with_instance(container: Container) -> None:
    """Test `register_instance` with name parameter."""

    config1: Config = Config()
    config1.value = "config1"

    config2: Config = Config()
    config2.value = "config2"

    container.register_instance(Config, instance=config1)  # Default
    container.register_instance(Config, instance=config2, name="alternate")

    default: object = container.resolve(Config)
    alternate: object = container.resolve(Config, name="alternate")

    assert default is config1
    assert alternate is config2
    assert default.value == "config1"
    assert alternate.value == "config2"


def test_named_registration_with_factory(container: Container) -> None:
    """Test `register_factory` with name parameter."""

    container.register_factory(
        Config,
        factory=lambda: Config(),
        lifetime="singleton",
    )

    def create_special_config() -> Config:
        c: Config = Config()
        c.value = "special"
        return c

    container.register_factory(
        Config,
        factory=create_special_config,
        name="special",
        lifetime="singleton",
    )

    default: object = container.resolve(Config)
    special: object = container.resolve(Config, name="special")

    assert default.value == "test_config"
    assert special.value == "special"


def test_multiple_named_registrations_same_interface(container: Container) -> None:
    """Test multiple named registrations of the same interface."""

    container.register(Config, name="config1", lifetime="singleton")
    container.register(Config, name="config2", lifetime="singleton")
    container.register(Config, name="config3", lifetime="singleton")

    c1: object = container.resolve(Config, name="config1")
    c2: object = container.resolve(Config, name="config2")
    c3: object = container.resolve(Config, name="config3")

    assert c1 is not c2
    assert c2 is not c3
    assert c1 is not c3


def test_named_registration_respects_lifetime(container: Container) -> None:
    """Test that named registrations respect lifetime strategies."""

    # Singleton named
    container.register(Config, name="singleton", lifetime="singleton")
    s1: object = container.resolve(Config, name="singleton")
    s2: object = container.resolve(Config, name="singleton")
    assert s1 is s2

    # Transient named
    container.register(Config, name="transient", lifetime="transient")
    t1: object = container.resolve(Config, name="transient")
    t2: object = container.resolve(Config, name="transient")
    assert t1 is not t2

    # Scoped named
    container.register(Config, name="scoped", lifetime="scoped")
    sc1: object = container.resolve(Config, name="scoped")
    sc2: object = container.resolve(Config, name="scoped")
    assert sc1 is sc2

    container.clear_scoped()
    sc3: object = container.resolve(Config, name="scoped")
    assert sc3 is not sc1


def test_autowiring_ignores_named_registrations(container: Container) -> None:
    """Test that auto-wiring only uses default registrations."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(Cache, name="special", lifetime="singleton")

    # `Cache` is required by `Database` but only registered with name
    # This should fail because auto-wiring only looks at defaults

    class ServiceWithCache:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    container.register(ServiceWithCache, lifetime="transient")

    with pytest.raises(DiResolutionError, match="not registered"):
        _ = container.resolve(ServiceWithCache)


def test_manual_factory_with_named_dependencies(container: Container) -> None:
    """Test manually constructing service with named dependencies."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(Cache, name="redis", lifetime="singleton")
    container.register(Cache, name="inmemory", lifetime="singleton")

    class ServiceA:
        def __init__(self, cache: Cache, db: Database) -> None:
            self.cache: Cache = cache
            self.db: Database = db

    class ServiceB:
        def __init__(self, cache: Cache, db: Database) -> None:
            self.cache: Cache = cache
            self.db: Database = db

    # Register factories that explicitly resolve named caches
    container.register_factory(
        ServiceA,
        factory=lambda: ServiceA(
            cache=container.resolve(Cache, name="redis"),
            db=container.resolve(Database),
        ),
        lifetime="singleton",
    )

    container.register_factory(
        ServiceB,
        factory=lambda: ServiceB(
            cache=container.resolve(Cache, name="inmemory"),
            db=container.resolve(Database),
        ),
        lifetime="singleton",
    )

    service_a: object = container.resolve(ServiceA)
    service_b: object = container.resolve(ServiceB)

    assert isinstance(service_a, ServiceA)
    assert isinstance(service_b, ServiceB)
    assert service_a.cache is not service_b.cache
    assert service_a.db is service_b.db  # Same singleton Database


@pytest.mark.asyncio
async def test_async_resolve_named_registration(container: Container) -> None:
    """Test async resolution of named registrations."""

    container.register(Config, name="async_config", lifetime="singleton")

    config: object = await container.async_resolve(Config, name="async_config")

    assert isinstance(config, Config)


def test_overwrite_named_registration(container: Container) -> None:
    """Test that re-registering with same name overwrites previous registration."""

    config1: Config = Config()
    config1.value = "first"

    config2: Config = Config()
    config2.value = "second"

    container.register_instance(Config, instance=config1, name="test")
    first: object = container.resolve(Config, name="test")
    assert first.value == "first"

    # Re-register with same name
    container.register_instance(Config, instance=config2, name="test")
    second: object = container.resolve(Config, name="test")
    assert second.value == "second"
    assert second is not first


def test_clear_scoped_affects_all_named_registrations(container: Container) -> None:
    """Test that clear_scoped clears all named scoped instances."""

    container.register(Config, lifetime="scoped")
    container.register(Config, name="named", lifetime="scoped")

    default1: object = container.resolve(Config)
    named1: object = container.resolve(Config, name="named")

    container.clear_scoped()

    default2: object = container.resolve(Config)
    named2: object = container.resolve(Config, name="named")

    assert default2 is not default1
    assert named2 is not named1
