"""
supervisor/handlers/incident_handler.py
---------------------------------------
Modular Supervisor Handlers Facade.
Re-exports clean domain handlers:
  - incident_triage.py   -> message_handler, execute_validated_llm
  - incident_learning.py -> learning_handler
  - incident_reanalyze.py-> reanalyze_handler
  - incident_retry.py    -> ai_retry_handler
"""

try:
    from .incident_triage import execute_validated_llm, message_handler
    from .incident_learning import learning_handler
    from .incident_reanalyze import reanalyze_handler
    from .incident_retry import ai_retry_handler
except ImportError:
    from supervisor.handlers.incident_triage import execute_validated_llm, message_handler
    from supervisor.handlers.incident_learning import learning_handler
    from supervisor.handlers.incident_reanalyze import reanalyze_handler
    from supervisor.handlers.incident_retry import ai_retry_handler

__all__ = [
    "execute_validated_llm",
    "message_handler",
    "learning_handler",
    "reanalyze_handler",
    "ai_retry_handler",
]
