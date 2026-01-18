# Ko-Nexus

A lightweight, auto-wiring dependency injection container for Python with type-hint-based resolution and lifecycle management.

---

## Table of Contents

1. [What is Ko-Nexus?](#what-is-ko-nexus)
2. [Why Ko-Nexus?](#why)
3. [Features](#features)
4. [Installation](#installation)
5. [Quick Start](#quick-start)
    - [1. Define Your Services](#1-define-your-services)
    - [2. Configure the Container](#2-configure-the-container)
    - [3. Use the Container](#3-use-the-container)
6. [Core Concepts](#core-concepts)
    - [Auto-Wiring](#auto-wiring)
    - [Lifetime Strategies](#lifetime-strategies)
    - [Interface Binding](#interface-binding)
    - [Named Registrations](#named-registrations)
    - [Optional Dependencies](#optional-dependencies)
    - [Manual Wiring](#manual-wiring)
    - [Resource Lifecycle](#resource-lifecycle)
7. [Advanced Features](#advanced-features)
    - [Validation](#validation)
    - [Auto-Registration](#auto-registration)
    - [Asynchronous Resolution](#asynchronous-resolution)
    - [Complex Named Registrations](#named-registrations-for-complex-scenarios)
8. [Type Safety](#type-safety)
9. [Real-World Example](#real-world-example)
10. [Error Handling](#error-handling)
11. [Testing](#testing)
12. [Philosophy](#philosophy)
13. [For Contributors](#for-contributors)
    - [Development setup](#development-setup)
    - [Running Tests](#running-tests)
    - [Code Style](#code-style)
14. [License](#license)

---

## What is Ko-Nexus?

Ko-Nexus is a minimal dependency injection (DI) container I built for my personal projects. It automatically wires dependencies based on type hints, which eliminates manual dependency passing while maintaining strict type safety.

## Why?

I needed a DI container that:

- **Auto-wires dependencies** from type hints
- Works seamlessly with static type checkers (like pyright/mypy/basedpyright)
- Supports multiple **lifetime strategies** (singleton, transient, scoped)
- Handles **interface-to-implementation binding**
- Provides **automatic resource lifecycle management**
- Scales to large codebases with complex dependency graphs
- Does not require decorators for injection
- **Remains Pythonic** but type-safe

## Features

- ✅ **Auto-Wiring** - resolves dependencies automatically via type hints
- ✅ **Lifetime Management** - singleton, transient, and scoped lifetimes
- ✅ **Async Support** - asynchronous factories and resolutions
- ✅ **Interface Binding** - map `Protocol`/`ABC` to implementations
- ✅ **Named Registrations** - register multiple implementations of same interface within names
- ✅ **Circular Dependency Detection** - catches cycles at resolution time
- ✅ **Resource Lifecycle**  - automatic shutdown via context managers
- ✅ **Optional Dependencies** - handles `Type | None`, `Optional[None]`, or `Union[Type, None]` gracefully
- ✅ **Validation** - startup validation to catch configuration error early
- ✅ **Auto-Discovery** - scan modules/packages for automatic registration (optional)
- ✅ **Zero External Dependencies** - pure Python implementation
- ✅ **Type-Safe** - explicitly and strictly typed
- ✅ **Python 3.10+** - leverages modern Python features

---

## Installation

Do not forget to change the placeholder `<tag>` with your desired release version:

```bash
pip install git+https://github.com/Amjko2234/ko-nexus.git@<tag>
```

### From Source

```bash
git clone https://github.com/Amjko2234/ko-nexus.git
cd ko-log
pip install -e .
```

### Requirements

- Python >= 3.14

---

## Quick Start

### 1. Define Your Services

```py
from typing import Protocol

# Domain interfaces
class ICache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...

# Infrastructure implementations
class RedisCache:
    def __init__(self, config: Config):
        self.config = config
    
    def get(self, key: str) -> str | None:
        # Redis implementation
        pass
    
    def set(self, key: str, value: str) -> None:
        # Redis implementation
        pass

# Application services
class UserService:
    def __init__(self, cache: ICache, db: DatabasePool):
        self.cache = cache  # Will be auto-wired
        self.db = db        # Will be auto-wired
    
    async def get_user(self, user_id: str) -> User:
        cached = self.cache.get(user_id)
        if cached:
            return User.from_json(cached)
        
        user = await self.db.fetch_user(user_id)
        self.cache.set(user_id, user.to_json())
        return user
```

### 2. Configure the Container

```py
from ko_nexus import Container, Lifetime

def create_container() -> Container:
    container = Container()
    
    # Register concrete types
    container.register(Config, lifetime="singleton")
    container.register(DatabasePool, lifetime="singleton")
    
    # Register interface bindings
    container.register(  # Uses default registration
        ICache, implementation=RedisCache, lifetime="singleton"
    )
    
    # Register implementations with names
    container.register(  # Does not use default registration
        ICache, implementation=InMemoryCache, name="in_memory", lifetime="singleton"
    )
    
    # Register services
    container.register(UserService, lifetime="scoped")
    
    # Validate configuration
    container.validate()
    
    return container
```

### 3. Use the Container

```py
import asyncio

async def main():
    async with create_container() as container:
        # Resolve services - dependencies auto-wired!
        user_service = container.resolve(UserService)
        
        # Use the service
        user = await user_service.get_user("123")
        print(f"User: {user.name}")
        
        # Manual resolution with name
        inmem_cache = container.resolve(ICache, name="in_memory")
    
        # Resources automatically cleaned up here

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Core Concepts

### Auto-Wiring

Ko-Nexus inspects constructor type hints and automatically resolves dependencies:

```py
class MessageHandler:
    def __init__(self, llm: LLMClient, memory: IMemoryStore, logger: Logger):
        # Container automatically resolves LLMClient, IMemoryStore, Logger
        self.llm = llm
        self.memory = memory
        self.logger = logger

# In composition root:
container.register(MessageHandler, lifetime="transient")

# Resolve - all dependencies auto-wired!
handler = container.resolve(MessageHandler)
```

### Lifetime Strategies

**Singleton** - One instance per container (cached after first resolution)

```py
container.register(DatabasePool, lifetime="singleton")
db1 = container.resolve(DatabasePool)
db2 = container.resolve(DatabasePool)
assert db1 is db2  # Same instance
```

**Transient** - New instance every resolution

```py
container.register(RequestHandler, lifetime="transient")
handler1 = container.resolve(RequestHandler)
handler2 = container.resolve(RequestHandler)
assert handler1 is not handler2  # Different instances
```

**Scoped** - One instance per scope (cleared with `container.clear_scoped()`)

```python
container.register(UserService, lifetime="scoped")
service1 = container.resolve(UserService)
service2 = container.resolve(UserService)
assert service1 is service2  # Same instance

container.clear_scoped()
service3 = container.resolve(UserService)
assert service3 is not service1  # New instance after scope clear
```

### Interface Binding

Map abstract interfaces to concrete implementations:

```py
from typing import Protocol

class IRepository(Protocol):
    def save(self, data: str) -> None: ...

class PostgresRepository:
    def __init__(self, db: DatabasePool):
        self.db = db
    
    def save(self, data: str) -> None:
        # Implementation
        pass

# Bind interface to implementation
container.register(IRepository, implementation=PostgresRepository, lifetime="scoped")

# Services depend on interface, get implementation
class UserService:
    def __init__(self, repo: IRepository):  # IRepository, not PostgresRepository
        self.repo = repo
```

### Named Registrations

Register multiple implementations of the same interface using names for manual resolution:

```py
from typing import Protocol

class ICache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...

class RedisCache:
    def get(self, key: str) -> str | None:
        # Redis implementation
        pass
    
    def set(self, key: str, value: str) -> None:
        # Redis implementation
        pass

class InMemoryCache:
    def __init__(self):
        self.data: dict[str, str] = {}
    
    def get(self, key: str) -> str | None:
        return self.data.get(key)
    
    def set(self, key: str, value: str) -> None:
        self.data[key] = value

# Register default for auto-wiring
container.register(ICache, implementation=RedisCache, lifetime="singleton")

# Register named variant for manual resolution
container.register(
    ICache, implementation=InMemoryCache, name="in_memory", lifetime="singleton"
)

# Auto-wiring uses default
class UserService:
    def __init__(self, cache: ICache):  # Gets `RedisCache`
        self.cache = cache

service = container.resolve(UserService)
assert isinstance(service.cache, RedisCache)

# Manual resolution uses name
inmem_cache = container.resolve(ICache, name="in_memory")
assert isinstance(inmem_cache, InMemoryCache)
```

**Important**: Auto-wiring always uses default registrations (non-named). As, named registrations are for explicit manual resolution only.

**Uses cases**:

- Multiple tenants with different database connections
- Environment-specific configurations (dev/staging/prod)
- Feature flags controlling implementation section
- Different caching strategies for different purposes

```py
# Multi-tenant example
container.register(Database, name="tenant_a", lifetime="singleton")
container.register(Database, name="tenant_b", lifetime="singleton")

# Manually wire tenant-specific services
container.register_factory(
    TenantService,
    factory=lambda: TenantService(
        db=container.resolve(Database, name="tenant_a")
    ),
    name="tenant_a",
    lifetime="scoped",
)
```

### Optional Dependencies

Handles `Type | None`, `Optional[None]`, or `Union[Type, None]` gracefully:

```py
class Service:
    def __init__(self, cache: ICache | None = None):
        self.cache = cache

# If ICache is registered, it's injected
# If not registered, cache = None (uses default)
```

### Manual Wiring

For special cases, use factories:

```py
# Pre-resolve dependencies for custom initialization
config = container.resolve(Config)
db = container.resolve(DatabasePool)

container.register_factory(
    ComplexService,
    factory=lambda: ComplexService(
        db,
        api_key=config.api_key,
        timeout=30
    ),
    lifetime="singleton",
)
```

### Resource Lifecycle

Container manages startup/shutdown automatically:

```py
class DatabasePool:
    def __init__(self, config: Config):
        self.connection = None
    
    async def connect(self):
        self.connection = await create_connection()
    
    async def close(self):
        if self.connection:
            await self.connection.close()

# Use context manager for automatic cleanup
async with create_container() as container:
    # All singletons initialized
    db = container.resolve(DatabasePool)
    # Use db...
    # DatabasePool.close() called automatically
```

---

## Advanced Features

### Validation

Catch configuration errors at startup:

```py
def create_container() -> Container:
    container = Container()
    
    # Register services...
    
    # Validate all dependencies are resolvable
    container.validate()  # Raises `DiValidationError` if issues found
    
    return container
```

### Auto-Registration

Scan modules/packages for automatic registration:

```py
# Register all classes in a module
container.auto_register_module(
    'myapp.infrastructure',
    lifetime="singleton",
    predicate=lambda cls: cls.__name__.endswith('Client'),
)

# Register entire package recursively
container.auto_register_package(
    'myapp.domain.services',
    lifetime="scoped",
    exclude_abstract=True,
)
```

### Asynchronous Resolution

Support for async factories:

```py
async def create_llm_client(config: Config) -> LLMClient:
    client = LLMClient(config.api_key)
    await client.initialize()
    return client

container.register_factory(LLMClient, implementation=create_llm_client, lifetime="singleton")

# Resolve asynchronously
llm = await container.async_resolve(LLMClient)
```

### Named Registrations for Complex Scenarios

Use named registrations when you need multiple implementations of the same interface:

```py
# Environment-specific configurations
dev_config = Config(env="dev", debug=True)
prod_config = Config(env="prod", debug=False)

container.register_instance(Config, implementation=dev_config, name="dev")
container.register_instance(Config, implementation=prod_config, name="prod")

# Resolve based on environment
current_env = os.getenv("APP_ENV", "dev")
config = container.resolve(Config, name=current_env)

# Feature flags
container.register(IPaymentProcessor, StripeProcessor, name="stripe")
container.register(IPaymentProcessor, PayPalProcessor, name="paypal")

def create_payment_service() -> PaymentService:
    processor_name = feature_flags.get("payment_provider", "stripe")
    processor = container.resolve(IPaymentProcessor, name=processor_name)
    return PaymentService(processor)

container.register_factory(PaymentService, create_payment_service)
```

---

## Type Safety

Ko-Nexus is designed for strict static type checking:

```py
from ko_nexus import Container

container = Container()
container.register(Config, lifetime="singleton")

# Type-safe resolution
config: object = container.resolve(Config)  
assert isinstance(config, Config)  # ✅ Type: `Config`

# Generic support
T = TypeVar('T')
def get_service(container: Container, service_type: type[T]) -> T:
    return container.resolve(service_type)

user_service: object = get_service(container, UserService)  
assert isinstance(user_service, UserService)  # ✅ Type: `UserService`
```

---

## Real-World Example

```py
# composition_root.py
from ko_nexus import Container, Lifetime

def create_container() -> Container:
    container = Container()
    
    # Configuration
    config = Config.load_from_env()
    container.register_instance(Config, implementation=config)
    
    # Infrastructure (concrete types)
    container.register(OpenAIClient, lifetime="singleton")
    container.register(DatabasePool, lifetime="singleton")
    
    # Repositories (interface bindings)
    container.register(IUserRepository, implementation=PostgresUserRepository, lifetime="scoped")
    container.register(IMemoryStore, implementation=VectorMemoryStore, lifetime="singleton")
    
    # Domain services (auto-wired)
    container.register(UserService, lifetime="scoped")
    container.register(MessageOrchestrator, lifetime="scoped")
    
    # Application layer
    container.register(ChatApplication, lifetime="singleton")

    # Named registrations for different environments
    container.register(ICache, RedisCache, name="redis", lifetime="singleton")
    container.register(ICache, InMemoryCache, name="in_memory", lifetime="singleton")
    
    # Conditionally select implementation
    cache_type = config.cache_type  # "redis" or "in_memory"
    if cache_type == "redis":
        container.register(IMemoryStore, implementation=RedisMemoryStore, lifetime="singleton")
    else:
        container.register(IMemoryStore, implementation=InMemoryStore, lifetime="singleton")
    
    container.validate()
    return container

# main.py
import asyncio

async def main():
    async with create_container() as container:
        app = container.resolve(ChatApplication)
        try:
            await app.run()
        finally:
            await app.shutdown()
            
    # Or
    # container: Container = create_container()
    # app = container.resolve(ChatApplication)
    # try:
    #     await app.run()
    # finally:
    #     await app.shutdown()
    #     # Explicitly specify if not using context manager
    #     await container.async_shutdown_resources()

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Error Handling

Ko-Nexus provides clear and structured error messages:

```py
from ko_nexus import (
    DiAutoRegistrationError,
    DiCallableError,
    DiCircularDependencyError,
    DiResolutionError,
    DiValidationError,
)

# DiAutoRegistrationError - problem with auto registering multiple modules
# Error:
# >> REGISTRY::Container::IMPORT::ERROR

# DiCallableError - factory/cleanup functon raises
await container.async_shutdown_resources()
# Error: Errors raised while shutting down resources:
#     - Error 1: An awaitable resource cleanup for instance `<module.Class at 0x...>` can not be called with `shutdown_resources`. Skipped it
#     - Error 2: An exception occured when cleaning up resource for instance `<module.Class at 0x...>`: Invalid configuration value
# >> CALLABLE::Container::UNEXPECTED::ERROR

# DiCircularDependencyError - circular dependencies
container.resolve(ServiceA)
# Error: Circular dependency detected: `ServiceA -> ServiceB -> ServiceA`
# >> DEPENDENCY::Container::CIRCULAR::ERROR

# DiResolutionError - type not registered
container.resolve(UnregisteredType)
# Error: Interface type `UnregisteredType` is not registered
# >> DEPENDENCY::Container::MISSING:ERROR

# DiValidationError - missing dependencies (only checks defaults)
container.register(Config, lifetime="singleton")
container.register(UserService, lifetime="transient")
container.register(Cache, name="special", lifetime="singleton")  # Named only, no default
# Missing Database and default Cache registrations

container.validate()
# Error: Errors found during container validation:
#     - Error 1: UserService: Cannot resolve parameter `db` of type `Database` (no default registration)
#     - Error 2: UserService: Cannot resolve parameter `cache` of type `Cache` (no default registration)
# >> DEPENDENCY::Container::INVALID::ERROR

```

**Error code format:**

```txt
LAYER::Service::CATEGORY::SEVERITY[::RECOVERABLE]
```

---

## Testing

Mock dependencies easily:

```py
def test_use_service() -> None:
    container = Container()
    
    # Register mocks
    mock_cache = MockCache()
    container.register(CacheInterface, implementation=mock_cache)
    
    mock_db = MockDb()
    container.register(DatabaseInterface, implementation=mock_db)
    
    # Service gets mocked dependencies
    service = container.resolve(UserService)
    
    assert service.cache is mock_cache
    assert service.db is mock_db
```

Easily test named registrations:

```py
def test_service_with_multiple_cache_implementations() -> None:
    container = Container()
    
    # Register multiple cache implementations
    container.register(ICache, MockRedisCache, lifetime="singleton")
    container.register(ICache, MockInMemoryCache, name="inmemory", lifetime="singleton")
    
    # Service gets default
    service = container.resolve(UserService)
    assert isinstance(service.cache, MockRedisCache)
    
    # Manually resolve named variant
    inmem = container.resolve(ICache, name="inmemory")
    assert isinstance(inmem, MockInMemoryCache)
```

---

## Philosophy

This is a personal tool built for practical use, not a framework. It follows these simple principles:

1. **Explicit Composition Root** - all wiring in one place, not scattered across codebases
2. **Type Safety First** - designed for static analysis and IDE support
3. **Auto-Wiring by Default** - still flexible for manual wiring only when needed
4. **Pythonic Patterns** - context managers, protocols, type hints
5. **Minimal Magic** - clear, inspectable behavior

---

## For Contributors

While this is primarily a personal project, I'm open to:

- Bug reports with reproducible examples
- Documentation improvements
- Performance optimizations
- Feature requests (with clear use cases)

*If you find it useful, that's reward enough.* ✨

### Development Setup

```bash
git clone https://github.com/Amjko2234/ko-nexus.git
cd ko-log
python -m venv .venv
source .venv/bin/active # or .venv/Scripts/Activate on Windows

pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -vv
```

### Code Style

- Formatter: `black`, `isort`
- Linter: `ruff`
- Type Checker: `basedpyright`

---

## License

MIT License. See [LICENSE](LICENSE.rst) for details.

---

*Built for practical use, shared in the case it helps others build better software.* 🙂
