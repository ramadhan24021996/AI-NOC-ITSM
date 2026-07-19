from abc import ABC, abstractmethod

class IVersionController(ABC):
    @abstractmethod
    def check_compatibility(self, version_a: str, version_b: str) -> bool:
        raise NotImplementedError("LF-1 Framework: check_compatibility not implemented")

    @abstractmethod
    def trigger_migration_hook(self, target_version: str) -> bool:
        raise NotImplementedError("LF-1 Framework: trigger_migration_hook not implemented")

    @abstractmethod
    def generate_rollback_metadata(self, current_version: str) -> dict:
        raise NotImplementedError("LF-1 Framework: generate_rollback_metadata not implemented")
