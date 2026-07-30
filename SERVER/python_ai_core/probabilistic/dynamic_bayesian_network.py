"""
DYNAMIC BAYESIAN NETWORK (DBN) FOR TIME-SERIES ANOMALY DETECTION
Tracks hidden system states (e.g., PROGRESSIVE_LEAK, SLOW_DEGRADATION) across time steps t-1 -> t:
Belief(X_t) = α * P(E_t | X_t) * Σ [ P(X_t | X_{t-1}) * Belief(X_{t-1}) ]
"""

import math
import logging
import json
import os
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger("DYNAMIC_BAYESIAN_NETWORK")

# Status Sistem Tersembunyi (Hidden System States)
STATES = ["HEALTHY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "CRITICAL_FAILURE"]

class DynamicBayesianNetwork:
    """
    Dynamic Bayesian Network (DBN) Engine untuk deteksi anomali kumulatif deret waktu (Time-Series).
    Menggabungkan Role-Adaptive Transition Matrix P(X_t | X_{t-1}, Role) dan Multivariate Observation Likelihood.
    """

    def __init__(self, model_filepath: Optional[str] = None):
        self.states = STATES
        self.initial_belief = {
            "HEALTHY": 0.95,
            "MINOR_ANOMALY": 0.04,
            "PROGRESSIVE_LEAK": 0.009,
            "CRITICAL_FAILURE": 0.001
        }

        # 1. Matriks Transisi Adaptif Per Role Perangkat (Context-Aware Transition Matrices)
        self.role_transition_matrices: Dict[str, Dict[str, Dict[str, float]]] = {
            "DATABASE": { # Database Server: Kebocoran memori / slow query lock berkembang lebih cepat
                "HEALTHY":          {"HEALTHY": 0.88, "MINOR_ANOMALY": 0.08, "PROGRESSIVE_LEAK": 0.035, "CRITICAL_FAILURE": 0.005},
                "MINOR_ANOMALY":    {"HEALTHY": 0.12, "MINOR_ANOMALY": 0.45, "PROGRESSIVE_LEAK": 0.350, "CRITICAL_FAILURE": 0.080},
                "PROGRESSIVE_LEAK": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.05, "PROGRESSIVE_LEAK": 0.640, "CRITICAL_FAILURE": 0.300},
                "CRITICAL_FAILURE": {"HEALTHY": 0.00, "MINOR_ANOMALY": 0.02, "PROGRESSIVE_LEAK": 0.100, "CRITICAL_FAILURE": 0.880}
            },
            "WEB_SERVER": { # Web Server: Kemungkinan auto-recovery lebih tinggi saat traffic melandai
                "HEALTHY":          {"HEALTHY": 0.94, "MINOR_ANOMALY": 0.05, "PROGRESSIVE_LEAK": 0.009, "CRITICAL_FAILURE": 0.001},
                "MINOR_ANOMALY":    {"HEALTHY": 0.35, "MINOR_ANOMALY": 0.50, "PROGRESSIVE_LEAK": 0.120, "CRITICAL_FAILURE": 0.030},
                "PROGRESSIVE_LEAK": {"HEALTHY": 0.05, "MINOR_ANOMALY": 0.15, "PROGRESSIVE_LEAK": 0.650, "CRITICAL_FAILURE": 0.150},
                "CRITICAL_FAILURE": {"HEALTHY": 0.02, "MINOR_ANOMALY": 0.08, "PROGRESSIVE_LEAK": 0.200, "CRITICAL_FAILURE": 0.700}
            },
            "POS_CASHIER": { # PC Kasir POS: Sangat dipengaruhi Spooler & Thread Lock
                "HEALTHY":          {"HEALTHY": 0.92, "MINOR_ANOMALY": 0.06, "PROGRESSIVE_LEAK": 0.018, "CRITICAL_FAILURE": 0.002},
                "MINOR_ANOMALY":    {"HEALTHY": 0.20, "MINOR_ANOMALY": 0.50, "PROGRESSIVE_LEAK": 0.250, "CRITICAL_FAILURE": 0.050},
                "PROGRESSIVE_LEAK": {"HEALTHY": 0.02, "MINOR_ANOMALY": 0.08, "PROGRESSIVE_LEAK": 0.650, "CRITICAL_FAILURE": 0.250},
                "CRITICAL_FAILURE": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.04, "PROGRESSIVE_LEAK": 0.150, "CRITICAL_FAILURE": 0.800}
            }
        }
        
        if model_filepath:
            self.load_model(model_filepath)

        # Default transition matrix fallback
        self.default_transition_matrix = self.role_transition_matrices["POS_CASHIER"]

        # State memory per perangkat {device_id: current_belief_dict}
        self._device_beliefs: Dict[str, Dict[str, float]] = {}

    def fit_transition_matrices(self, historical_transitions: List[Tuple[str, str, str]]):
        """
        historical_transitions: list of (role, prev_state, next_state)
        """
        counts = {}
        for role, prev_s, next_s in historical_transitions:
            role = role.upper()
            if role not in counts:
                counts[role] = {s: {ns: 0 for ns in self.states} for s in self.states}
            if prev_s in self.states and next_s in self.states:
                counts[role][prev_s][next_s] += 1
                
        for role, role_counts in counts.items():
            if role not in self.role_transition_matrices:
                self.role_transition_matrices[role] = {s: {ns: 0.0 for ns in self.states} for s in self.states}
                
            for prev_s, next_counts in role_counts.items():
                total = sum(next_counts.values())
                if total > 0:
                    for next_s, count in next_counts.items():
                        self.role_transition_matrices[role][prev_s][next_s] = round(count / total, 4)
                        
    def save_model(self, filepath: str):
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump({"role_transition_matrices": self.role_transition_matrices}, f, indent=4)
            
    def load_model(self, filepath: str):
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                if "role_transition_matrices" in data:
                    self.role_transition_matrices = data["role_transition_matrices"]
                    logger.info(f"Loaded role_transition_matrices from {filepath}")

    def get_transition_matrix_for_role(self, role: str) -> Dict[str, Dict[str, float]]:
        """Mengambil matriks transisi adaptif sesuai role perangkat."""
        return self.role_transition_matrices.get(role.upper(), self.default_transition_matrix)

    def get_time_adjusted_transition_matrix(self, role: str, current_hour: Optional[int] = None) -> Dict[str, Dict[str, float]]:
        """
        Mengambil matriks transisi adaptif yang disesuaikan dengan Jam Operasional (Peak vs Off-Peak).
        Jam 08:00 - 17:00 (Peak Hours): Probabilitas eskalasi anomali dinaikkan 1.25x.
        """
        import datetime
        if current_hour is None:
            current_hour = datetime.datetime.now().hour

        base_matrix = self.get_transition_matrix_for_role(role)
        is_peak_hours = (8 <= current_hour <= 17)

        if not is_peak_hours:
            return base_matrix

        # Scale escalation rates during peak business hours
        adjusted_matrix = {}
        for s_from, transitions in base_matrix.items():
            adjusted_matrix[s_from] = {}
            total = 0.0
            for s_to, prob in transitions.items():
                if s_from != s_to and s_to in ["PROGRESSIVE_LEAK", "CRITICAL_FAILURE"]:
                    new_p = prob * 1.25
                else:
                    new_p = prob
                adjusted_matrix[s_from][s_to] = new_p
                total += new_p
            # Normalize row so sum equals 1.0
            for s_to in adjusted_matrix[s_from]:
                adjusted_matrix[s_from][s_to] = round(adjusted_matrix[s_from][s_to] / total, 4)

        return adjusted_matrix

    def get_context_adjusted_transition_matrix(
        self,
        role: str,
        context_risk_scale: float = 1.0
    ) -> Dict[str, Dict[str, float]]:
        """
        Mengambil matriks transisi adaptif yang disesuaikan dengan Konteks Bisnis (Kalender & Event).
        """
        base_matrix = self.get_transition_matrix_for_role(role)
        if context_risk_scale == 1.0:
            return base_matrix

        adjusted_matrix = {}
        for s_from, transitions in base_matrix.items():
            adjusted_matrix[s_from] = {}
            total = 0.0
            for s_to, prob in transitions.items():
                if s_from != s_to and s_to in ["PROGRESSIVE_LEAK", "CRITICAL_FAILURE"]:
                    new_p = prob * context_risk_scale
                else:
                    new_p = prob
                adjusted_matrix[s_from][s_to] = new_p
                total += new_p

            for s_to in adjusted_matrix[s_from]:
                adjusted_matrix[s_from][s_to] = round(adjusted_matrix[s_from][s_to] / total, 4)

        return adjusted_matrix

    def get_device_belief(self, device_name: str) -> Dict[str, float]:
        """Mengambil distribusi belief terkini untuk perangkat tertentu."""
        if device_name not in self._device_beliefs:
            self._device_beliefs[device_name] = dict(self.initial_belief)
        return self._device_beliefs[device_name]

    def compute_multivariate_observation_likelihood(self, state: str, observation: Dict[str, Any]) -> float:
        """
        Menhitung Likelihood Multivariate P(Evidence_t | State_t).
        Memodelkan 8 Variabel Bukti sekaligus:
        - z_score_mem, z_score_cpu, mem_growth_rate (%/jam)
        - gc_pause_ms (JVM GC Pause Duration)
        - swap_usage_percent, thread_count, open_handles, oom_events (Count)
        """
        z_mem = float(observation.get("z_score_mem", 0.0))
        z_cpu = float(observation.get("z_score_cpu", 0.0))
        growth_rate = float(observation.get("mem_growth_rate", 0.0))
        gc_pause_ms = float(observation.get("gc_pause_ms", 0.0))
        swap_percent = float(observation.get("swap_usage_percent", 0.0))
        thread_count = float(observation.get("thread_count", 0.0))
        oom_events = int(observation.get("oom_events", 0))

        if state == "HEALTHY":
            p_mem = math.exp(-0.5 * (z_mem ** 2))
            p_growth = 0.95 if growth_rate < 2.0 else 0.10
            p_gc = 0.95 if gc_pause_ms < 100 else 0.20
            p_oom = 0.99 if oom_events == 0 else 0.01
            return max(0.0001, p_mem * p_growth * p_gc * p_oom)

        elif state == "MINOR_ANOMALY":
            p_mem = math.exp(-0.5 * ((z_mem - 2.0) ** 2))
            p_growth = 0.80 if 2.0 <= growth_rate < 5.0 else 0.30
            p_gc = 0.80 if 100 <= gc_pause_ms < 500 else 0.30
            p_oom = 0.95 if oom_events == 0 else 0.05
            return max(0.0001, p_mem * p_growth * p_gc * p_oom)

        elif state == "PROGRESSIVE_LEAK":
            # Likelihood tinggi jika growth_rate > 5%, swap naik, atau thread count naik kumulatif
            p_growth = 1.0 / (1.0 + math.exp(-(growth_rate - 4.0)))
            p_swap = 1.0 / (1.0 + math.exp(-(swap_percent - 20.0)/10.0)) if swap_percent > 0 else 0.60
            p_mem = 0.85 if z_mem >= 1.8 else 0.50
            return max(0.0001, p_growth * p_mem * p_swap)

        elif state == "CRITICAL_FAILURE":
            # Likelihood tinggi jika OOM events > 0, GC pause > 1000ms, atau Z_mem > 3.5
            p_mem = 1.0 / (1.0 + math.exp(-(z_mem - 3.5)))
            p_oom = 0.99 if oom_events > 0 else 0.40
            p_gc = 0.95 if gc_pause_ms >= 1000 else 0.40
            return max(0.0001, p_mem * p_oom * p_gc)

        return 0.10

    def update_belief_step(self, device_name: str, observation_t: Dict[str, Any], role: str = "POS_CASHIER") -> Tuple[Dict[str, float], str]:
        """
        Melakukan Forward Filtering DBN (Bayesian Update over Time):
        1. Prediction Step: P(X_t | E_{1:t-1}) = Σ [ P(X_t | X_{t-1}, Role) * Belief(X_{t-1}) ]
        2. Update Step: Belief(X_t) = α * P(Multivariate_E_t | X_t) * Prediction(X_t)
        """
        prev_belief = self.get_device_belief(device_name)
        trans_matrix = self.get_time_adjusted_transition_matrix(role)

        # 1. Prediction Step (Prior untuk time step t)
        predicted_belief = {}
        for next_state in self.states:
            sum_prob = 0.0
            for prev_state in self.states:
                trans_prob = trans_matrix[prev_state][next_state]
                sum_prob += trans_prob * prev_belief[prev_state]
            predicted_belief[next_state] = sum_prob

        # 2. Update Step (Multiply Multivariate Likelihood P(E_t | X_t))
        unnormalized_belief = {}
        total_weight = 0.0
        for state in self.states:
            likelihood = self.compute_multivariate_observation_likelihood(state, observation_t)
            updated_val = likelihood * predicted_belief[state]
            unnormalized_belief[state] = updated_val
            total_weight += updated_val

        # 3. Normalisasi (α factor)
        if total_weight == 0:
            total_weight = 1.0

        normalized_belief = {}
        for state in self.states:
            normalized_belief[state] = round(unnormalized_belief[state] / total_weight, 4)

        # Update memori belief perangkat
        self._device_beliefs[device_name] = normalized_belief

        # Tentukan status dominan
        dominant_state = max(self.states, key=lambda s: normalized_belief.get(s, 0.0))
        
        logger.info(f"[DBN ENGINE] Updated Belief for '{device_name}' (Role={role}): Dominant={dominant_state} ({normalized_belief[dominant_state]*100:.1f}%) | Full={normalized_belief}")
        return normalized_belief, dominant_state


# Self-Test Demo untuk Simulasi Kebocoran Memori Lambat (Slow Memory Leak 3-Jam)
if __name__ == "__main__":
    dbn = DynamicBayesianNetwork()
    target_device = "PC-KASIR-08"

    print(f"=== SIMULASI DETEKSI ANOMALI DBN TIME-SERIES UNTUK '{target_device}' ===")
    print("Skenario: Memori naik lambat dari Z=0.5 -> Z=1.8 -> Z=2.4 -> Z=3.1 dalam 3 Jam (T=0 s.d. T=6)\n")

    # Simulasi 7 Time Steps (Tiap 30 Menit)
    time_series_observations = [
        {"time": "T+00m", "z_score_mem": 0.4, "z_score_cpu": 0.8, "mem_growth_rate": 0.5},
        {"time": "T+30m", "z_score_mem": 0.9, "z_score_cpu": 1.1, "mem_growth_rate": 2.1},
        {"time": "T+60m", "z_score_mem": 1.4, "z_score_cpu": 1.3, "mem_growth_rate": 4.5},
        {"time": "T+90m", "z_score_mem": 1.8, "z_score_cpu": 1.5, "mem_growth_rate": 6.8}, # Belum breach Z > 3.0, tapi DBN mendeteksi!
        {"time": "T+120m","z_score_mem": 2.3, "z_score_cpu": 1.8, "mem_growth_rate": 8.9},
        {"time": "T+150m","z_score_mem": 2.9, "z_score_cpu": 2.1, "mem_growth_rate": 11.2},
        {"time": "T+180m","z_score_mem": 3.4, "z_score_cpu": 2.6, "mem_growth_rate": 14.5},
    ]

    for step in time_series_observations:
        t_label = step["time"]
        belief, dominant = dbn.update_belief_step(target_device, step)
        
        print(f"[{t_label}] Observasi: Z_mem={step['z_score_mem']:<4} Growth={step['mem_growth_rate']:<4}%/jam")
        print(f"       Status Dominan: {dominant:<18} (Probabilitas: {belief[dominant]*100:.1f}%)")
        print(f"       Distribusi State: HEALTHY={belief['HEALTHY']*100:.1f}%, MINOR={belief['MINOR_ANOMALY']*100:.1f}%, LEAK={belief['PROGRESSIVE_LEAK']*100:.1f}%, CRITICAL={belief['CRITICAL_FAILURE']*100:.1f}%\n")
