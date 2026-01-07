from ko_nexus import Container

from ._classes import Config, Database, TransientService


def test_singleton_returns_same_instances(container: Container) -> None:
    """Test singleton returns the same instance every resolution."""

    container.register(Config, lifetime="singleton")

    instance1: object = container.resolve(Config)
    instance2: object = container.resolve(Config)

    assert instance1 is instance2


def test_transient_returns_different_instances(container: Container) -> None:
    """Test transient returns new instances every resolution."""

    container.register(TransientService, lifetime="transient")

    TransientService.instance_count = 0
    instance1: object = container.resolve(TransientService)
    instance2: object = container.resolve(TransientService)

    assert instance1 is not instance2
    assert instance1.id == 1
    assert instance2.id == 2


def test_scoped_returns_same_within_scope(container: Container) -> None:
    """Test scoped returns same instances within scope every resolution."""

    container.register(Config, lifetime="scoped")

    instance1: object = container.resolve(Config)
    instance2: object = container.resolve(Config)

    assert instance1 is instance2

    # Clear scope and resolve again
    container.clear_scoped()
    instance3: object = container.resolve(Config)

    assert instance3 is not instance1


def test_singleton_with_transient_dependency(container: Container) -> None:
    """Test singleton service with transient dependency resolves correctly."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="transient")

    db1: object = container.resolve(Database)
    db2: object = container.resolve(Database)

    assert db1 is not db2
    assert db1.config is db2.config
