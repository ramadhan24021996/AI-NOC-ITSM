"""
AI Kernel - Service Locator
Provides global service discovery registry.
"""
from typing import Dict, Any, Type, Optional

class ServiceLocator:
    """Foundational Service Locator registry."""
    _services: Dict[Type[Any], Any] = {}

    @classmethod
    def register(cls, service_type: Type[Any], instance: Any) -> None:
        cls._services[service_type] = instance

    @classmethod
    def get(cls, service_type: Type[Any]) -> Optional[Any]:
        return cls._services.get(service_type)

    @classmethod
    def clear(cls) -> None:
        cls._services.clear()
