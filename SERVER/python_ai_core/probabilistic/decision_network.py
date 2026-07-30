"""
DECISION NETWORK & EXPECTED UTILITY ENGINE
Calculates Maximum Expected Utility (MEU) for candidate remediation actions:
EU(a) = Σ_{s} P(s) * [ P(success | a, s) * U(success) + P(fail | a, s) * U(fail) - Cost(Downtime) - Cost(BusinessRisk) ]

Compares candidate actions (e.g., Restart Service vs. Reboot Host vs. Clear Cache)
and selects the action with Maximum Expected Utility, balancing success rate against business risk and downtime.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger("DECISION_NETWORK")

class RemediationActionNode:
    """Representasi Aksi Pemulihan dengan Parameter Probabilitas & Utilitas."""
    def __init__(
        self,
        action_id: str,
        name: str,
        target_device: str,
        success_probability: float,
        estimated_downtime_seconds: float,
        business_risk_score: float, # 0.0 (Low) - 1.0 (Critical)
        description: str = ""
    ):
        self.action_id = action_id
        self.name = name
        self.target_device = target_device
        self.success_probability = min(1.0, max(0.0, success_probability))
        self.estimated_downtime_seconds = estimated_downtime_seconds
        self.business_risk_score = min(1.0, max(0.0, business_risk_score))
        self.description = description


class DecisionNetworkEngine:
    """
    Decision Network / Maximum Expected Utility (MEU) Engine.
    Menghitung Expected Utility untuk setiap kandidat aksi pemulihan AI:
    
    EU(a) = P(Success | a) * U(Success) + (1 - P(Success | a)) * U(Failure)
            - Penalty(Downtime) - Penalty(Business Risk)
    """

    def __init__(
        self,
        u_success: float = 100.0,       # Utilitas positif jika pemulihan berhasil
        u_failure: float = -200.0,      # Penalti utilitas negatif jika pemulihan gagal
        downtime_cost_per_sec: float = 0.5, # Biaya kerugian downtime per detik
        risk_penalty_weight: float = 40.0   # Bobot penalti risiko bisnis
    ):
        self.U_success = u_success
        self.U_failure = u_failure
        self.downtime_cost_per_sec = downtime_cost_per_sec
        self.risk_penalty_weight = risk_penalty_weight

    def calculate_action_expected_utility(
        self,
        action: RemediationActionNode,
        belief_distribution: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Menhitung Expected Utility (EU) untuk satu aksi pemulihan.
        """
        p_success = action.success_probability
        p_fail = 1.0 - p_success

        # 1. Base Expected Utility dari Hasil Pemulihan
        base_utility = (p_success * self.U_success) + (p_fail * self.U_failure)

        # 2. Biaya Penalti Downtime & Risiko Bisnis
        downtime_penalty = action.estimated_downtime_seconds * self.downtime_cost_per_sec
        risk_penalty = action.business_risk_score * self.risk_penalty_weight

        # 3. Penyesuaian Bobot berdasarkan Belief Distribution Sistem (jika ada)
        state_multiplier = 1.0
        if belief_distribution:
            # Jika belief state menunjukkan CRITICAL_FAILURE tinggi, toleransi downtime sedikit naik
            crit_prob = belief_distribution.get("CRITICAL_FAILURE", 0.0)
            if crit_prob > 0.5:
                state_multiplier = 0.7 # mengurangi penalti downtime dalam kondisi krisis
                
        total_downtime_penalty = downtime_penalty * state_multiplier
        final_expected_utility = base_utility - total_downtime_penalty - risk_penalty

        return {
            "action_id": action.action_id,
            "action_name": action.name,
            "target_device": action.target_device,
            "success_probability": round(p_success, 4),
            "success_percentage": f"{round(p_success * 100, 1)}%",
            "estimated_downtime_sec": action.estimated_downtime_seconds,
            "business_risk_score": action.business_risk_score,
            "base_utility": round(base_utility, 2),
            "downtime_penalty": round(total_downtime_penalty, 2),
            "risk_penalty": round(risk_penalty, 2),
            "expected_utility": round(final_expected_utility, 2)
        }

    def evaluate_and_select_optimal_action(
        self,
        candidate_actions: List[RemediationActionNode],
        belief_distribution: Optional[Dict[str, float]] = None
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Mengevaluasi seluruh kandidat aksi dan memilih Aksi Optimal berbasis Maximum Expected Utility (MEU).
        """
        if not candidate_actions:
            raise ValueError("No candidate actions provided to Decision Network Engine.")

        evaluated_list = []
        for action in candidate_actions:
            res = self.calculate_action_expected_utility(action, belief_distribution)
            evaluated_list.append(res)

        # Urutkan berdasarkan Expected Utility (MEU) tertinggi
        evaluated_list.sort(key=lambda x: x["expected_utility"], reverse=True)
        optimal_action = evaluated_list[0]

        logger.info(
            f"[DECISION NETWORK] Optimal Action Selected: '{optimal_action['action_name']}' "
            f"with MEU = {optimal_action['expected_utility']} (P_success={optimal_action['success_percentage']})"
        )
        return optimal_action, evaluated_list


# Self-Test Demo untuk Pemilihan Aksi Berbasis Maximum Expected Utility (MEU)
if __name__ == "__main__":
    engine = DecisionNetworkEngine()

    print("=== DECISION NETWORK & MAXIMUM EXPECTED UTILITY (MEU) TEST ===")
    print("Skenario: Membandingkan 3 Opsi Pemulihan untuk Insiden Spooler POS Kasir\n")

    # 3 Opsi Aksi Pemulihan:
    # Aksi A: Clear Printer Queue (Downtime 2 detik, Risk rendah 0.1, Success 80%)
    # Aksi B: Restart Spooler RPC Service (Downtime 10 detik, Risk rendah 0.2, Success 88%)
    # Aksi C: Reboot Entire Cashier Host (Downtime 300 detik, Risk tinggi 0.8, Success 95%)

    action_a = RemediationActionNode("ACT-01", "Clear Printer Queue", "PC-KASIR-01", 0.80, 2.0, 0.10)
    action_b = RemediationActionNode("ACT-02", "Restart Spooler Service", "PC-KASIR-01", 0.88, 10.0, 0.20)
    action_c = RemediationActionNode("ACT-03", "Reboot Cashier Host", "PC-KASIR-01", 0.95, 300.0, 0.80)

    actions = [action_a, action_b, action_c]
    optimal, ranked = engine.evaluate_and_select_optimal_action(actions)

    print(f"🏆 AKSI OPTIMAL TERPILIH (MEU): '{optimal['action_name']}' (Expected Utility: {optimal['expected_utility']})\n")
    print(f"{'Nama Aksi':<25} | {'P(Success)':<10} | {'Downtime':<10} | {'Risk':<6} | {'Expected Utility (MEU)':<22}")
    print("-" * 80)
    for r in ranked:
        print(f"{r['action_name']:<25} | {r['success_percentage']:<10} | {r['estimated_downtime_sec']:<4} sec   | {r['business_risk_score']:<6} | {r['expected_utility']:<22}")
