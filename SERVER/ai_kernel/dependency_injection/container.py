"""
AI Kernel - Dependency Injection Container
Provides clean dependency registration and resolution without global state pollution.
"""
from typing import Dict, Any, Type, TypeVar, Callable, Optional

T = TypeVar("T")

class DIContainer:
    """Foundational dependency injection container."""
    def __init__(self):
        self._singletons: Dict[Type[Any], Any] = {}
        self._factories: Dict[Type[Any], Callable[['DIContainer'], Any]] = {}

    def register_singleton(self, interface_type: Type[T], instance: T) -> None:
        self._singletons[interface_type] = instance

    def register_factory(self, interface_type: Type[T], factory: Callable[['DIContainer'], T]) -> None:
        self._factories[interface_type] = factory

    def resolve(self, interface_type: Type[T]) -> T:
        if interface_type in self._singletons:
            return self._singletons[interface_type]
        if interface_type in self._factories:
            return self._factories[interface_type](self)
        raise KeyError(f"Service for type {interface_type} not registered in DI container.")
