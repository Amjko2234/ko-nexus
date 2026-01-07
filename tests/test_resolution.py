import pytest

from ko_nexus import Container

from ._classes import (
    Cache,
    Config,
    Database,
    OptionalDependencyService,
    UserService,
    create_async_service,
)


def test_deep_dependency_chain(configured_container: Container) -> None:
    """Test resolving deep dependency chains."""

    configured_container.register(UserService, lifetime="transient")
    service: object = configured_container.resolve(UserService)

    assert isinstance(service, UserService)
    assert isinstance(service.db, Database)
    assert isinstance(service.cache, Cache)
    assert isinstance(service.config, Config)
    assert service.db.config is service.config


def test_optional_dependency_registered(container: Container) -> None:
    """Test optional dependency when registered."""

    container.register(Cache, lifetime="singleton")
    container.register(OptionalDependencyService, lifetime="transient")
    service: object = container.resolve(OptionalDependencyService)

    assert service.cache is not None
    assert isinstance(service.cache, Cache)


def test_optional_dependency_not_registered(container: Container) -> None:
    """Test optional dependency when not registered."""

    container.register(OptionalDependencyService, lifetime="transient")
    service: object = container.resolve(OptionalDependencyService)

    assert service.cache is None


def test_resolve_during_registration(container: Container) -> None:
    """Test resolving dependencies during registration phase."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    # Resolve early
    config: object = container.resolve(Config)
    db: object = container.resolve(Database)

    # Use resolved instances in factory
    container.register_factory(
        UserService,
        factory=lambda: UserService(db, Cache(), config),
        lifetime="transient",
    )
    service: object = container.resolve(UserService)

    assert service.config is config
    assert service.db is db


@pytest.mark.asyncio
async def test_async_resolve_sync_dependency(container: Container) -> None:
    """Test async resolve with sync dependency."""

    container.register(Config, lifetime="singleton")
    config: object = await container.async_resolve(Config)

    assert isinstance(config, Config)


@pytest.mark.asyncio
async def test_async_factory(container: Container) -> None:
    """Test async factory function."""

    container.register(Config, Config, lifetime="singleton")
    container.register_factory(
        UserService, factory=create_async_service, lifetime="singleton"
    )
    service: object = await container.async_resolve(UserService)

    assert isinstance(service, UserService)
    assert isinstance(service.config, Config)
