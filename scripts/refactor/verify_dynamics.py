import os
import sys

# Add python_ai_core to path to match pyright config
sys.path.append(os.path.join(os.path.dirname(__file__), 'SERVER', 'python_ai_core'))

from probabilistic.probabilistic_engine import BayesianHypothesisEngine
from probabilistic.dynamic_bayesian_network import DynamicBayesianNetwork

print("=== VERIFIKASI DYNAMIC PRIORS ===")
engine = BayesianHypothesisEngine()
print(f"Priors sebelum training: {engine.default_priors}")

# Mock data: 10 incidents, 8 memory leak, 2 unindexed query
historical_incidents = [
    "MEMORY_LEAK", "MEMORY_LEAK", "UNINDEXED_QUERY", "MEMORY_LEAK", "MEMORY_LEAK",
    "MEMORY_LEAK", "MEMORY_LEAK", "UNINDEXED_QUERY", "MEMORY_LEAK", "MEMORY_LEAK"
]

engine.fit_priors(historical_incidents)
print(f"Priors setelah training: {engine.default_priors}")

engine.save_model('/tmp/prob_model.json')
engine2 = BayesianHypothesisEngine('/tmp/prob_model.json')
print(f"Priors di-load dari JSON: {engine2.default_priors}\n")


print("=== VERIFIKASI DYNAMIC MATRICES ===")
dbn = DynamicBayesianNetwork()
print(f"Matrix DATABASE HEALTHY->HEALTHY sebelum training: {dbn.role_transition_matrices['DATABASE']['HEALTHY']['HEALTHY']}")

# Mock data: Database mostly transitions to MINOR_ANOMALY from HEALTHY
historical_transitions = [
    ("DATABASE", "HEALTHY", "MINOR_ANOMALY"),
    ("DATABASE", "HEALTHY", "MINOR_ANOMALY"),
    ("DATABASE", "HEALTHY", "HEALTHY"),
    ("DATABASE", "MINOR_ANOMALY", "PROGRESSIVE_LEAK")
]

dbn.fit_transition_matrices(historical_transitions)
print(f"Matrix DATABASE HEALTHY->HEALTHY setelah training: {dbn.role_transition_matrices['DATABASE']['HEALTHY']['HEALTHY']}")
print(f"Matrix DATABASE HEALTHY->MINOR_ANOMALY setelah training: {dbn.role_transition_matrices['DATABASE']['HEALTHY']['MINOR_ANOMALY']}")

dbn.save_model('/tmp/dbn_model.json')
dbn2 = DynamicBayesianNetwork('/tmp/dbn_model.json')
print(f"Matrix DATABASE HEALTHY->MINOR_ANOMALY dari JSON: {dbn2.role_transition_matrices['DATABASE']['HEALTHY']['MINOR_ANOMALY']}\n")
