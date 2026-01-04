from collections.abc import AsyncGenerator, Awaitable, Callable, Generator

import pytest
import pytest_asyncio

from ._class import (
    APIClient,
    AsyncContainer,
    CallableService,
    Database,
    MixedContainer,
    SyncContainer,
)

# =====================================================================================
#   Factory/Singleton fixtures
# =====================================================================================


@pytest.fixture
def sync_service() -> Callable[[], CallableService]:
    def _func() -> CallableService:
        return CallableService()

    return _func


@pytest.fixture
def crash_sync_service() -> Callable[[], CallableService]:
    def _func() -> CallableService:
        raise RuntimeError()

    return _func


@pytest_asyncio.fixture
async def async_service() -> Callable[[], Awaitable[CallableService]]:
    async def _func() -> CallableService:
        return CallableService()

    return _func


@pytest_asyncio.fixture
async def crash_async_service() -> Callable[[], Awaitable[CallableService]]:
    async def _func() -> CallableService:
        raise RuntimeError()

    return _func


# =====================================================================================
#   Container & Resource fixtures
# =====================================================================================


@pytest.fixture(scope="session")
def sync_container_with_resources() -> Generator[SyncContainer, None]:
    container: SyncContainer = SyncContainer()
    container.init_resources()
    yield container
    container.shutdown_resources()


@pytest_asyncio.fixture(scope="session")
async def async_container_with_resources() -> AsyncGenerator[AsyncContainer, None]:
    container: AsyncContainer = AsyncContainer()
    await container.async_init_resources()
    yield container
    await container.async_shutdown_resources()


@pytest_asyncio.fixture(scope="session")
async def mixed_container_with_resources() -> AsyncGenerator[MixedContainer, None]:
    container: MixedContainer = MixedContainer()
    await container.async_init_resources()
    yield container
    await container.async_shutdown_resources()


@pytest.fixture(scope="session")
def db_resource(
    sync_container_with_resources: SyncContainer,
) -> Generator[Database, None]:
    container: SyncContainer = sync_container_with_resources
    yield container.db.get()


@pytest.fixture(scope="session")
def db_singleton_resource(
    sync_container_with_resources: SyncContainer,
) -> Generator[Database, None]:
    container: SyncContainer = sync_container_with_resources
    yield container.db_singleton.get()


@pytest_asyncio.fixture(scope="session")
async def apiclient_resource(
    async_container_with_resources: AsyncContainer,
) -> AsyncGenerator[APIClient, None]:
    container: AsyncContainer = async_container_with_resources
    yield container.apiclient.get()


@pytest_asyncio.fixture(scope="session")
async def apiclient_singleton_resource(
    async_container_with_resources: AsyncContainer,
) -> AsyncGenerator[APIClient, None]:
    container: AsyncContainer = async_container_with_resources
    yield container.apiclient_singleton.get()
