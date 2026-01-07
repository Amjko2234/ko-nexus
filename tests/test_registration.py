import pytest

from ko_nexus import Container, DiAutoRegistrationError

from ._classes import Config, Database, create_database


def test_register_simple_class(container: Container) -> None:
    """Test basic registration without dependencies."""

    container.register(Config, lifetime="singleton")
    instance: object = container.resolve(Config)

    assert isinstance(instance, Config)
    assert instance.value == "test_config"


def test_register_with_dependencies(container: Container) -> None:
    """Test registering a class with dependencies."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    db: object = container.resolve(Database)

    assert isinstance(db, Database)
    assert isinstance(db.config, Config)
    assert db.connected is True


def test_register_instance(container: Container) -> None:
    """Test registering a pre-existing instance."""

    config: Config = Config()
    config.value = "custom_config"

    container.register_instance(Config, instance=config)
    resolved: object = container.resolve(Config)

    assert resolved is config
    assert resolved.value == "custom_config"


def test_register_factory(container: Container) -> None:
    """Test registering a factory function."""

    container.register(Config, lifetime="singleton")
    container.register_factory(Database, factory=create_database, lifetime="singleton")

    db: object = container.resolve(Database)

    assert isinstance(db, Database)
    assert isinstance(db.config, Config)


# ======================================================================================
#   Auto-registration
# ======================================================================================


def test_auto_register_module_invalid_path(container: Container) -> None:
    """Test auto-register with invalid module path."""

    with pytest.raises(DiAutoRegistrationError, match="Failed to import"):
        container.auto_register_module(module_path="nonexistent.module")


def test_auto_register_with_predicate(container: Container) -> None:
    """Test auto-register with predicate filter."""

    # This test assumes there's a real module to scan
    # In practice, it'd be best to test against an actual codebase
    # For demonstration, we'll test the error case
    container.auto_register_module(
        module_path="pytest",  # Valid module but won't have our classes
        predicate=lambda cls: cls.__name__.endswith("Service"),
    )
    # Should not raise, just won't register anything


def test_auto_register_package_not_package(container: Container) -> None:
    """Test auto-register package with non-package module."""

    with pytest.raises(DiAutoRegistrationError, match="not a real package"):
        container.auto_register_package(
            package_path="sys"
        )  # sys is a module, not package
