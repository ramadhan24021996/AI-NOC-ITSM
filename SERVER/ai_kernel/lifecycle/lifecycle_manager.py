"""
AI Kernel - Lifecycle Manager
Manages application startup, graceful degradation, and shutdown hooks.
"""
import logging
from typing import List, Callable

logger = logging.getLogger("ai_kernel.lifecycle")

class LifecycleManager:
    """Foundational lifecycle manager for service hooks."""
    def __init__(self):
        self._startup_hooks: List[Callable[[], None]] = []
        self._shutdown_hooks: List[Callable[[], None]] = []
        self._is_running: bool = False

    def register_startup_hook(self, hook: Callable[[], None]) -> None:
        self._startup_hooks.append(hook)

    def register_shutdown_hook(self, hook: Callable[[], None]) -> None:
        self._shutdown_hooks.append(hook)

    def startup(self) -> None:
        logger.info("Executing AI Kernel startup hooks...")
        for hook in self._startup_hooks:
            try:
                hook()
            except Exception as e:
                logger.error(f"Startup hook error: {e}")
        self._is_running = True

    def shutdown(self) -> None:
        logger.info("Executing AI Kernel shutdown hooks...")
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
            except Exception as e:
                logger.error(f"Shutdown hook error: {e}")
        self._is_running = False

    @property
    def is_running(self) -> bool:
        return self._is_running
