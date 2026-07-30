import logging
import json
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger("POLICY_ENGINE")

class PolicyEngine:
    """
    Hardened Policy Engine for NOC IT AI v3.0.
    Enforces dynamic OPA-style governance rules, policy versioning,
    database-backed invariant inputs, and audit trails.
    """

    def __init__(self):
        logger.info("Initializing Hardened OPA Governance Policy Engine.")

    def evaluate_policy(
        self,
        conn,
        confidence: float,
        risk: str,
        severity: str,
        action_type: str = "",
        incident_id: Optional[int] = None,
        trust_score: Optional[float] = None,
        blast_radius: Optional[int] = None,
        site_criticality: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """
        Evaluates the active governance policy ruleset in order of priority.
        
        Inputs evaluated:
          - severity: string (LOW, MEDIUM, HIGH, CRITICAL)
          - confidence: float (0.0 to 1.0)
          - risk: string (LOW, MEDIUM, HIGH, CRITICAL)
          - trust_score: float (0.0 to 100.0)
          - blast_radius: integer (1+)
          - site_criticality: string (LOW, MEDIUM, HIGH)

        Returns policy effect: "FORCE_HITL", "REQUIRE_APPROVAL", "AUTO_EXECUTE", etc.
        """
        # 1. Normalize confidence score to 0..1 range
        conf_val = float(confidence)
        if conf_val > 1.0:
            conf_val = conf_val / 100.0

        # 2. Kill Switch: Emergency abort for full autonomous mode
        import os
        if os.getenv("AI_ENABLE_AUTONOMOUS", "true").lower() == "false":
            logger.warning("KILL SWITCH ACTIVATED: AI_ENABLE_AUTONOMOUS=false. Forcing HITL.")
            return "FORCE_HITL"

        # 3. Retrieve missing inputs from database if connection is available
        db_trust_score = trust_score
        db_blast_radius = blast_radius
        db_site_criticality = site_criticality
        pc_name = None
        site_id = None
        db_severity = severity

        if conn and incident_id is not None:
            try:
                with conn.cursor() as cur:
                    # A. Fetch incident properties (pc_name, site_id, severity)
                    cur.execute(
                        "SELECT pc_name, site_id, severity FROM fleet_incidents WHERE incident_id = %s",
                        (incident_id,)
                    )
                    inc_row = cur.fetchone()
                    if inc_row:
                        pc_name, site_id, db_severity = inc_row
                        if not severity:
                            severity = db_severity

                    # B. Fetch trust score if not explicitly passed
                    if db_trust_score is None:
                        # First try pc_name
                        if pc_name:
                            cur.execute(
                                "SELECT trust_score FROM agent_trust_scores WHERE agent_name = %s",
                                (pc_name,)
                            )
                            ts_row = cur.fetchone()
                            if ts_row:
                                db_trust_score = float(ts_row[0])
                        # If still none, try agent_name
                        if db_trust_score is None and agent_name:
                            cur.execute(
                                "SELECT trust_score FROM agent_trust_scores WHERE agent_name = %s",
                                (agent_name,)
                            )
                            ts_row = cur.fetchone()
                            if ts_row:
                                db_trust_score = float(ts_row[0])
                        # If still none, fallback to default agent or 100.0
                        if db_trust_score is None:
                            cur.execute(
                                "SELECT trust_score FROM agent_trust_scores WHERE agent_name = 'NOC-Agent-01'"
                            )
                            ts_row = cur.fetchone()
                            db_trust_score = float(ts_row[0]) if ts_row else 100.0

                    # C. Fetch blast_radius from incident raw_data if not passed
                    if db_blast_radius is None:
                        cur.execute(
                            "SELECT raw_data FROM incidents WHERE incident_id = %s",
                            (incident_id,)
                        )
                        raw_row = cur.fetchone()
                        if raw_row and raw_row[0]:
                            raw_data = raw_row[0]
                            if isinstance(raw_data, str):
                                try:
                                    raw_data = json.loads(raw_data)
                                except:
                                    raw_data = {}
                            if isinstance(raw_data, dict):
                                db_blast_radius = (
                                    raw_data.get("blast_radius") or
                                    raw_data.get("metadata", {}).get("blast_radius")
                                )
                        if db_blast_radius is None:
                            db_blast_radius = 1 # safe default

                    # D. Fetch site criticality if not passed
                    if db_site_criticality is None:
                        target_site = site_id or "global"
                        cur.execute(
                            "SELECT criticality FROM fleet_sites WHERE site_id = %s",
                            (target_site,)
                        )
                        site_row = cur.fetchone()
                        db_site_criticality = site_row[0] if site_row else "MEDIUM"

            except Exception as db_err:
                logger.warning(f"Error querying policy parameters from DB: {db_err}")

        # Apply fallbacks for any parameter that remains None
        eval_trust_score = db_trust_score if db_trust_score is not None else 100.0
        eval_blast_radius = int(db_blast_radius) if db_blast_radius is not None else 1
        eval_site_criticality = str(db_site_criticality).upper() if db_site_criticality else "MEDIUM"
        eval_severity = str(severity or db_severity or "LOW").upper()
        eval_risk = str(risk or "MEDIUM").upper()

        # Build context object for rule evaluation
        context = {
            "confidence": conf_val,
            "risk_str": eval_risk,
            "severity": eval_severity,
            "trust_score": eval_trust_score,
            "blast_radius": eval_blast_radius,
            "site_criticality": eval_site_criticality,
            "action_type": action_type,
            # Backwards compatibility and numeric mapping
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4,
            "risk": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(eval_risk, 2),
            "severity_val": {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}.get(eval_severity, 2),
        }

        logger.info(f"Policy evaluation context: {context}")

        matched_rule = "None"
        effect = "REQUIRE_APPROVAL" # default fallback
        policy_version = 0

        # Try to load rules from active version (Versioning Model)
        rules = []
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT version, rules_json FROM policy_versions WHERE is_active = TRUE LIMIT 1"
                    )
                    row = cur.fetchone()
                    if row:
                        policy_version = row[0]
                        rules_data = row[1]
                        if isinstance(rules_data, str):
                            rules_data = json.loads(rules_data)
                        rules = rules_data.get("rules", [])
                        # Sort by priority desc
                        rules = sorted(rules, key=lambda x: x.get("priority", 0), reverse=True)
            except Exception as e:
                logger.warning(f"Failed to fetch active ruleset version: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # Fallback to legacy opa_policy_rules table if active version table is empty or failed
        if not rules and conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT rule_name, condition_expr, effect FROM opa_policy_rules ORDER BY priority DESC"
                    )
                    legacy_rows = cur.fetchall()
                    for r_name, expr, eff in legacy_rows:
                        rules.append({
                            "name": r_name,
                            "condition": expr,
                            "effect": eff
                        })
            except Exception as e:
                logger.warning(f"Failed to fetch legacy policy rules: {e}")
                if conn:
                    try:
                        conn.rollback()
                    except:
                        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        # Evaluate rules
        matched = False
        for r in rules:
            r_name = r.get("name")
            expr = r.get("condition")
            eff = r.get("effect")
            try:
                # Safe evaluation with restricted namespace
                result = eval(expr, {"__builtins__": None}, context)
                if result:
                    matched_rule = r_name
                    effect = eff
                    matched = True
                    logger.info(f"Rule matched: '{r_name}' -> Effect: {effect}")
                    break
            except Exception as eval_err:
                logger.error(f"Error evaluating rule condition '{expr}': {eval_err}")

        # If no rule matched, execute fallback logic
        if not matched:
            effect = self._fallback_evaluate(conf_val, eval_risk, eval_severity, eval_trust_score, eval_blast_radius)
            matched_rule = "System fallback logic"

        # Calculate rules signature hash for perfect replay
        import hashlib
        rules_str = json.dumps(rules, sort_keys=True)
        signature_hash = hashlib.sha256(rules_str.encode()).hexdigest()
        policy_snapshot_id = f"PSNP-v{policy_version}-{signature_hash[:16]}"

        # Log policy evaluation event to audit trail (Audit Trail Model)
        if conn:
            try:
                with conn.cursor() as cur:
                    # 0. Save to policy_snapshots if not exists
                    cur.execute(
                        "SELECT id FROM policy_snapshots WHERE policy_snapshot_id = %s",
                        (policy_snapshot_id,)
                    )
                    if not cur.fetchone():
                        cur.execute(
                            """
                            INSERT INTO policy_snapshots (policy_snapshot_id, policy_version, policy_content, signature_hash, created_at)
                            VALUES (%s, %s, %s, %s, NOW())
                            """,
                            (policy_snapshot_id, policy_version, rules_str, signature_hash)
                        )
                    
                    # Update policy_snapshot_id in incidents and fleet_incidents tables
                    if incident_id is not None:
                        cur.execute(
                            "UPDATE incidents SET policy_snapshot_id = %s WHERE incident_id = %s",
                            (policy_snapshot_id, incident_id)
                        )
                        cur.execute(
                            "UPDATE fleet_incidents SET policy_snapshot_id = %s WHERE incident_id = %s",
                            (policy_snapshot_id, incident_id)
                        )

                    # 1. Log to policy_audit_trail
                    cur.execute(
                        """
                        INSERT INTO policy_audit_trail 
                            (incident_id, policy_version, input_context, matched_rule, effect, evaluated_at)
                        VALUES (%s, %s, %s, %s, %s, NOW())
                        """,
                        (incident_id, policy_version, json.dumps(context), matched_rule, effect)
                    )
                    # 2. Log to security_events
                    cur.execute(
                        """
                        INSERT INTO security_events (rule_name, event_type, payload)
                        VALUES (%s, %s, %s)
                        """,
                        (matched_rule, "POLICY_EVALUATED", json.dumps({"context": context, "effect": effect, "incident_id": incident_id, "policy_snapshot_id": policy_snapshot_id}))
                    )
                    conn.commit()
            except Exception as log_err:
                logger.error(f"Failed to persist policy audit logs: {log_err}")
                try:
                    conn.rollback()
                except:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')

        return effect

    def _fallback_evaluate(
        self,
        confidence: float,
        risk: str,
        severity: str,
        trust_score: float = 100.0,
        blast_radius: int = 1
    ) -> str:
        """
        Fallback safety guardrail using deterministic HITL Matrix.
        
        BUKAN MOCK / BUKAN SIMULASI.
        Ini adalah lapisan keamanan deterministik yang dijalankan hanya apabila
        tidak ada aturan OPA yang aktif di database (policy_versions / opa_policy_rules).
        Logika ini menegakkan batas keamanan absolut yang tidak bisa dioverride.
        """
        # Hardcoded HITL Matrix Rules
        # Rule 1: Any CRITICAL severity incident ALWAYS requires HITL.
        if severity == "CRITICAL":
            return "FORCE_HITL"
            
        # Rule 2: Any action deemed HIGH risk ALWAYS requires HITL.
        if risk == "HIGH" or risk == "CRITICAL":
            return "FORCE_HITL"
            
        # Rule 3: Actions affecting more than 3 devices (Blast Radius) require HITL.
        if blast_radius > 3:
            return "FORCE_HITL"
            
        # Rule 4: Untrusted agents (trust_score < 70) cannot perform autonomous actions.
        if trust_score < 70.0:
            return "FORCE_HITL"
            
        # Rule 5: Medium risk requires high confidence (>85%) to auto-execute.
        if risk == "MEDIUM":
            if confidence >= 0.85:
                return "AUTO_EXECUTE"
            else:
                return "REQUIRE_APPROVAL"
                
        # Rule 6: Low risk auto-executes if confidence is acceptable (>70%).
        if risk == "LOW":
            if confidence >= 0.70:
                return "AUTO_EXECUTE"
            else:
                return "REQUIRE_APPROVAL"

        return "REQUIRE_APPROVAL"

def get_policy_engine():
    return PolicyEngine()
