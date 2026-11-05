"""
Enterprise Dashboard Analytics Engine Module
Integrates 6 AIOS Widgets into the existing Command Dashboard Menu:
1. Widget Status AIOS Kernel & Micro-Processes (PID, CPU %, Memory Limit, Sandbox)
2. Widget Calibrated Root Cause Confidence (Raw 95% vs Calibrated 72% ECE ⭐⭐⭐⭐⭐)
3. Widget Visual RCA Explainability Graph & Mermaid Visualizer (Color coding, edge weights, counterfactuals)
4. Panel Resource Optimization AI (VM auto-resize, Docker placement, VM migration, storage balancing)
5. Panel Knowledge Promotion Vault (/docs/SOP_VAULT/ - Draft -> Production candidates)
6. Widget AI Constitution & Immutable Audit Feed (Real-time 8-rule compliance stream).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .aios_kernel import AIOSKernel
from .aios_confidence_calibrator import AIOSConfidenceCalibrator
from .aios_explainability_graph_visualizer import AIOSExplainabilityGraphVisualizer
from .aios_resource_optimizer import AIOSResourceOptimizer
from .knowledge_promotion_pipeline import KnowledgePromotionPipeline
from .aios_constitution import AIOSConstitution


@dataclass
class DashboardWidgetPayload:
    widget_id: str
    widget_title: str
    widget_type: str
    data_payload: Dict[str, Any]
    ui_display_template: str


class EnterpriseDashboardAnalytics:
    """Generates unified real-time dashboard payloads for the existing dashboard menu."""

    def __init__(self):
        self.kernel = AIOSKernel()
        self.calibrator = AIOSConfidenceCalibrator()
        self.visualizer = AIOSExplainabilityGraphVisualizer()
        self.resource_optimizer = AIOSResourceOptimizer()
        self.promotion_pipeline = KnowledgePromotionPipeline()
        self.constitution = AIOSConstitution()

    def generate_all_dashboard_widgets(self, incident_id: str = "INC-DASH-101") -> List[DashboardWidgetPayload]:
        widgets = []

        # 1. AIOS Kernel Widget
        proc = self.kernel.spawn_agent_process("ArchitectAgent", cpu_quota_pct=25.0)
        widgets.append(DashboardWidgetPayload(
            widget_id="WIDGET-KERNEL-STATUS",
            widget_title="Widget Status AIOS Kernel & Micro-Processes",
            widget_type="METRIC_PANEL",
            data_payload={
                "active_pid": proc.process_id,
                "agent_name": proc.agent_name,
                "cpu_quota_pct": f"{proc.cpu_quota_pct}%",
                "memory_limit_mb": f"{proc.memory_limit_mb}MB",
                "process_isolation": "SANDBOXED_MICROKERNEL",
                "status": proc.status
            },
            ui_display_template="KERNEL_HEALTH_CARD"
        ))

        # 2. Calibrated Confidence Widget
        calib_res = self.calibrator.calibrate_confidence(raw_confidence=0.95)
        widgets.append(DashboardWidgetPayload(
            widget_id="WIDGET-CONFIDENCE-CALIBRATED",
            widget_title="Widget Calibrated Root Cause Confidence (ECE ⭐⭐⭐⭐⭐)",
            widget_type="GAUGE_COMPARISON",
            data_payload={
                "raw_confidence_pct": f"{calib_res.raw_confidence*100:.1f}%",
                "calibrated_confidence_pct": f"{calib_res.calibrated_confidence*100:.1f}%",
                "ece_error_pct": f"{calib_res.expected_calibration_error*100:.1f}%",
                "calibration_tier": calib_res.calibration_tier,
                "calibration_reason": calib_res.calibration_reason
            },
            ui_display_template="CONFIDENCE_ECE_GAUGE"
        ))

        # 3. Visual RCA Explainability Graph Widget
        graph_payload = self.visualizer.generate_explainability_graph(incident_id, "Gateway Router FW-01 Packet Loss")
        widgets.append(DashboardWidgetPayload(
            widget_id="WIDGET-VISUAL-RCA-GRAPH",
            widget_title="Widget Visual RCA Explainability Graph & Mermaid Visualizer",
            widget_type="GRAPH_MERMAID_PANEL",
            data_payload={
                "nodes_count": len(graph_payload.nodes),
                "edges_count": len(graph_payload.edges),
                "mermaid_diagram": graph_payload.mermaid_diagram_markdown,
                "timeline_sequence": graph_payload.timeline_sequence
            },
            ui_display_template="MERMAID_INTERACTIVE_CANVAS"
        ))

        # 4. Resource Optimization AI Panel
        res_opt = self.resource_optimizer.analyze_resource_utilization("VM-APP-SERVER-01", "VM", cpu_usage_pct=95.0, ram_usage_pct=20.0)
        widgets.append(DashboardWidgetPayload(
            widget_id="PANEL-RESOURCE-OPTIMIZATION",
            widget_title="Panel Resource Optimization AI",
            widget_type="ACTIONABLE_OPTIMIZATION_PANEL",
            data_payload={
                "asset_id": res_opt.target_asset_id,
                "anomaly": res_opt.detected_anomaly,
                "recommended_action": res_opt.recommended_action,
                "estimated_savings": f"{res_opt.estimated_savings_pct}%",
                "execution_ready": res_opt.is_automated_execution_ready
            },
            ui_display_template="RESOURCE_RESIZE_CARD"
        ))

        # 5. Knowledge Promotion Vault Panel
        widgets.append(DashboardWidgetPayload(
            widget_id="PANEL-KNOWLEDGE-PROMOTION-VAULT",
            widget_title="Panel Knowledge Promotion Vault (/docs/SOP_VAULT/)",
            widget_type="LIFECYCLE_PROGRESS_BOARD",
            data_payload={
                "vault_path": "/docs/SOP_VAULT/",
                "lifecycle_stages": ["DRAFT", "SANDBOX", "SIMULATED", "VALIDATED", "PRODUCTION"],
                "active_candidates_count": 4,
                "latest_sop_generated": f"/docs/SOP_VAULT/{incident_id}/SOP.md"
            },
            ui_display_template="KNOWLEDGE_KANBAN_BOARD"
        ))

        # 6. AI Constitution Audit Feed Widget
        const_res = self.constitution.validate_action_constitution("RestartInterface", confidence_score=0.92, has_evidence=True)
        widgets.append(DashboardWidgetPayload(
            widget_id="WIDGET-AI-CONSTITUTION-AUDIT",
            widget_title="Widget AI Constitution & Immutable Audit Feed",
            widget_type="AUDIT_STREAM_FEED",
            data_payload={
                "enforced_rules_count": len(self.constitution.rules),
                "last_action_validated": const_res.action_name,
                "compliance_status": "COMPLIANT" if const_res.permitted else "VIOLATION_BLOCKED",
                "explanation": const_res.explanation
            },
            ui_display_template="REALTIME_AUDIT_LOG"
        ))

        return widgets
