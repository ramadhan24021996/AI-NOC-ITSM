"""
Unit Tests for Enterprise Causal Engine & Counterfactual Simulator
"""

import unittest
from causal_engine import (
    StructuralCausalModel, LayerType,
    CausalGraph, DoOperator,
    CounterfactualSimulator, ParallelSimulationRunner,
    CausalScorer, CausalExplainer
)


class TestCausalEngine(unittest.TestCase):
    def test_scm_variables(self):
        scm = StructuralCausalModel()
        self.assertIsNotNone(scm.get_variable("PacketLoss"))
        self.assertEqual(scm.get_variable("PacketLoss").layer, LayerType.L3_NETWORK)
        self.assertFalse(scm.get_variable("PacketLoss").is_anomalous())

        # Mutate variable
        scm.set_value("PacketLoss", 0.85)
        self.assertTrue(scm.get_variable("PacketLoss").is_anomalous())

    def test_do_operator(self):
        graph = CausalGraph()
        do_op = DoOperator(graph)

        # do(PacketLoss = 0.0) -> Normal
        sim_state = do_op.apply_do("PacketLoss", 0.0)
        self.assertEqual(sim_state["PacketLoss"], 0.0)

    def test_counterfactual_simulation_scenario(self):
        """
        Test Scenario:
        Real world incident state:
        PacketLoss = 0.85 (Anomalous)
        DNS_Timeout = True (Anomalous)
        POS_Error = True (Anomalous)
        Printer_Offline = True (Anomalous)

        Run Counterfactual Simulation:
        1) Printer_Offline = False -> POS_Error remains True (Printer is NOT root cause)
        2) PacketLoss = 0.0 -> POS_Error turns False (PacketLoss IS root cause)
        """
        real_world_state = {
            "PacketLoss": 0.85,
            "DNS_Timeout": True,
            "HTTP_502": True,
            "POS_Error": True,
            "Printer_Offline": True
        }

        sim = CounterfactualSimulator()

        # Test Printer_Offline intervention
        res_printer = sim.simulate_counterfactual("Printer_Offline", real_world_state, primary_symptom="POS_Error")
        self.assertFalse(res_printer.primary_symptom_resolved)
        self.assertFalse(res_printer.is_root_cause_candidate)

        # Test PacketLoss intervention
        res_pkt = sim.simulate_counterfactual("PacketLoss", real_world_state, primary_symptom="POS_Error")
        self.assertTrue(res_pkt.primary_symptom_resolved)
        self.assertTrue(res_pkt.is_root_cause_candidate)

    def test_multi_agent_intervention_and_explanation(self):
        real_world_state = {
            "PacketLoss": 0.85,
            "DNS_Timeout": True,
            "POS_Error": True,
            "Printer_Offline": True
        }

        runner = ParallelSimulationRunner()
        interventions = runner.run_simulations(real_world_state, primary_symptom="POS_Error")

        scorer = CausalScorer()
        ranked_scores = scorer.score_and_rank(interventions)

        self.assertGreaterEqual(len(ranked_scores), 1)
        top = ranked_scores[0]
        self.assertEqual(top.variable_name, "PacketLoss")
        self.assertGreaterEqual(top.confidence_pct, 90.0)

        explanation = CausalExplainer.explain(top, ranked_scores)
        self.assertIn("Primary Root Cause Identified", explanation)
        self.assertIn("PacketLoss", explanation)


if __name__ == "__main__":
    unittest.main()
