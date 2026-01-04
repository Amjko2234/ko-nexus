import asyncio
from unittest.mock import Mock

import pytest

from ko_nexus import DiCallableError, DiUninitializedResourceError, Resource, resource

# =====================================================================================
#   With mocks
# =====================================================================================


def test_sync_nonsingleton_resource_life_with_mock() -> None:
    """Test basic resource lifecycle with nonsingleton, mocked callables."""

    # All `Provider` objects ensure all callables are functions with `__name__`
    # attribute or property
    init_mock: Mock = Mock(return_value="test_value")
    init_mock.__name__ = "<Mock>"
    cleanup_mock: Mock = Mock()
    cleanup_mock.__name__ = "<Mock>"

    resource_: Resource[Mock] = resource(
        initializer=init_mock,
        cleanup=cleanup_mock,
        singleton=False,
    )

    # Test resolve
    value: str = resource_.resolve()
    assert not resource_.is_resolved()  # Not a singleton
    assert value == "test_value"
    init_mock.assert_called_once()

    # Test get and is already resolved
    assert resource_.get() == "test_value"

    # Test shutdown
    resource_.shutdown()
    cleanup_mock.assert_called_once()


@pytest.mark.asyncio
async def test_async_nonsingleton_resource_life_with_mock() -> None:
    """Test basic resource lifecycle with nonsingleton, mocked callables."""

    # Real awaitable callables are used so that calling requires `await`
    async def async_init() -> str:
        await asyncio.sleep(0.01)
        return "test_value"

    async def async_cleanup(_: object) -> None:
        await asyncio.sleep(0.01)

    resource_: Resource[str] = resource(
        initializer=async_init,
        cleanup=async_cleanup,
        singleton=False,
    )

    # Test resolve
    value: str = await resource_.async_resolve()
    assert value == "test_value"

    # Test get and is already resolved
    assert resource_.get() == "test_value"

    # Test shutdown
    await resource_.async_shutdown()


def test_sync_singleton_resource_life_with_mock() -> None:
    """Test basic resource lifecycle with singleton, mocked callables."""

    init_mock: Mock = Mock(return_value="test_value")
    init_mock.__name__ = "<Mock>"
    cleanup_mock: Mock = Mock()
    cleanup_mock.__name__ = "<Mock>"

    resource_: Resource[Mock] = resource(
        initializer=init_mock,
        cleanup=cleanup_mock,
        singleton=False,
    )

    # Test resolve
    value: str = resource_.resolve()
    assert not resource_.is_resolved()  # Not a singleton
    assert value == "test_value"
    init_mock.assert_called_once()

    # Test get and is already resolved
    assert resource_.get() == "test_value"

    # Test shutdown
    resource_.shutdown()
    cleanup_mock.assert_called_once()


@pytest.mark.asyncio
async def test_async_singleton_resource_life_with_mock() -> None:
    """Test basic resource lifecycle with singleton, mocked callables."""

    async def async_init() -> str:
        await asyncio.sleep(0.01)
        return "test_value"

    async def async_cleanup(_: object) -> None:
        await asyncio.sleep(0.01)

    resource_: Resource[str] = resource(
        initializer=async_init,
        cleanup=async_cleanup,
        singleton=True,
    )

    # Test resolve
    value: str = await resource_.async_resolve()
    assert value == "test_value"
    assert resource_.is_resolved() is True

    # Test get and is already resolved
    assert resource_.get() == "test_value"

    # Test shutdown
    await resource_.async_shutdown()
    assert not resource_.is_resolved()


def test_resource_without_cleanup() -> None:
    """Test basic resource lifecycle without cleanup callable."""

    init_mock: Mock = Mock(return_value="test_value")
    init_mock.__name__ = "<Mock>"

    resource_: Resource[Mock] = resource(initializer=init_mock)

    value: str = resource_.resolve()
    assert value == "test_value"
    assert resource_.is_resolved() is True

    # Should not crash
    resource_.shutdown()
    assert not resource_.is_resolved()


def test_resource_calling_without_init_raises() -> None:
    """
    Test error raised when trying to get callable's value without initializing
    it's resource lifecycle
    """

    init_mock: Mock = Mock(return_value="test_value")
    init_mock.__name__ = "<Mock>"

    resource_: Resource[Mock] = resource(initializer=init_mock)

    with pytest.raises(DiUninitializedResourceError):
        _ = resource_.get()


def test_sync_calling_on_async_callable_raises() -> None:
    """
    Test error raised when trying to initialize async resources inside a sync context.
    """

    async def async_init() -> str:
        await asyncio.sleep(0.01)
        return "nothing"

    async def async_cleanup(_: object) -> None:
        pass

    resource_: Resource[str] = resource(initializer=async_init, cleanup=async_cleanup)

    with pytest.raises(
        TypeError, match=r"Cannot call sync `resolve\(\)` on an async `Resource`"
    ):
        _ = resource_.resolve()
    with pytest.raises(
        TypeError, match=r"Cannot call sync `shutdown\(\)` on an async `Resource`"
    ):
        _ = resource_.shutdown()


def test_passing_callable_without_name_raises() -> None:
    """Test all lazy callables must be non-anonymous functions."""

    with pytest.raises(TypeError, match="`factory` must be a function"):
        # Instantiated `Mock` objects are callables but does not carry `__name__`
        _ = resource(initializer=Mock())


def test_passing_lambda_callable_raises() -> None:
    """Test all lazy callables must be non-anonymous functions."""

    with pytest.raises(TypeError, match="`Lambda` is not supported"):
        _ = resource(initializer=lambda: "nothing")


def test_sync_callable_error_propagation() -> None:
    """Test any error raised by the callable will be translated to `DiCallableError`."""

    def failing_init() -> str:
        raise ValueError("Initialization failed")

    def failing_cleanup(_: object) -> None:
        raise ValueError("Cleanup failed")

    resource_: Resource[str] = resource(
        initializer=failing_init, cleanup=failing_cleanup
    )

    with pytest.raises(DiCallableError):
        _ = resource_.resolve()
    with pytest.raises(DiCallableError):
        # True shutdown is only executed if the resource exists
        resource_.resource = "value"
        _ = resource_.shutdown()


@pytest.mark.asyncio
async def test_async_callable_error_propagation() -> None:
    """Test any error raised by the callable will be translated to `DiCallableError`."""

    async def failing_init() -> str:
        raise ValueError("Initialization failed")

    async def failing_cleanup(_: object) -> None:
        raise ValueError("Cleanup failed")

    resource_: Resource[str] = resource(
        initializer=failing_init, cleanup=failing_cleanup
    )

    with pytest.raises(DiCallableError):
        _ = await resource_.async_resolve()
    with pytest.raises(DiCallableError):
        # True shutdown is only executed if the resource exists
        resource_.resource = "value"
        _ = await resource_.async_shutdown()
