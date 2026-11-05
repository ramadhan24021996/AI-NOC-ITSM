"""
Domain Exceptions for Enterprise AI Operations Platform
"""

class DomainException(Exception):
    """Base exception for all domain errors."""
    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code

class RAGRetrievalException(DomainException):
    """Exception raised during RAG knowledge retrieval errors."""
    def __init__(self, message: str):
        super().__init__(message, code="RAG_RETRIEVAL_ERROR")

class ToolExecutionException(DomainException):
    """Exception raised during tool execution errors."""
    def __init__(self, message: str):
        super().__init__(message, code="TOOL_EXECUTION_ERROR")

class InsufficientEvidenceException(DomainException):
    """Exception raised when evidence confidence score is below threshold (< 0.70)."""
    def __init__(self, message: str = "Evidence confidence score insufficient (< 0.70)."):
        super().__init__(message, code="INSUFFICIENT_EVIDENCE")

class UnauthorizedActionException(DomainException):
    """Exception raised when action is forbidden by RBAC capability matrix."""
    def __init__(self, message: str = "Action unauthorized by RBAC capability matrix."):
        super().__init__(message, code="UNAUTHORIZED_ACTION")
