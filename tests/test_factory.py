# pyright: reportPrivateUsage=false

from collections.abc import Awaitable, Callable

import pytest

from ko_nexus import (
    AsyncFactory,
    DiCallableError,
    Factory,
    async_factory,
    factory,
)

from ._class import CallableService


def test_sync_factory(sync_service: Callable[[], CallableService]) -> None:
    """Test `Factory[T]` instantiation and does not return singletons of `T`."""

    svc_singleton1: Factory[CallableService] = factory(sync_service)

    # Test not singletons
    svc1: CallableService = svc_singleton1()
    svc2: CallableService = svc_singleton1()
    assert svc1 is not svc2

    # Test calls not syncing
    svc1()
    svc2()
    assert svc1.called == 1
    assert svc2.called == 1
    svc2()
    assert svc2.called == 2
    assert svc1.called == 1


@pytest.mark.asyncio
async def test_async_factory(
    async_service: Callable[[], Awaitable[CallableService]],
) -> None:
    """Test `AsyncFactory[T]` instantiation and does not return singletons of `T`."""

    svc_singleton1: AsyncFactory[CallableService] = async_factory(async_service)

    # Test not singletons
    svc1: CallableService = await svc_singleton1()
    svc2: CallableService = await svc_singleton1()
    assert svc1 is not svc2

    # Test calls not syncing
    svc1()
    svc2()
    assert svc1.called == 1
    assert svc2.called == 1
    svc2()
    assert svc2.called == 2
    assert svc1.called == 1


def test_lambda_factory_not_allowed() -> None:
    """
    `Lambda` callables are not allowed for lazy calls as anonymous functions are
    difficult to trace if something internally raises an error.
    """

    # No check for asynchronous factories as async lambdas are impossible.
    with pytest.raises(TypeError, match="`Lambda` is not supported."):
        _ = factory(lambda: CallableService())


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
        _ = factory(crash_sync_service)()
    with pytest.raises(DiCallableError):
        _ = await async_factory(crash_async_service)()
