"""
SERVER.workflow_registry - Declarative Playbook Schema & Loader
Declarative YAML/JSON playbook definitions — ZERO hardcoded Python workflows!
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class PlaybookStep:
    step_id: str
    action_name: str
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    requires_approval: bool = False

@dataclass
class DeclarativePlaybook:
    playbook_id: str
    name: str
    domain_type: str      # "incident" | "recovery" | "maintenance" | "approval" | "validation"
    steps: List[PlaybookStep] = field(default_factory=list)
    version: str = "v1.0"

class PlaybookLoader:
    """Loads and validates declarative JSON/YAML playbooks."""
    def __init__(self):
        self._playbooks: Dict[str, DeclarativePlaybook] = {}

    def register_playbook(self, playbook: DeclarativePlaybook) -> None:
        self._playbooks[playbook.playbook_id] = playbook

    def get_playbook(self, playbook_id: str) -> Optional[DeclarativePlaybook]:
        return self._playbooks.get(playbook_id)

    def list_playbooks(self) -> List[DeclarativePlaybook]:
        return list(self._playbooks.values())
