from ko_nexus import Container

from ._classes import (
    Cache,
    Config,
    Database,
    InMemoryRepository,
    IRepository,
    SQLRepository,
)


def test_multi_tenant_pattern() -> None:
    """Test multi-tenant pattern with named registrations per tenant."""

    container: Container = Container()

    # Shared infrastructure (default)
    container.register(Config, lifetime="singleton")

    # Tenant-specific databases
    def create_tenant_a_db() -> Database:
        db: Database = Database(container.resolve(Config))
        db.storage.append("tenant_a_data")
        return db

    def create_tenant_b_db() -> Database:
        db: Database = Database(container.resolve(Config))
        db.storage.append("tenant_b_data")
        return db

    container.register_factory(
        Database, create_tenant_a_db, name="tenant_a", lifetime="singleton"
    )
    container.register_factory(
        Database, create_tenant_b_db, name="tenant_b", lifetime="singleton"
    )

    # Tenant-specific repositories
    class TenantRepository:
        def __init__(self, db: Database, cache: Cache) -> None:
            self.db: Database = db
            self.cache: Cache = cache

    container.register(Cache, lifetime="singleton")  # Shared cache

    container.register_factory(
        TenantRepository,
        factory=lambda: TenantRepository(
            db=container.resolve(Database, name="tenant_a"),
            cache=container.resolve(Cache),
        ),
        name="tenant_a",
        lifetime="scoped",
    )

    container.register_factory(
        TenantRepository,
        factory=lambda: TenantRepository(
            db=container.resolve(Database, name="tenant_b"),
            cache=container.resolve(Cache),
        ),
        name="tenant_b",
        lifetime="scoped",
    )

    # Resolve tenant-specific repos
    repo_a: object = container.resolve(TenantRepository, name="tenant_a")
    repo_b: object = container.resolve(TenantRepository, name="tenant_b")

    assert isinstance(repo_a, TenantRepository)
    assert isinstance(repo_b, TenantRepository)
    assert repo_a.db is not repo_b.db
    assert repo_a.cache is repo_b.cache  # Shared cache
    assert "tenant_a_data" in repo_a.db.storage
    assert "tenant_b_data" in repo_b.db.storage


def test_environment_specific_configuration() -> None:
    """Test environment-specific services (dev/staging/prod)."""

    container: Container = Container()

    # Environment-specific configs
    dev_config: Config = Config()
    dev_config.value = "dev_settings"

    prod_config: Config = Config()
    prod_config.value = "prod_settings"

    container.register_instance(Config, dev_config, name="dev")
    container.register_instance(Config, prod_config, name="prod")

    # Environment-specific databases
    container.register_factory(
        Database,
        factory=lambda: Database(container.resolve(Config, name="dev")),
        name="dev",
        lifetime="singleton",
    )

    container.register_factory(
        Database,
        factory=lambda: Database(container.resolve(Config, name="prod")),
        name="prod",
        lifetime="singleton",
    )

    dev_db: object = container.resolve(Database, name="dev")
    prod_db: object = container.resolve(Database, name="prod")

    assert dev_db.config.value == "dev_settings"
    assert prod_db.config.value == "prod_settings"


def test_caching_strategy_pattern() -> None:
    """Test different caching strategies for different use cases."""

    container: Container = Container()

    # Default cache (auto-wired)
    container.register(Cache, lifetime="singleton")

    # Named caches for specific purposes
    def create_session_cache() -> Cache:
        cache: Cache = Cache()
        cache.data["type"] = "session"
        return cache

    def create_query_cache() -> Cache:
        cache: Cache = Cache()
        cache.data["type"] = "query"
        return cache

    container.register_factory(
        Cache, create_session_cache, name="session", lifetime="singleton"
    )
    container.register_factory(
        Cache, create_query_cache, name="query", lifetime="singleton"
    )

    class SessionManager:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    class QueryOptimizer:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    # Manually wire with specific caches
    container.register_factory(
        SessionManager,
        factory=lambda: SessionManager(container.resolve(Cache, name="session")),
        lifetime="singleton",
    )

    container.register_factory(
        QueryOptimizer,
        factory=lambda: QueryOptimizer(container.resolve(Cache, name="query")),
        lifetime="singleton",
    )

    session_mgr: object = container.resolve(SessionManager)
    query_opt: object = container.resolve(QueryOptimizer)

    assert session_mgr.cache.data["type"] == "session"
    assert query_opt.cache.data["type"] == "query"


def test_repository_pattern_with_multiple_implementations() -> None:
    """Test repository pattern with different storage backends."""

    container: Container = Container()

    container.register(Config, lifetime="singleton")
    container.register(Database, lifetime="singleton")

    # Default repository for auto-wiring
    container.register(IRepository, SQLRepository, lifetime="singleton")

    # Alternative implementations
    container.register(
        IRepository, InMemoryRepository, name="inmemory", lifetime="singleton"
    )
    container.register(IRepository, SQLRepository, name="sql", lifetime="singleton")

    class UserService:
        def __init__(self, repo: IRepository) -> None:
            self.repo: IRepository = repo

    # Auto-wired service uses default
    container.register(UserService, lifetime="transient")
    auto_service: object = container.resolve(UserService)

    # Manually wired service uses specific implementation
    container.register_factory(
        UserService,
        factory=lambda: UserService(container.resolve(IRepository, name="inmemory")),
        name="with_inmemory",
        lifetime="transient",
    )

    manual_service: object = container.resolve(UserService, name="with_inmemory")

    assert isinstance(auto_service, UserService)
    assert isinstance(manual_service, UserService)
    assert isinstance(auto_service.repo, SQLRepository)
    assert isinstance(manual_service.repo, InMemoryRepository)


def test_feature_flags_pattern() -> None:
    """Test feature flags controlling which implementation to use."""

    container: Container = Container()

    # Feature flag config
    class FeatureConfig:
        def __init__(self) -> None:
            self.use_new_cache: bool = False

    feature_config: FeatureConfig = FeatureConfig()
    container.register_instance(FeatureConfig, feature_config)

    # Register both old and new implementations
    container.register(Cache, name="old", lifetime="singleton")

    def create_new_cache() -> Cache:
        cache: Cache = Cache()
        cache.data["version"] = "new"
        return cache

    container.register_factory(
        Cache, create_new_cache, name="new", lifetime="singleton"
    )

    # Service that dynamically selects implementation
    class CacheService:
        def __init__(self, cache: Cache) -> None:
            self.cache: Cache = cache

    def create_cache_service() -> CacheService:
        fc: FeatureConfig = container.resolve(FeatureConfig)
        cache_name: str = "new" if fc.use_new_cache else "old"
        cache: Cache = container.resolve(Cache, name=cache_name)
        return CacheService(cache)

    container.register_factory(CacheService, create_cache_service, lifetime="transient")

    # Test with old implementation
    service1: object = container.resolve(CacheService)
    assert "version" not in service1.cache.data

    # Toggle feature flag
    feature_config.use_new_cache = True

    # Test with new implementation
    service2: object = container.resolve(CacheService)
    assert service2.cache.data.get("version") == "new"


def test_composition_root_with_named_registrations() -> None:
    """Test realistic composition root pattern with named registrations."""

    # Services using defaults (auto-wired)
    class ProductionService:
        def __init__(self, repo: IRepository, cache: Cache) -> None:
            self.repo: IRepository = repo
            self.cache: Cache = cache

    # Services using named dependencies (manually wired)
    class TestService:
        def __init__(self, repo: IRepository) -> None:
            self.repo: IRepository = repo

    def create_container() -> Container:
        container: Container = Container()

        # Core infrastructure (defaults for auto-wiring)
        container.register(Config, lifetime="singleton")
        container.register(Database, lifetime="singleton")
        container.register(Cache, lifetime="singleton")

        # Named alternatives for specific use cases
        container.register(
            IRepository,
            implementation=SQLRepository,
            lifetime="singleton",
        )  # Default

        container.register(
            IRepository,
            implementation=InMemoryRepository,
            name="testing",
            lifetime="singleton",
        )

        container.register(ProductionService, lifetime="scoped")

        container.register_factory(
            TestService,
            factory=lambda: TestService(
                repo=container.resolve(IRepository, name="testing")
            ),
            lifetime="scoped",
        )

        container.validate()
        return container

    container: Container = create_container()

    prod_service: object = container.resolve(ProductionService)
    test_service: object = container.resolve(TestService)

    assert isinstance(prod_service.repo, SQLRepository)
    assert isinstance(test_service.repo, InMemoryRepository)
