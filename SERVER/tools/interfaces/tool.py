"""
SERVER.tools.interfaces — Core Tool Interfaces & Data Contracts
===============================================================
Tahap 2.4 — Tool Execution Layer

Semua driver, dispatcher, policy, dan approval harus mengimplementasikan atau
menggunakan interface ini. Tidak ada driver yang boleh dipanggil langsung dari
LLM, Jarvis, atau orchestrator tanpa melewati lapisan ini.

Alur aman yang diwajibkan:
  LLM/Jarvis
      │
      ▼
  [Orchestrator]
      │
      ▼
  ToolDispatcher  ← satu-satunya entry point publik
      │
      ▼
  ApprovalManager (HITL check)
      │
      ▼
  ToolPolicyEngine (rule enforcement)
      │
      ▼
  RiskClassifier (risk scoring)
      │
      ▼
  Driver (SSH / Docker / RouterOS / REST / Sandbox)
      │
      ▼
  ToolAuditLogger (immutable audit trail)
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
from SERVER.shared.enums import ActionRiskLevel


# ── Enums ─────────────────────────────────────────────────────────────────────

class ToolStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    DENIED = "DENIED"          # Ditolak oleh policy/approval
    PENDING_APPROVAL = "PENDING_APPROVAL"
    SANDBOXED = "SANDBOXED"    # Dieksekusi dalam sandbox saja (dry-run)
    TIMED_OUT = "TIMED_OUT"

class ApprovalStatus(str, Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"    # Confidence >= 92% + risk LOW
    FORCE_HITL = "FORCE_HITL"         # Mandatory human approval

class RiskLevel(str, Enum):
    LOW = "LOW"          # Read-only, info gathering
    MEDIUM = "MEDIUM"    # Restart services, config changes
    HIGH = "HIGH"        # Delete operations, network changes
    CRITICAL = "CRITICAL"  # Irreversible destructive actions


# ── Data Contracts ─────────────────────────────────────────────────────────────

@dataclass
class ToolManifest:
    """Deklarasi metadata setiap tool/driver."""
    tool_id: str
    name: str
    description: str
    version: str
    risk_level: ActionRiskLevel
    driver_type: str = ""           # "ssh" | "docker" | "mikrotik" | "rest" | "sandbox"
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30
    requires_hitl: bool = False
    is_reversible: bool = True  # Apakah aksi dapat di-rollback


@dataclass
class ToolRequest:
    """Permintaan eksekusi tool yang masuk ke ToolDispatcher."""
    request_id: str
    tool_id: str
    params: Dict[str, Any]
    requestor_role: str         # "ai_auto" | "ai_suggested" | "operator"
    incident_id: str = ""
    severity: str = "LOW"
    confidence: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolResult:
    """Hasil eksekusi tool setelah melewati seluruh lapisan keamanan."""
    request_id: str
    tool_id: str
    status: ToolStatus
    output: str = ""
    error: str = ""
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    risk_level: RiskLevel = RiskLevel.LOW
    risk_score: int = 0
    executed_by: str = ""       # Driver name yang mengeksekusi
    duration_ms: int = 0
    is_dry_run: bool = False
    audit_id: str = ""


@dataclass
class PolicyDecision:
    """Keputusan dari ToolPolicyEngine."""
    allowed: bool
    reason: str
    requires_hitl: bool = False
    force_sandbox: bool = False  # Paksa dry-run sandbox
    policy_rule: str = ""


@dataclass
class RiskAssessment:
    """Penilaian risiko dari RiskClassifier."""
    risk_level: RiskLevel
    risk_score: int              # 0–100
    risk_reasons: List[str] = field(default_factory=list)
    requires_hitl: bool = False
    is_reversible: bool = True
    blast_radius: str = "NONE"  # "NONE" | "LOCAL" | "SERVICE" | "FLEET" | "DATACENTER"


# ── Abstract Interfaces ────────────────────────────────────────────────────────

class ToolDriver(ABC):
    """
    Abstract interface yang wajib diimplementasikan oleh setiap driver.
    Driver TIDAK BOLEH dipanggil langsung — selalu melalui ToolDispatcher.
    """
    @property
    @abstractmethod
    def driver_type(self) -> str:
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any], dry_run: bool = False) -> ToolResult:
        pass

    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        pass


class Tool(ABC):
    """Abstract interface untuk executable tools (existing, preserved for backward compat)."""
    @property
    @abstractmethod
    def manifest(self) -> ToolManifest:
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass


class ToolExecutor(ABC):
    """Abstract interface for executing registered tools safely (existing, preserved)."""
    @abstractmethod
    def run_tool(self, tool_id: str, params: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        pass


class PermissionChecker(ABC):
    """Abstract interface for evaluating tool permissions against RBAC (existing, preserved)."""
    @abstractmethod
    def check_permission(self, user_role: str, manifest: ToolManifest) -> bool:
        pass


class TimeoutManager(ABC):
    """Abstract interface for managing tool execution timeouts (existing, preserved)."""
    @abstractmethod
    def enforce_timeout(self, tool_id: str, timeout_seconds: int) -> None:
        pass
