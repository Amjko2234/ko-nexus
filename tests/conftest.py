import pytest

from ko_nexus import Container

from ._classes import Cache, Config, Database


@pytest.fixture
def container() -> Container:
    return Container()


@pytest.fixture
def configured_container() -> Container:
    container: Container = Container()
    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")
    container.register(Cache, lifetime="singleton")
    return container
