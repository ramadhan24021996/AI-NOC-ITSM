"""
SERVER.repositories - Unit of Work Pattern
Abstract Unit of Work interface for managing database transactions and boundaries.
"""
from abc import ABC, abstractmethod

class UnitOfWork(ABC):
    """Abstract Unit of Work transaction boundary interface."""
    def __enter__(self) -> 'UnitOfWork':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    @abstractmethod
    def commit(self) -> None:
        pass

    @abstractmethod
    def rollback(self) -> None:
        pass
