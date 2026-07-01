from collections.abc import Callable
from threading import Lock
from typing import Any, TypeVar

from app.core.exceptions import DependencyError

T = TypeVar("T")


class Container:
    """Thread-safe Dependency Injection (DI) Container for resolving services and repositories."""

    _instance: "Container | None" = None
    _global_lock = Lock()

    def __new__(cls, *args: Any, **kwargs: Any) -> "Container":
        """Ensures that the DI Container remains a singleton across the application lifecycle."""
        with cls._global_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self) -> None:
        # Avoid overriding registrations if container is re-instantiated
        if not hasattr(self, "_initialized"):
            self._services: dict[type[Any], Any] = {}
            self._factories: dict[type[Any], Callable[[], Any]] = {}
            self._lock = Lock()
            self._initialized = True

    def register_singleton(self, interface_cls: type[Any], instance: Any) -> None:
        """Registers a concrete singleton instance for a given interface type."""
        with self._lock:
            self._services[interface_cls] = instance

    def register_factory(self, interface_cls: type[Any], factory_func: Callable[[], Any]) -> None:
        """Registers a dynamic factory function for a given interface type."""
        with self._lock:
            self._factories[interface_cls] = factory_func

    def resolve(self, interface_cls: type[T]) -> T:
        """Resolves and returns the registered implementation for the requested interface type."""
        with self._lock:
            # Check for singleton match
            if interface_cls in self._services:
                instance = self._services[interface_cls]
                if not isinstance(instance, interface_cls):
                    raise DependencyError(
                        f"Registered singleton instance is not a subclass of {interface_cls.__name__}."
                    )
                return instance

            # Check for factory match
            if interface_cls in self._factories:
                instance = self._factories[interface_cls]()
                if not isinstance(instance, interface_cls):
                    raise DependencyError(
                        f"Factory produced an instance that is not a subclass of {interface_cls.__name__}."
                    )
                return instance

            # Raise error if no match is registered
            raise DependencyError(
                f"Dependency resolution failed: type '{interface_cls.__name__}' is not registered."
            )

    def clear(self) -> None:
        """Clears all registrations in the container. Primarily used for unit testing."""
        with self._lock:
            self._services.clear()
            self._factories.clear()

    @classmethod
    def get_instance(cls) -> "Container":
        """Convenience method to access the global container instance."""
        return cls()
