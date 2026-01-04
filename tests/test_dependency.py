# pyright: reportPrivateUsage=false

import pytest

from ko_nexus import Dependency, DiDependencyError

from ._class import ExampleDependency


def test_dependency_initialization() -> None:
    """Test basic dependency initialization."""

    dep: Dependency[str] = Dependency[str]()

    assert dep.name is None
    assert not dep.is_provided()
    assert str(dep._value) == "<UNSET>"

    # Test with name
    named_dep: Dependency[str] = Dependency[str](name="my_dependency")
    assert named_dep.name == "my_dependency"


def test_dependency_type_hinting() -> None:
    """Test that type hints work correctly with `Dependency`."""

    # Basic type
    str_dep: Dependency[str] = Dependency[str]()
    str_dep.provide(value="str_value")
    assert isinstance(str_dep.resolve(), str)

    int_dep: Dependency[int] = Dependency[int]()
    int_dep.provide(value=2234)
    assert isinstance(int_dep.resolve(), int)

    # Complex type
    obj_dep: Dependency[ExampleDependency] = Dependency[ExampleDependency]()
    obj: ExampleDependency = ExampleDependency(value="test_value")
    obj_dep.provide(value=obj)
    assert isinstance(obj_dep.resolve(), ExampleDependency)


def test_dependency_provide() -> None:
    """Test providing values to dependency."""

    dep: Dependency[str] = Dependency[str]()

    dep.provide(value="test_value")
    assert dep.is_provided()
    assert dep._value == "test_value"

    # New value should overwrite old value
    dep.provide(value="new_value")
    assert dep.is_provided()
    assert dep._value == "new_value"


def test_dependency_resolve() -> None:
    """Test resolving dependency will work if dependency value is provided beforehand."""

    dep: Dependency[ExampleDependency] = Dependency[ExampleDependency](name="example")

    example: ExampleDependency = ExampleDependency(value="test_value")
    dep.provide(value=example)

    # Resolving should return provided value
    assert isinstance(dep.resolve(), ExampleDependency)
    resolved: ExampleDependency = dep.resolve()
    assert resolved is example
    assert resolved.value == "test_value"
    assert resolved.do_something() == "Did something with `test_value`"


def test_dependency_callable_interface() -> None:
    dep: Dependency[str] = Dependency[str]()
    dep.provide(value="test_value")
    assert dep() == "test_value"


def test_unprovided_dependency_resolve_raises() -> None:
    """
    Test dependency will raise an error when an attempt to resolve is made before
    dependency value has been provided.
    """

    named_dep: Dependency[str] = Dependency[str](name="named_dependency")
    with pytest.raises(
        DiDependencyError, match="Dependency `named_dependency` has not been provided"
    ):
        _ = named_dep.resolve()

    unnamed_dep: Dependency[str] = Dependency[str]()
    with pytest.raises(
        DiDependencyError, match="Dependency `unnamed` has not been provided"
    ):
        _ = unnamed_dep.resolve()


def test_dependency_resolve_after_explicit_none_provided() -> None:
    """Test dependencies can be provided with explicit `None` values."""

    from types import NoneType
    from typing import Any

    dep: Dependency[Any] = Dependency[Any](name="nullable_dependency")
    dep.provide(value=None)

    assert dep.is_provided()
    # Should not raise because we explicitly want `None`
    assert isinstance(dep.resolve(), NoneType)
    result: None = dep.resolve()
    assert result is None
