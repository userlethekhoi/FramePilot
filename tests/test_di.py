import pytest

from app.application.di.container import Container
from app.core.exceptions import DependencyError


class DummyService:
    pass


class DummySubclass(DummyService):
    pass


class UnrelatedClass:
    pass


def test_singleton_registration_and_resolution() -> None:
    """Verifies singletons can be registered and resolved, maintaining reference equality."""
    container = Container()
    container.clear()

    service = DummyService()
    container.register_singleton(DummyService, service)

    resolved = container.resolve(DummyService)
    assert resolved is service


def test_factory_registration_and_resolution() -> None:
    """Verifies factory functions generate new instances upon resolution."""
    container = Container()
    container.clear()

    container.register_factory(DummyService, DummyService)

    resolved_1 = container.resolve(DummyService)
    resolved_2 = container.resolve(DummyService)

    assert isinstance(resolved_1, DummyService)
    assert isinstance(resolved_2, DummyService)
    assert resolved_1 is not resolved_2


def test_invalid_type_resolution_raises_error() -> None:
    """Verifies type mismatch throws clean DependencyError."""
    container = Container()
    container.clear()

    # Registering instance that is not subclasses of registration key
    container.register_singleton(DummyService, UnrelatedClass())  # type: ignore

    with pytest.raises(DependencyError):
        container.resolve(DummyService)


def test_unregistered_resolution_raises_error() -> None:
    """Verifies resolving unregistered service throws clean DependencyError."""
    container = Container()
    container.clear()

    with pytest.raises(DependencyError):
        container.resolve(DummyService)
