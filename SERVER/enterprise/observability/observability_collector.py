"""
SERVER.enterprise.observability - AI Observability & Decision Trace
Exposes AI pipeline metrics and Decision Trace entries without modifying python_ai_core.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from SERVER.shared.models import DecisionTraceEntryDTO

class ObservabilityCollector(ABC):
    """Abstract observability collector. python_ai_core remains unmodified."""

    @abstractmethod
    def record_decision_trace(self, trace_entry: DecisionTraceEntryDTO) -> None:
        pass

    @abstractmethod
    def record_metric(self, metric_name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        pass

    @abstractmethod
    def get_decision_traces(self, query_id: str) -> List[DecisionTraceEntryDTO]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 5.1
# ══════════════════════════════════════════════════════════════════════════════
import os, json, logging
import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor

_olog = logging.getLogger("enterprise.observability")

def _pgconn():
    return PGConnection()

class PostgreSQLObservabilityCollector(ObservabilityCollector):
    """
    Persists AI pipeline decision traces to ai_audit_trail.
    Stores metrics in telemetry_metrics table (if available), else logs.
    """

    def record_decision_trace(self, trace_entry: "DecisionTraceEntryDTO") -> None:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO ai_audit_trail
                           (event_id, actor, action_type, target, detail, created_at)
                           VALUES (gen_random_uuid(), %s, %s, %s, %s, NOW())""",
                        (
                            trace_entry.agent_id,
                            "DECISION_TRACE",
                            trace_entry.step_name,
                            json.dumps({
                                "input_summary":  trace_entry.input_summary,
                                "output_summary": trace_entry.output_summary,
                                "evidence_score": trace_entry.evidence_score,
                                "duration_ms":    trace_entry.duration_ms,
                                "timestamp":      trace_entry.timestamp,
                            })
                        )
                    )
                    conn.commit()
        except Exception as e:
            _olog.error("[ObservabilityCollector] record_decision_trace failed: %s", e, exc_info=True)

    def record_metric(self, metric_name: str, value: float,
                      labels: Optional[Dict[str, str]] = None) -> None:
        labels = labels or {}
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    # Try telemetry_metrics table; fall back to ai_audit_trail
                    try:
                        cur.execute(
                            """INSERT INTO telemetry_metrics (metric_name, value, labels, recorded_at)
                               VALUES (%s, %s, %s, NOW())""",
                            (metric_name, value, json.dumps(labels))
                        )
                    except Exception:
                        conn.rollback()
                        cur.execute(
                            """INSERT INTO ai_audit_trail (actor, action_type, target, detail, created_at)
                               VALUES (%s, %s, %s, %s, NOW())""",
                            ("system", "METRIC", metric_name,
                             json.dumps({"value": value, "labels": labels}))
                        )
                    conn.commit()
        except Exception as e:
            _olog.error("[ObservabilityCollector] record_metric(%s) failed: %s", metric_name, e, exc_info=True)

    def get_decision_traces(self, query_id: str) -> List["DecisionTraceEntryDTO"]:
        try:
            with PGConnection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT actor, action_type, target, detail, created_at
                           FROM ai_audit_trail
                           WHERE action_type = 'DECISION_TRACE' AND target = %s
                           ORDER BY created_at DESC LIMIT 50""",
                        (query_id,)
                    )
                    rows = cur.fetchall()
            from SERVER.shared.models import DecisionTraceEntryDTO
            result = []
            for r in rows:
                d = r.get("detail") or {}
                if isinstance(d, str):
                    d = json.loads(d)
                result.append(DecisionTraceEntryDTO(
                    step_name=str(r.get("target","")),
                    agent_id=str(r.get("actor","")),
                    input_summary=d.get("input_summary",""),
                    output_summary=d.get("output_summary",""),
                    evidence_score=float(d.get("evidence_score",0.0)),
                    duration_ms=float(d.get("duration_ms",0.0)),
                    timestamp=str(r.get("created_at","")),
                ))
            return result
        except Exception as e:
            _olog.error("[ObservabilityCollector] get_decision_traces(%s) failed: %s", query_id, e, exc_info=True)
            return []
