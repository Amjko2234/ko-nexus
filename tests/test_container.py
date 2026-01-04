import pytest

from ko_nexus import Container, DiContainerError

from ._class import APIClient, AsyncContainer, Database, MixedContainer, SyncContainer


@pytest.mark.asyncio
async def test_mixed_container_init(
    mixed_container_with_resources: MixedContainer,
) -> None:
    """Test mixed container initializaton with resources."""

    container: MixedContainer = mixed_container_with_resources

    assert isinstance(container.db.get(), Database)
    assert isinstance(container.db_singleton.get(), Database)
    assert isinstance(container.apiclient.get(), APIClient)
    assert isinstance(container.apiclient_singleton.get(), APIClient)


def test_sync_only_container_life() -> None:
    """Test basic container lifecycle with resources."""

    container: SyncContainer = SyncContainer()
    container.init_resources()

    assert isinstance(container.db.get(), Database)
    assert isinstance(container.db_singleton.get(), Database)

    container.shutdown_resources()


@pytest.mark.asyncio
async def test_async_container_life() -> None:
    """Test basic container lifecycle with resources."""

    container: AsyncContainer = AsyncContainer()
    await container.async_init_resources()

    assert isinstance(container.apiclient.get(), APIClient)
    assert isinstance(container.apiclient_singleton.get(), APIClient)

    await container.async_shutdown_resources()


@pytest.mark.asyncio
async def test_container_resource_life(
    mixed_container_with_resources: MixedContainer,
) -> None:
    """Test comprehensive container lifecycle with resources."""

    container: MixedContainer = mixed_container_with_resources

    # Two variables for singletons to check earlier if their attribute values
    # synchronize
    db: Database = container.db.get()
    db_singleton1: Database = container.db_singleton.get()
    db_singleton2: Database = container.db_singleton.get()

    apiclient: APIClient = container.apiclient.get()
    apiclient_singleton1: APIClient = container.apiclient_singleton.get()
    apiclient_singleton2: APIClient = container.apiclient_singleton.get()

    # Initial state
    assert len(db.query_history) == 0
    assert len(db_singleton1.query_history) == 0
    assert apiclient.session is None
    assert apiclient_singleton1.session is None

    # Test query histories are synchronized between two database (singleton) variables
    _ = db.query(query="Query 1")
    _ = db_singleton1.query(query="Query 2")
    _ = await db_singleton2.async_query(query="Query 3")
    assert len(db.query_history) == 1
    assert len(db_singleton1.query_history) == 2
    assert len(db_singleton2.query_history) == 2

    # Normal test
    await apiclient.connect()
    assert apiclient.session == "active"
    await apiclient.disconnect()

    # Test session state is synchronized between two apiclient (singleton) variables
    await apiclient_singleton1.connect()
    assert apiclient_singleton2.session == "active"
    await apiclient_singleton2.disconnect()
    assert apiclient_singleton1.session is None
    # Leave `session` in a state of "active" to check later:
    # (1) if the singleton maintained its state
    # (2) if the nonsingleton's state was reset to `None`
    await apiclient_singleton1.connect()
    await apiclient.connect()

    # Re-initializing should not restart singletons
    await container.async_init_resources()

    # Edge case: re-defining should only change nonsingleton instances--
    # singletons should remain in their latest state or hold their latest value/s
    db = container.db.get()
    db_singleton1 = container.db_singleton.get()
    db_singleton2 = container.db_singleton.get()
    apiclient = container.apiclient.get()
    apiclient_singleton1 = container.apiclient_singleton.get()
    apiclient_singleton2 = container.apiclient_singleton.get()
    assert len(db.query_history) == 0
    assert len(db_singleton1.query_history) == 2
    assert len(db_singleton2.query_history) == 2
    assert apiclient.session is None
    assert apiclient_singleton1.session == "active"


@pytest.mark.asyncio
async def test_empty_container_is_fine() -> None:
    """Test that an empty container lifecycle will not raise any error."""

    class EmptyContainer(Container):
        def __init__(self) -> None:
            super().__init__()

    # Should not crash
    container: EmptyContainer = EmptyContainer()
    await container.async_init_resources()
    await container.async_shutdown_resources()


def test_sync_calling_on_async_callable_raises() -> None:
    """
    Test error raised when trying to initialize async resources inside a sync context.
    """

    container: AsyncContainer = AsyncContainer()
    with pytest.raises(DiContainerError, match="Failed to initialize resources"):
        container.init_resources()
    with pytest.raises(DiContainerError, match="Failed to shutdown resources"):
        container.shutdown_resources()


def test_container_str_and_repr() -> None:
    """Test `str` and `repr` representation of containers."""

    sync_container: SyncContainer = SyncContainer()
    assert str(sync_container) == "SyncContainer"
    assert repr(sync_container) == "SyncContainer"

    async_container: AsyncContainer = AsyncContainer()
    assert str(async_container) == "AsyncContainer"
    assert repr(async_container) == "AsyncContainer"
