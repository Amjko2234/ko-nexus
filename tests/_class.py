import asyncio

from ko_nexus import Container, Dependency, Resource, resource

# =====================================================================================
#   Mock objects (for test purposes)
# =====================================================================================


class CallableService:
    def __init__(self) -> None:
        self.called: int = 0

    def __call__(self) -> None:
        self.called += 1


class Database:
    def __init__(self, connection_string: str = "default") -> None:
        self.connection_string: str = connection_string
        self.query_history: list[str] = []
        self.connected: bool = True

    def query(self, query: str) -> str:
        self.query_history.append(query)
        return f"Query `{query}` executed"

    async def async_query(self, query: str) -> str:
        await asyncio.sleep(0.01)
        self.query_history.append(query)
        return f"Query `{query}` executed"

    def close(self) -> None:
        self.connected = False


class APIClient:
    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key
        self.session: str | None = None

    async def connect(self) -> None:
        await asyncio.sleep(0.01)
        self.session = "active"

    async def disconnect(self) -> None:
        await asyncio.sleep(0.01)
        self.session = None


class ExampleDependency:
    def __init__(self, value: str = "default") -> None:
        self.value: str = value
        self.initialized: bool = True

    def do_something(self) -> str:
        return f"Did something with `{self.value}`"


class AnotherExampleDependency:
    def __init__(self, number: int = 0) -> None:
        self.number: int = number

    def twice(self) -> int:
        return self.number * 2


class SyncContainer(Container):
    __name__: str = "SyncContainer"

    def __init__(self) -> None:
        # Database resource
        def _init_db() -> Database:
            return Database(connection_string="test://localhost")

        def _cleanup_db(db: Database) -> None:
            return db.close()

        self.db: Resource[Database] = resource(
            initializer=_init_db,
            cleanup=_cleanup_db,
            singleton=False,
        )
        self.db_singleton: Resource[Database] = resource(
            initializer=_init_db,
            cleanup=_cleanup_db,
            singleton=True,
        )
        super().__init__()


class AsyncContainer(Container):
    __name__: str = "AsyncContainer"

    def __init__(self) -> None:
        # APIClient resource
        async def _init_apiclient() -> APIClient:
            return APIClient(api_key="test-api-key")

        async def _cleanup_apiclient(client: APIClient) -> None:
            return await client.disconnect()

        self.apiclient: Resource[APIClient] = resource(
            initializer=_init_apiclient,
            cleanup=_cleanup_apiclient,
            singleton=False,
        )
        self.apiclient_singleton: Resource[APIClient] = resource(
            initializer=_init_apiclient,
            cleanup=_cleanup_apiclient,
            singleton=True,
        )
        super().__init__()


class MixedContainer(Container):
    __name__: str = "MixedContainer"

    def __init__(self) -> None:
        # Database resource
        def _init_db() -> Database:
            return Database(connection_string="test://localhost")

        def _cleanup_db(db: Database) -> None:
            return db.close()

        self.db: Resource[Database] = resource(
            initializer=_init_db,
            cleanup=_cleanup_db,
            singleton=False,
        )
        self.db_singleton: Resource[Database] = resource(
            initializer=_init_db,
            cleanup=_cleanup_db,
            singleton=True,
        )

        # APIClient resource
        async def _init_apiclient() -> APIClient:
            return APIClient(api_key="test-api-key")

        async def _cleanup_apiclient(client: APIClient) -> None:
            return await client.disconnect()

        self.apiclient: Resource[APIClient] = resource(
            initializer=_init_apiclient,
            cleanup=_cleanup_apiclient,
            singleton=False,
        )
        self.apiclient_singleton: Resource[APIClient] = resource(
            initializer=_init_apiclient,
            cleanup=_cleanup_apiclient,
            singleton=True,
        )
        super().__init__()


class ContainerWithDependency(Container):
    def __init__(self, mixed_container: MixedContainer) -> None:
        self.mixed_container_dep: Dependency[MixedContainer] = Dependency[
            MixedContainer
        ]()

        super().__init__(mixed_container_dep=mixed_container)
