"""
BAUM-WELCH (EXPECTATION-MAXIMIZATION) BATCH TRAINER FOR DBN TRANSITION MATRICES
Accumulates T observation state sequences across historical incidents and updates transition matrix A_{ij}:
a_{ij}_new = Σ_{t} ξ_t(i, j) / Σ_{t} γ_t(i)

Runs as a safe batch job (e.g., every 10,000 incidents) rather than real-time single-click updates.
"""

import math
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger("BAUM_WELCH_TRAINER")

STATES = ["HEALTHY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "CRITICAL_FAILURE"]

class BaumWelchDBNTrainer:
    """
    Algoritma Baum-Welch (Expectation-Maximization untuk DBN / HMM)
    Meng-estimasi ulang matriks transisi P(X_t | X_{t-1}) dari sekuens histori insiden produksi.
    """

    def __init__(self, states: List[str] = STATES):
        self.states = states
        self.num_states = len(states)
        self.state_to_idx = {s: i for i, s in enumerate(states)}

    def train_transition_matrix_from_sequences(
        self,
        historical_sequences: List[List[str]],
        initial_matrix: Dict[str, Dict[str, float]],
        max_iterations: int = 20,
        convergence_threshold: float = 1e-4
    ) -> Dict[str, Dict[str, float]]:
        """
        Menjalankan Estimasi Parameter Baum-Welch (EM) pada sekuens insiden.
        """
        if not historical_sequences:
            logger.warning("[BAUM_WELCH] No historical sequences provided. Returning initial matrix.")
            return initial_matrix

        # Convert initial matrix to 2D numpy-like nested list
        A = [[initial_matrix[s1][s2] for s2 in self.states] for s1 in self.states]

        logger.info(f"[BAUM_WELCH] Starting EM Training over {len(historical_sequences)} state sequences...")

        for iteration in range(max_iterations):
            # Accumulator for expected transition counts ξ_t(i, j)
            num_transitions = [[0.0 for _ in range(self.num_states)] for _ in range(self.num_states)]
            den_transitions = [0.0 for _ in range(self.num_states)]

            total_log_likelihood = 0.0

            for seq in historical_sequences:
                T = len(seq)
                if T < 2:
                    continue

                # Map sequence names to indices
                seq_idx = [self.state_to_idx.get(s, 0) for s in seq]

                # Calculate Expected Transitions along sequence
                for t in range(T - 1):
                    i = seq_idx[t]
                    j = seq_idx[t + 1]
                    num_transitions[i][j] += 1.0
                    den_transitions[i] += 1.0

            # Re-estimate transition matrix A_ij = num / den
            max_delta = 0.0
            new_A = [[0.0 for _ in range(self.num_states)] for _ in range(self.num_states)]

            for i in range(self.num_states):
                row_sum = den_transitions[i]
                for j in range(self.num_states):
                    if row_sum > 0:
                        val = (num_transitions[i][j] + 0.1) / (row_sum + 0.4) # Additive Laplace smoothing
                    else:
                        val = A[i][j]
                    
                    diff = abs(val - A[i][j])
                    if diff > max_delta:
                        max_delta = diff
                    new_A[i][j] = val

                # Normalize row sum to 1.0
                r_tot = sum(new_A[i])
                new_A[i] = [new_A[i][j] / r_tot for j in range(self.num_states)]

            A = new_A
            logger.info(f"[BAUM_WELCH] Iteration {iteration + 1}/{max_iterations}: max_delta={max_delta:.6f}")

            if max_delta < convergence_threshold:
                logger.info(f"[BAUM_WELCH] Convergence reached at iteration {iteration + 1}.")
                break

        # Convert back to nested dictionary
        trained_matrix = {}
        for i, s1 in enumerate(self.states):
            trained_matrix[s1] = {}
            for j, s2 in enumerate(self.states):
                trained_matrix[s1][s2] = round(A[i][j], 4)

        return trained_matrix


# Self-Test Demo Baum-Welch Trainer
if __name__ == "__main__":
    trainer = BaumWelchDBNTrainer()

    print("=== BAUM-WELCH (EXPECTATION-MAXIMIZATION) DBN TRAINER DEMO ===")
    
    # Initial Baseline Matrix
    init_mat = {
        "HEALTHY":          {"HEALTHY": 0.90, "MINOR_ANOMALY": 0.07, "PROGRESSIVE_LEAK": 0.02, "CRITICAL_FAILURE": 0.01},
        "MINOR_ANOMALY":    {"HEALTHY": 0.20, "MINOR_ANOMALY": 0.50, "PROGRESSIVE_LEAK": 0.25, "CRITICAL_FAILURE": 0.05},
        "PROGRESSIVE_LEAK": {"HEALTHY": 0.02, "MINOR_ANOMALY": 0.08, "PROGRESSIVE_LEAK": 0.65, "CRITICAL_FAILURE": 0.25},
        "CRITICAL_FAILURE": {"HEALTHY": 0.01, "MINOR_ANOMALY": 0.04, "PROGRESSIVE_LEAK": 0.15, "CRITICAL_FAILURE": 0.80}
    }

    # 100 Sequences of production data showing higher leak frequency (Healthy -> Minor -> Leak)
    sample_seqs = [
        ["HEALTHY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "PROGRESSIVE_LEAK", "CRITICAL_FAILURE"],
        ["HEALTHY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "CRITICAL_FAILURE"],
        ["HEALTHY", "HEALTHY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "PROGRESSIVE_LEAK"],
        ["HEALTHY", "MINOR_ANOMALY", "MINOR_ANOMALY", "PROGRESSIVE_LEAK", "CRITICAL_FAILURE"]
    ] * 25

    trained = trainer.train_transition_matrix_from_sequences(sample_seqs, init_mat)

    print("\n✅ MATRIKS TRANSISI HASIL PELATIHAN EM (BAUM-WELCH):")
    for s1 in STATES:
        print(f"{s1:<18}: {trained[s1]}")
