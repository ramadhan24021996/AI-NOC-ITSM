import json
import logging
from schemas import PolicySchema
from rag_engine import get_rag_engine

logger = logging.getLogger("SECURITY_AGENT")

class SecurityAgent:
    def __init__(self, nc=None):
        self.nc = nc
        self.rag = get_rag_engine()

    async def start(self):
        if not self.nc:
            return
        async def handler(msg):
            try:
                payload = json.loads(msg.data.decode())
                logger.info(f"Security Agent validating: {payload}")
                
                # Construct PolicySchema to validate the active policy rule
                policy = PolicySchema(
                    policy_id="POL-MAIN",
                    name="Dynamic Security Policy",
                    is_active=True,
                    blocked_commands=["rm -rf", "delete", "format", "shutdown /s", "kill -9"],
                    max_risk_allowed="medium"
                )
                
                action = payload.get("action", "").lower()
                confidence = float(payload.get("confidence", 0.0))
                severity = str(payload.get("severity", "LOW")).upper()
                
                is_safe = True
                reason = "Action verified safe under dynamic security policy"

                # 1. Blocked commands check
                for blocked in policy.blocked_commands:
                    if blocked in action:
                        is_safe = False
                        reason = f"Security Violation: Command contains blocked substring '{blocked}' (Blocked by policy {policy.policy_id})"
                        break

                # 2. Dynamic DB Policy check
                if is_safe:
                    try:
                        self.rag.connect()
                        rule_name = "HIGH_SEVERITY" if severity in ("HIGH", "CRITICAL") else "LOW_SEVERITY"
                        with self.rag.conn.cursor() as cur:
                            cur.execute("SELECT min_confidence, action_allowed FROM security_policy_rules WHERE rule_name = %s", (rule_name,))
                            row = cur.fetchone()
                            if row:
                                min_conf = float(row[0])
                                # Map 0-1 confidence back to percentage if needed
                                conf_pct = confidence if confidence > 1.0 else confidence * 100.0
                                min_conf_pct = min_conf if min_conf > 1.0 else min_conf * 100.0
                                
                                if conf_pct < min_conf_pct:
                                    is_safe = False
                                    reason = f"Security Policy Blocked: Confidence {conf_pct:.1f}% is lower than the required {min_conf_pct:.1f}% for severity {severity}"
                    except Exception as db_err:
                        logger.error(f"Error querying security policies DB: {db_err}")
                        try:
                            self.rag.conn.rollback()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    finally:
                        try:
                            self.rag.conn.close()
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')

                response_payload = {
                    "is_safe": is_safe,
                    "reason": reason,
                    "policy_applied": policy.dict()
                }
                await msg.respond(json.dumps(response_payload).encode())
            except Exception as e:
                logger.error(f"Error in SecurityAgent handler: {e}")
                await msg.respond(json.dumps({"error": str(e)}).encode())

        await self.nc.subscribe("agent.security.validate", cb=handler)
        logger.info("Security Agent listening on 'agent.security.validate'")
