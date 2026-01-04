# pyright: reportPrivateUsage=false

from collections.abc import Awaitable, Callable

import pytest

from ko_nexus import (
    AsyncSingleton,
    DiCallableError,
    Singleton,
    async_singleton,
    singleton,
)

from ._class import CallableService


def test_sync_singleton(sync_service: Callable[[], CallableService]) -> None:
    """Test `Singleton[T]` instantiation and does return singletons of `T`."""

    svc_singleton1: Singleton[CallableService] = singleton(sync_service)

    # Test singleton
    svc1: CallableService = svc_singleton1()
    assert svc_singleton1._instance is not None
    svc2: CallableService = svc_singleton1()
    assert svc1 is svc2

    # Test calls are syncing
    svc1()
    svc2()
    assert svc1.called == 2


@pytest.mark.asyncio
async def test_async_singleton(
    async_service: Callable[[], Awaitable[CallableService]],
) -> None:
    """Test `AsyncSingleton[T]` instantiation and does return singletons of `T`."""

    svc_singleton1: AsyncSingleton[CallableService] = async_singleton(async_service)

    # Test singleton
    svc1: CallableService = await svc_singleton1()
    assert svc_singleton1._instance is not None
    svc2: CallableService = await svc_singleton1()
    assert svc1 is svc2

    # Test calls are syncing
    svc1()
    svc2()
    assert svc1.called == 2


def test_lambda_singleton_not_allowed() -> None:
    """
    `Lambda` callables are not allowed for lazy calls as anonymous functions are
    difficult to trace if something internally raises an error.
    """

    # No check for asynchronous factories as async lambdas are impossible.
    with pytest.raises(TypeError, match="`Lambda` is not supported."):
        _ = singleton(lambda: CallableService())


@pytest.mark.asyncio
async def test_callable_error_propagation(
    crash_sync_service: Callable[[], CallableService],
    crash_async_service: Callable[[], Awaitable[CallableService]],
) -> None:
    """
    Any errors raised by the internal callable should be translated to
    `DiCallableError`.
    """

    with pytest.raises(DiCallableError):
        _ = singleton(crash_sync_service)()
    with pytest.raises(DiCallableError):
        _ = await async_singleton(crash_async_service)()
