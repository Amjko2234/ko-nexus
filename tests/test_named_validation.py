import pytest

from ko_nexus import Container, DiCircularDependencyError, DiValidationError

from ._classes import Cache, CircularA, CircularB, Config, Database


def test_validation_only_checks_defaults(container: Container) -> None:
    """Test that validation only validates default registrations."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    # Register invalid named registration (missing dependencies)
    class BrokenService:
        def __init__(self, missing: Cache) -> None:
            self.missing: Cache = missing

    container.register(BrokenService, name="broken", lifetime="transient")

    # Validation should pass because only defaults are validated
    container.validate()  # Should not raise


def test_validation_fails_for_invalid_default(container: Container) -> None:
    """Test that validation catches invalid default registrations."""

    class BrokenService:
        def __init__(self, missing: Cache) -> None:
            self.missing: Cache = missing

    container.register(BrokenService, lifetime="transient")  # Default

    with pytest.raises(DiValidationError):
        container.validate()


def test_validation_passes_with_valid_defaults_and_broken_named(
    container: Container,
) -> None:
    """Test validation passes when defaults are valid but named are broken."""

    container.register(Config, lifetime="singleton")
    container.register(Cache, lifetime="singleton")

    # Valid default
    class ValidService:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    container.register(ValidService, lifetime="transient")

    # Invalid named (missing `Database`)
    class InvalidService:
        def __init__(self, db: Database) -> None:
            self.db: Database = db

    container.register(InvalidService, name="broken", lifetime="transient")

    # Should pass - named not validated
    container.validate()


def test_circular_dependency_detection_with_names(container: Container) -> None:
    """Test circular dependency detection includes name in error message."""

    # Register with defaults for auto-wiring to work
    container.register(CircularA, lifetime="transient")
    container.register(CircularB, lifetime="transient")

    # Also register named versions (to test name appears in error)
    container.register(CircularA, name="named_a", lifetime="transient")
    container.register(CircularB, name="named_b", lifetime="transient")

    # Test default triggers circular dependency
    with pytest.raises(DiCircularDependencyError, match=r"CircularA\(default\)"):
        _ = container.resolve(CircularA)

    # Named also triggers circular dependency (same classes)
    with pytest.raises(DiCircularDependencyError, match=r"CircularA\(named_a\)"):
        _ = container.resolve(CircularA, name="named_a")


def test_circular_dependency_default_and_named_separate(container: Container) -> None:
    """Test that default and named registrations have separate circular checks."""

    # This is more of a sanity check - default and named should be treated
    # as distinct in the resolution stack

    container.register(Config, lifetime="singleton")
    container.register(Config, name="special", lifetime="singleton")

    # No circular dependency here
    c1: object = container.resolve(Config)
    c2: object = container.resolve(Config, name="special")

    assert c1 is not c2


def test_validation_with_only_named_registrations(container: Container) -> None:
    """Test validation when interface has only named registrations (no default)."""

    container.register(Config, name="named1", lifetime="singleton")
    container.register(Config, name="named2", lifetime="singleton")

    # Should pass - no defaults to validate
    container.validate()


def test_validation_with_default_depending_on_named_fails(
    container: Container,
) -> None:
    """Test that default registration can't depend on named registration."""

    container.register(Cache, name="special", lifetime="singleton")

    class ServiceNeedingCache:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    container.register(ServiceNeedingCache, lifetime="transient")

    # Should fail - default `Service` needs `Cache`, but `Cache` only has named
    with pytest.raises(DiValidationError):
        container.validate()


def test_validation_multiple_defaults_valid(container: Container) -> None:
    """Test validation with multiple valid default registrations."""

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(Cache, lifetime="singleton")

    class ServiceA:
        def __init__(self, config: Config, db: Database) -> None:
            self.config: Config = config
            self.db: Database = db

    class ServiceB:
        def __init__(self, cache: Cache, config: Config) -> None:
            self.cache: Cache = cache
            self.config: Config = config

    container.register(ServiceA, lifetime="transient")
    container.register(ServiceB, lifetime="transient")

    # Should pass - all defaults have valid dependencies
    container.validate()


def test_shutdown_resources_handles_named_registrations(container: Container) -> None:
    """Test that shutdown cleans up both default and named registrations."""

    cleanup_calls: list[str] = []

    def cleanup_default(_: Config) -> None:
        cleanup_calls.append("default")

    def cleanup_named(_: Config) -> None:
        cleanup_calls.append("named")

    container.register(Config, cleanup=cleanup_default, lifetime="singleton")
    container.register(
        Config, name="special", cleanup=cleanup_named, lifetime="singleton"
    )

    # Resolve both to create instances
    _ = container.resolve(Config)
    _ = container.resolve(Config, name="special")

    container.shutdown_resources()

    assert "default" in cleanup_calls
    assert "named" in cleanup_calls


@pytest.mark.asyncio
async def test_async_shutdown_resources_handles_named_registrations(
    container: Container,
) -> None:
    """Test async shutdown cleans up both default and named registrations."""

    cleanup_calls: list[str] = []

    async def async_cleanup_default(_: Config) -> None:
        cleanup_calls.append("default")

    async def async_cleanup_named(_: Config) -> None:
        cleanup_calls.append("named")

    container.register(Config, cleanup=async_cleanup_default, lifetime="singleton")
    container.register(
        Config, name="special", cleanup=async_cleanup_named, lifetime="singleton"
    )

    # Resolve both to create instances
    _ = await container.async_resolve(Config)
    _ = await container.async_resolve(Config, name="special")

    await container.async_shutdown_resources()

    assert "default" in cleanup_calls
    assert "named" in cleanup_calls
