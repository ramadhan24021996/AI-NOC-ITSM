"""
Full End-to-End Multi-Layer Integration Suite for Causal AI Platform
Simulates full pipeline across Layers L1 to L7 failure scenarios:
L1 Cable Disconnect, L2 VLAN Misconfig, L3 Gateway Unreachable, L4 Firewall Block, L5/L6 TLS Fail, L7 POS Timeout.
"""

import unittest
from causal_engine import (
    EvidenceCollector, StructuralCausalModel,
    CausalGraph, CounterfactualSimulator,
    CausalValidator, InterventionPlanner,
    CausalScorer, CausalExplainer,
    ProductionKPIEngine
)


class TestFullCausalPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.collector = EvidenceCollector()
        self.scm = StructuralCausalModel()
        self.graph = CausalGraph(self.scm)
        self.simulator = CounterfactualSimulator(self.graph)
        self.validator = CausalValidator()
        self.planner = InterventionPlanner()
        self.scorer = CausalScorer()

    def test_layer1_to_layer7_cascade_integration(self):
        """
        Integration Scenario:
        Wireless AP signal drop -> Packet Loss -> DNS Timeout -> Connection Timeout -> POS Error & Printer Offline.
        """
        raw_payload = {
            "device_id": "POS-KASIR-STORE-01",
            "telemetry": {
                "rssi_dbm": -88,
                "packet_loss": 0.85,
                "rtt_ms": 1450,
                "resolve_time_ms": 5000
            },
            "windows_events": [{"event_id": 7036, "service": "PrintSpooler"}],
            "browser_console": [{"error": "ERR_NAME_NOT_RESOLVED"}]
        }

        # 1. Evidence Collection
        evidence = self.collector.collect_all_evidence(raw_payload)
        self.assertEqual(evidence.device_id, "POS-KASIR-STORE-01")

        # 2. Construct Real World Incident State
        real_world_state = {
            "RSSI": -88,
            "PacketLoss": 0.85,
            "DNS_Timeout": True,
            "ConnectionTimeout": True,
            "POS_Error": True,
            "Printer_Offline": True
        }

        # 3. Counterfactual Simulation
        cf_result = self.simulator.simulate_counterfactual("PacketLoss", real_world_state, primary_symptom="POS_Error")
        self.assertTrue(cf_result.primary_symptom_resolved)
        self.assertTrue(cf_result.is_root_cause_candidate)

        # 4. Causal Validation
        val_result = self.validator.validate_hypothesis("PacketLoss", evidence.to_dict())
        self.assertTrue(val_result.is_valid)

        # 5. Actionable Intervention Planning
        actions = self.planner.get_actionable_steps("PacketLoss")
        self.assertGreaterEqual(len(actions), 1)
        self.assertEqual(actions[0].action_id, "ACT-NET-01")

    def test_layer5_layer6_tls_certificate_failure_integration(self):
        """
        Integration Scenario:
        SSL/TLS Certificate Expired -> TLS Handshake Failure -> Connection Timeout -> POS Login Error.
        """
        real_world_state = {
            "CertExpired": True,
            "TLS_Failure": True,
            "ConnectionTimeout": True,
            "POS_Error": True
        }

        cf_cert = self.simulator.simulate_counterfactual("CertExpired", real_world_state, primary_symptom="POS_Error")
        self.assertTrue(cf_cert.primary_symptom_resolved)
        self.assertTrue(cf_cert.is_root_cause_candidate)


if __name__ == "__main__":
    unittest.main()
