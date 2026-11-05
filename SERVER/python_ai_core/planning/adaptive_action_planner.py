"""
adaptive_action_planner.py
===========================
Failure-Aware Adaptive Action Planner Engine.
Menerapkan Prinsip Failure Adaptation:
Jika tindakan A sebelumnya gagal terverifikasi, sistem dilarang mengulang tindakan A
tanpa bukti baru. Planner secara otomatis bermutasi memilih tindakan B dari Decision Tree SOP
atau mengeskalasi insiden.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("AdaptiveActionPlanner")


class AdaptiveActionPlanner:
    """
    Perencana Tindakan Adaptif dengan Mutasi Plan Berbasis Kegagalan.
    """

    def generate_adaptive_plan(
        self,
        incident_context: Any
    ) -> Dict[str, Any]:
        """
        Menghasilkan Execution Plan adaptif berdasarkan konteks insiden dan riwayat kegagalan.
        """
        # Ekstrak daftar nama tindakan yang telah gagal
        failed_action_names = {
            f.get("action", {}).get("name", "").upper()
            for f in incident_context.failed_actions
        }

        logger.info(
            f"[AdaptivePlanner] Formulating plan for incident {incident_context.incident_id} | "
            f"Attempt Count: {incident_context.attempt_count} | Failed Actions: {failed_action_names}"
        )

        # 1. Pilih SOP Utama dari matched_sops
        selected_sop = incident_context.selected_sop
        if not selected_sop and incident_context.matched_sops:
            selected_sop = incident_context.matched_sops[0]
            incident_context.selected_sop = selected_sop

        if not selected_sop:
            logger.warning(f"[AdaptivePlanner] No matching SOP found for incident {incident_context.incident_id}")
            return {
                "plan_status": "NO_SOP_MATCHED",
                "recommended_action": None,
                "requires_escalation": True,
                "reason": "Tidak ada SOP terdaftar yang sesuai dengan konteks insiden."
            }

        decision_tree = selected_sop.get("decision_tree", {})
        telemetry = incident_context.telemetry or {}

        # 2. Evaluasi Decision Tree Step per Step
        proposed_action = None

        # Evaluasi Step 1: Check Spooler Status / Stopped
        if "step_1" in decision_tree:
            step1 = decision_tree["step_1"]
            is_spooler_stopped = telemetry.get("spooler_stopped", False) or any(
                "spooler stopped" in s.lower() for s in incident_context.symptoms
            )
            if is_spooler_stopped:
                act = step1.get("action_if_true")
                if act and isinstance(act, dict) and act.get("name", "").upper() not in failed_action_names:
                    proposed_action = act

        # Evaluasi Step 2: Check Print Queue Stuck (Jika step 1 gagal atau tidak cocok)
        if not proposed_action and "step_2" in decision_tree:
            step2 = decision_tree["step_2"]
            is_queue_stuck = telemetry.get("print_queue_stuck", False) or telemetry.get("print_queue_count", 0) > 0 or any(
                "queue" in s.lower() for s in incident_context.symptoms
            )
            if is_queue_stuck:
                act = step2.get("action_if_true")
                if act and isinstance(act, dict) and act.get("name", "").upper() not in failed_action_names:
                    proposed_action = act

        # Evaluasi Step 3: Check Connectivity / Driver / Diagnostic (Fallback alternatif)
        if not proposed_action and "step_3" in decision_tree:
            step3 = decision_tree["step_3"]
            is_unreachable = telemetry.get("printer_unreachable", False) or any(
                "unreachable" in s.lower() or "ping" in s.lower() for s in incident_context.symptoms
            )
            if is_unreachable:
                act = step3.get("action_if_true")
                if act and isinstance(act, dict) and act.get("name", "").upper() not in failed_action_names:
                    proposed_action = act
            else:
                act = step3.get("action_if_false")
                if act and isinstance(act, dict) and act.get("name", "").upper() not in failed_action_names:
                    proposed_action = act

        # 3. Validasi Keunikan Plan (FAILURE ADAPTATION ENFORCEMENT)
        if proposed_action and proposed_action.get("name", "").upper() in failed_action_names:
            logger.warning(
                f"[FailureAdaptation] Proposed action '{proposed_action.get('name')}' has ALREADY failed. "
                "Mutating plan to alternative action."
            )
            proposed_action = None

        # 4. Fallback jika semua aksi dalam SOP telah dicoba & gagal -> Pemicu Eskalasi
        if not proposed_action:
            logger.warning(f"[AdaptivePlanner] All actions in SOP '{selected_sop.get('sop_id')}' exhausted or failed. Escalating.")
            return {
                "plan_status": "EXHAUSTED_SOP_ACTIONS",
                "recommended_action": None,
                "requires_escalation": True,
                "reason": f"Seluruh aksi remedi pada SOP {selected_sop.get('sop_id')} telah dicoba dan gagal."
            }

        logger.info(f"[AdaptivePlanner] Generated plan: '{proposed_action.get('name')}' for device '{incident_context.device_id}'")
        return {
            "plan_status": "PLAN_GENERATED",
            "recommended_action": proposed_action,
            "requires_escalation": False,
            "reason": f"Rencana tindakan adaptif '{proposed_action.get('name')}' berhasil diformulasikan."
        }
