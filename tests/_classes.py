from __future__ import annotations

from typing import Protocol


class Config:
    def __init__(self) -> None:
        self.value: str = "test_config"


class Database:
    def __init__(self, config: Config) -> None:
        self.config: Config = config
        self.storage: list[str] = []
        self.connected: bool = True


class Cache:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}


class UserService:
    def __init__(self, db: Database, cache: Cache, config: Config) -> None:
        self.db: Database = db
        self.cache: Cache = cache
        self.config: Config = config


class TransientService:
    instance_count: int = 0

    def __init__(self) -> None:
        TransientService.instance_count += 1
        self.id: int = TransientService.instance_count


class IRepository(Protocol):
    def save(self, data: str) -> None: ...


class SQLRepository:
    def __init__(self, db: Database) -> None:
        self.db: Database = db

    def save(self, data: str) -> None:
        self.db.storage.append(data)


class InMemoryRepository:
    def __init__(self) -> None:
        self.storage: list[str] = []

    def save(self, data: str) -> None:
        self.storage.append(data)


class CircularA:
    def __init__(self, b: CircularB, /) -> None:
        self.b: CircularB = b


class CircularB:
    def __init__(self, a: CircularA, /) -> None:
        self.a: CircularA = a


class OptionalDependencyService:
    def __init__(self, cache: Cache | None = None) -> None:
        self.cache: Cache | None = cache


def create_database(config: Config) -> Database:
    return Database(config)


def create_async_service(config: Config) -> UserService:
    db: Database = Database(config)
    cache: Cache = Cache()
    return UserService(db, cache, config)
