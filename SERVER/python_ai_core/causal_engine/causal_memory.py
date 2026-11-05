"""
Causal Memory Module
Persistent memory store linking Incident -> Root Cause -> Counterfactual -> Evidence -> Operator Feedback.
Allows AI to learn and continuously improve RCA precision over time.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import json
import sqlite3
import os


@dataclass
class CausalMemoryRecord:
    incident_id: str
    device_id: str
    timestamp: str
    root_cause_variable: str
    confidence_score: float
    evidence_summary: Dict[str, Any]
    operator_feedback: Optional[str] = None  # "CONFIRMED", "REJECTED", "FALSE_POSITIVE"
    remediation_success: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "root_cause_variable": self.root_cause_variable,
            "confidence_score": self.confidence_score,
            "evidence_summary": self.evidence_summary,
            "operator_feedback": self.operator_feedback,
            "remediation_success": self.remediation_success
        }


class CausalMemory:
    def __init__(self, db_path: str = "/tmp/causal_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS causal_memory (
                incident_id TEXT PRIMARY KEY,
                device_id TEXT,
                timestamp TEXT,
                root_cause_variable TEXT,
                confidence_score REAL,
                evidence_summary TEXT,
                operator_feedback TEXT,
                remediation_success INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def store_memory(self, record: CausalMemoryRecord):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO causal_memory (
                incident_id, device_id, timestamp, root_cause_variable,
                confidence_score, evidence_summary, operator_feedback, remediation_success
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record.incident_id,
            record.device_id,
            record.timestamp,
            record.root_cause_variable,
            record.confidence_score,
            json.dumps(record.evidence_summary),
            record.operator_feedback,
            1 if record.remediation_success else 0
        ))
        conn.commit()
        conn.close()

    def record_feedback(self, incident_id: str, feedback: str, success: bool):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            UPDATE causal_memory
            SET operator_feedback = ?, remediation_success = ?
            WHERE incident_id = ?
        """, (feedback, 1 if success else 0, incident_id))
        conn.commit()
        conn.close()

    def get_memory(self, incident_id: str) -> Optional[CausalMemoryRecord]:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT incident_id, device_id, timestamp, root_cause_variable,
                   confidence_score, evidence_summary, operator_feedback, remediation_success
            FROM causal_memory WHERE incident_id = ?
        """, (incident_id,))
        row = cur.fetchone()
        conn.close()

        if row:
            return CausalMemoryRecord(
                incident_id=row[0],
                device_id=row[1],
                timestamp=row[2],
                root_cause_variable=row[3],
                confidence_score=row[4],
                evidence_summary=json.loads(row[5]),
                operator_feedback=row[6],
                remediation_success=bool(row[7])
            )
        return None
