import pytest

from ko_nexus import (
    Container,
    DiCircularDependencyError,
    DiResolutionError,
    DiValidationError,
)

from ._classes import CircularA, CircularB, Config, UserService


def test_resolve_unregistered_type(container: Container) -> None:
    """Test resolving unregistered type raises error."""

    with pytest.raises(DiResolutionError, match="not registered"):
        _ = container.resolve(Config)


def test_circular_dependency_detection(container: Container) -> None:
    """Test circular dependency detection."""

    container.register(CircularA, lifetime="transient")
    container.register(CircularB, lifetime="transient")

    with pytest.raises(DiCircularDependencyError, match="Circular dependency"):
        _ = container.resolve(CircularA)


def test_missing_dependency_parameter(container: Container) -> None:
    """Test missing required dependency raises error."""

    class MissingDepService:
        def __init__(self, unknown: Config) -> None:
            self.unknown: Config = unknown

    container.register(
        MissingDepService, implementation=MissingDepService, lifetime="transient"
    )

    with pytest.raises(DiResolutionError, match="Cannot resolve parameter"):
        _ = container.resolve(MissingDepService)


def test_validation_catches_errors(container: Container) -> None:
    """Test validation catches configuration errors."""

    container.register(Config, lifetime="singleton")
    container.register(UserService, implementation=UserService, lifetime="transient")
    # Missing Database and Cache registrations

    with pytest.raises(DiValidationError):
        container.validate()


def test_validation_success(configured_container: Container) -> None:
    """Test validation passes for valid configuration."""

    configured_container.register(
        UserService, implementation=UserService, lifetime="transient"
    )

    # Should not raise
    configured_container.validate()
