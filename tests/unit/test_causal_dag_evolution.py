"""
tests.unit.test_causal_dag_evolution
====================================
Unit tests for Online Dynamic Causal DAG Edge Calibration and Feedback Ingestion.
"""
import unittest
from unittest.mock import MagicMock
from SERVER.python_ai_core.engines.causal_dag_engine import CausalDAGEngine


class TestCausalDAGEvolution(unittest.TestCase):

    def setUp(self):
        self.mock_db = MagicMock()
        self.engine = CausalDAGEngine(db_conn=self.mock_db)

    def test_ingest_causal_feedback_success_reward(self):
        """Test that verified resolution increases causal edge weights."""
        mock_cursor = MagicMock()
        self.mock_db.cursor.return_value.__enter__.return_value = mock_cursor
        
        # Simulate existing edges in PostgreSQL reasoning_edges
        mock_cursor.fetchall.return_value = [
            ("node-1", "node-2", 0.60, "HYPOTHESIS", {"description": "Memory Leak on Spooler"}),
            ("node-1", "node-3", 0.40, "HYPOTHESIS", {"description": "Network Packet Loss"}),
        ]

        result = self.engine.ingest_causal_feedback(
            incident_id="INC-4102",
            verified_root_cause_type="SPOOLER",
            success=True
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["calibrated_edges"], 1)
        self.assertTrue(result["success"])
        
        # Verify UPDATE query was executed with reward (+0.15 => 0.75)
        mock_cursor.execute.assert_any_call("""
                        UPDATE reasoning_edges
                        SET weight = %s
                        WHERE from_node = %s AND to_node = %s
                    """, (0.75, "node-1", "node-2"))
        self.mock_db.commit.assert_called()

    def test_ingest_causal_feedback_failure_penalty(self):
        """Test that failed remediation penalizes false hypothesis edge weight."""
        mock_cursor = MagicMock()
        self.mock_db.cursor.return_value.__enter__.return_value = mock_cursor

        # Simulate wrong hypothesis: "Network Packet Loss"
        mock_cursor.fetchall.return_value = [
            ("node-1", "node-3", 0.45, "HYPOTHESIS", {"description": "Network Packet Loss"}),
        ]

        result = self.engine.ingest_causal_feedback(
            incident_id="INC-4102",
            verified_root_cause_type="SPOOLER",
            success=False
        )

        self.assertEqual(result["status"], "CALIBRATED")
        self.assertEqual(result["calibrated_edges"], 1)
        self.assertFalse(result["success"])

        # Verify UPDATE query was executed with penalty (-0.20 => 0.25)
        mock_cursor.execute.assert_any_call("""
                        UPDATE reasoning_edges
                        SET weight = %s
                        WHERE from_node = %s AND to_node = %s
                    """, (0.25, "node-1", "node-3"))


if __name__ == "__main__":
    unittest.main()
