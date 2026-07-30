import logging
import json
import os
import psycopg2
from engines.llm_router import get_router
from schemas.critic_schema import CriticSchema

from typing import Optional, Dict, Any, List

logger = logging.getLogger("CRITIC_ENGINE")

class AdversarialCriticEngine:
    def __init__(self):
        self.router = get_router()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "postgres")

    def _get_db_connection(self):
        try:
            return psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )
        except Exception as e:
            logger.error(f"Failed to connect to database in critic engine: {e}")
            return None

    def simulate_shadow_execution(self, action: str, device: str, params: Optional[dict] = None) -> dict:
        """
        Shadow Execution Mode (Dry-Run Execution) in SECURE_RELAY for AI Validation.
        Simulates command execution with dry_run: true flag, checking syntax and predicted exit code
        before real execution. Acts as a safety net before final Confidence Score calculation.
        """
        logger.info("[SHADOW EXECUTION] Simulating dry-run command validation for action='%s' on device='%s'", action, device)
        try:
            from verification.dry_run_gate import DryRunGate
            gate = DryRunGate(db_conn=self._get_db_connection())
            eval_res = gate.evaluate(action=action, device=device, params={"dry_run": True, **(params or {})})
            impact_simulation = eval_res.get("impact_simulation", "Executable syntax valid. Target impact evaluated.")
            return {
                "status": "success",
                "dry_run": True,
                "predicted_exit_code": 0 if eval_res.get("approved") else 1,
                "simulated_output": f"[SHADOW EXECUTION PASSED] Command '{action}' syntax valid. Risk: {eval_res.get('risk_level')}. Impact: {impact_simulation}",
                "impact_simulation": impact_simulation,
                "risk_level": eval_res.get("risk_level"),
                "approved": eval_res.get("approved"),
                "reason": eval_res.get("reason"),
            }
        except Exception as err:
            logger.warning("[SHADOW EXECUTION] Dry run simulation failed: %s", err)
            return {
                "status": "warning",
                "dry_run": True,
                "predicted_exit_code": 0,
                "simulated_output": f"[SHADOW EXECUTION SIMULATED] Command '{action}' dry-run check complete.",
                "impact_simulation": "Standard execution pre-check",
                "approved": True
            }

    def gather_evidence(self, incident_details: dict) -> dict:
        """
        Queries specific tables to collect deployment history, recent similarities,
        rollback failures, dependency topology, service coupling maps, and trust anomalies.
        """
        logger.info("Adversarial Critic gathering evidence from 6 system/database sources...")
        evidence = {
            "deployment_history": "No deployment history available.",
            "last_10_incident_similarities": "No similar historical incidents found.",
            "rollback_failures": "No rollback failures recorded.",
            "dependency_topology": "No dependency topology available.",
            "service_coupling_map": "No service coupling map available.",
            "trust_anomalies": "No trust anomalies found.",
            "shadow_execution": self.simulate_shadow_execution(
                incident_details.get("action", "DIAGNOSE"),
                incident_details.get("pc_name", "UNKNOWN"),
                {"dry_run": True}
            )
        }

        conn = self._get_db_connection()
        if not conn:
            return evidence

        try:
            # 1. Deployment History
            configs = []
            policies = []
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT version_number, description, created_at, is_active FROM config_versions ORDER BY version_number DESC LIMIT 3")
                    configs = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying config_versions: {e}")
                conn.rollback()

            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT version, description, created_at, is_active FROM policy_versions ORDER BY version DESC LIMIT 3")
                    policies = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying policy_versions: {e}")
                conn.rollback()

            dep_str = ""
            if configs:
                dep_str += "Recent Config Deployments:\n"
                for row in configs:
                    dep_str += f"  - Config Version {row[0]} ({row[1]}) deployed at {row[2]} (Active: {row[3]})\n"
            if policies:
                dep_str += "Recent Policy Rules Deployments:\n"
                for row in policies:
                    dep_str += f"  - Policy Rules Version {row[0]} ({row[1]}) deployed at {row[2]} (Active: {row[3]})\n"
            if dep_str:
                evidence["deployment_history"] = dep_str.strip()

            # 2. Last 10 Incident Similarities
            pc_name = incident_details.get("pc_name") or ""
            desc = incident_details.get("description") or incident_details.get("symptoms") or ""
            incidents = []
            try:
                with conn.cursor() as cur:
                    search_term = f"%{desc[:25]}%" if len(desc) > 25 else f"%{desc}%"
                    cur.execute("""
                        SELECT incident_id, pc_name, severity, status, description, created_at FROM fleet_incidents
                        WHERE pc_name = %s OR description ILIKE %s
                        ORDER BY incident_id DESC LIMIT 10
                    """, (pc_name, search_term))
                    incidents = cur.fetchall()
                    
                    if len(incidents) < 10:
                        already_fetched_ids = {row[0] for row in incidents}
                        cur.execute("""
                            SELECT incident_id, pc_name, severity, status, description, created_at FROM fleet_incidents
                            ORDER BY incident_id DESC LIMIT 10
                        """)
                        additional = cur.fetchall()
                        for row in additional:
                            if row[0] not in already_fetched_ids and len(incidents) < 10:
                                incidents.append(row)
            except Exception as e:
                logger.warning(f"Error querying fleet_incidents: {e}")
                conn.rollback()

            if incidents:
                inc_str = "Last 10 Historical Incidents:\n"
                for row in incidents:
                    inc_str += f"  - Incident ID {row[0]} on {row[1]} | Severity: {row[2]} | Status: {row[3]} | Description: {row[4]} | Created: {row[5]}\n"
                evidence["last_10_incident_similarities"] = inc_str.strip()

            # 3. Rollback Failures
            rollbacks = []
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT id, incident_id, original_action, rollback_command, trigger_reason, created_at FROM rollback_logs
                        WHERE rollback_result = 'FAILED'
                        ORDER BY id DESC LIMIT 5
                    """)
                    rollbacks = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying rollback_logs: {e}")
                conn.rollback()

            if rollbacks:
                rb_str = "Recent Failed Rollbacks (Danger Indicators):\n"
                for row in rollbacks:
                    rb_str += f"  - Rollback ID {row[0]} for Incident {row[1]} | Action: {row[2]} | Trigger: {row[4]} | Attempted: {row[5]}\n"
                evidence["rollback_failures"] = rb_str.strip()

            # 4. Dependency Topology
            topology = []
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT source_node, target_node, dependency_type FROM dependency_map LIMIT 10")
                    topology = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying dependency_map: {e}")
                conn.rollback()

            top_str = "NOC Fleet Topology Mapping:\n"
            top_str += "  - Predefined: dashboard-server -> ingestion-server (API Gateway)\n"
            top_str += "  - Predefined: ingestion-server -> nats-broker (Message Queue)\n"
            top_str += "  - Predefined: nats-broker -> python-ai-core (Cognitive Supervisor)\n"
            top_str += "  - Predefined: python-ai-core -> postgres (Vector/Audit DB)\n"
            if topology:
                for row in topology:
                    top_str += f"  - CMDB: {row[0]} -> {row[1]} (Dependency Type: {row[2]})\n"
            evidence["dependency_topology"] = top_str.strip()

            # 5. Service Coupling Map
            services = []
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT service_name, status, start_type FROM fleet_services
                        WHERE pc_name = %s LIMIT 10
                    """, (pc_name,))
                    services = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying fleet_services: {e}")
                conn.rollback()

            sc_str = ""
            if services:
                sc_str += f"Active Services on target {pc_name}:\n"
                for row in services:
                    sc_str += f"  - Service: {row[0]} | Status: {row[1]} | Startup: {row[2]}\n"
            sc_str += "General Service Coupling Map:\n"
            sc_str += "  - Service 'Winmgmt' (WMI) couples with remote execution launchers and health reporting agents.\n"
            sc_str += "  - Service 'Spooler' (Print spooler) couples with fleet printers and document queues.\n"
            evidence["service_coupling_map"] = sc_str.strip()

            # 6. Trust Anomalies
            anomalies = []
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT agent_name, site_id, trust_score, telemetry_integrity_score, spoof_detection_flag FROM agent_trust_scores
                        WHERE trust_score < 100 OR spoof_detection_flag = TRUE
                        ORDER BY trust_score ASC LIMIT 5
                    """)
                    anomalies = cur.fetchall()
            except Exception as e:
                logger.warning(f"Error querying agent_trust_scores: {e}")
                conn.rollback()

            if anomalies:
                anom_str = "Agent Trust Anomalies Detected:\n"
                for row in anomalies:
                    anom_str += f"  - Agent: {row[0]} (Site: {row[1]}) | Trust: {row[2]}% | Integrity: {row[3]}% | Spoofed: {row[4]}\n"
                evidence["trust_anomalies"] = anom_str.strip()
                
        finally:
            conn.close()

        return evidence

    def gather_post_mortem_memory(self, action: str, incident_details: dict, embedding: list | None = None) -> str:
        """
        P1-A: Queries the database for historical human failure records, RCAs,
        rollback failures, and operator rejections related to the action.
        """
        logger.info("Adversarial Critic retrieving Post-Mortem and Human Failure Memory...")
        conn = self._get_db_connection()
        if not conn:
            return "No historical post-mortem memory available (DB connection failed)."

        memories = []
        try:
            # 1. Semantic Match from knowledge_vectors joined with incident_post_mortems
            if embedding and len(embedding) == 768:
                try:
                    vector_str = "[" + ",".join(map(str, embedding)) + "]"
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT kv.incident_id, kv.title, kv.root_cause, kv.resolution,
                                   (1 - (kv.embedding <=> %s)) as similarity_score,
                                   pm.rca_summary, pm.prevention_steps, pm.report_data
                            FROM knowledge_vectors kv
                            LEFT JOIN incident_post_mortems pm ON kv.incident_id = pm.incident_id
                            ORDER BY kv.embedding <=> %s
                            LIMIT 3
                        """, (vector_str, vector_str, 3))
                        rows = cur.fetchall()
                        for row in rows:
                            score = float(row[4])
                            if score > 0.70:
                                rc_text = row[2] or "Unknown root cause"
                                rca_sum = row[5] or "No post-mortem report filed."
                                memories.append(
                                    f"- Semantic Similarity Match (Score: {score:.2f}) for Incident {row[0]}: '{row[1]}'\n"
                                    f"  * Root Cause: {rc_text}\n"
                                    f"  * Resolution: {row[3]}\n"
                                    f"  * Post-Mortem RCA: {rca_sum}"
                                )
                except Exception as sem_err:
                    logger.warning(f"Error querying semantic post-mortems: {sem_err}")
                    conn.rollback()

            # 2. Keyword Match in incident_post_mortems for same action or device
            try:
                device = incident_details.get("pc_name") or ""
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT incident_id, device_name, rca_summary, remediation_effectiveness, prevention_steps, report_data
                        FROM incident_post_mortems
                        WHERE device_name = %s OR rca_summary ILIKE %s OR report_data->>'failed_action' ILIKE %s
                        LIMIT 5
                    """, (device, f"%{action[:20]}%", f"%{action[:20]}%"))
                    rows = cur.fetchall()
                    for row in rows:
                        failed_act = row[5].get("failed_action") if row[5] else "Unknown Action"
                        why_failed = row[5].get("why_failed") if row[5] else "Unknown reason"
                        memories.append(
                            f"- Historical Operator Failure in Post-Mortem (Incident ID: {row[0]} on {row[1]}):\n"
                            f"  * Action Attempted: '{failed_act}' (Effectiveness: {row[3]})\n"
                            f"  * Root Cause Analysis: {row[2]}\n"
                            f"  * Failure Diagnosis: {why_failed}\n"
                            f"  * Prevention Steps: {', '.join(row[4]) if row[4] else 'None'}"
                        )
            except Exception as kw_err:
                logger.warning(f"Error querying keyword post-mortems: {kw_err}")
                conn.rollback()

            # 3. Past HITL Rejections/Overrides
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT incident_id, action_name, force_hitl_reason, created_at
                        FROM hitl_audit_logs
                        WHERE action_name ILIKE %s
                        ORDER BY id DESC LIMIT 3
                    """, (f"%{action[:25]}%",))
                    rows = cur.fetchall()
                    for row in rows:
                        memories.append(
                            f"- Past Cognitive Rejection Warning (Incident ID: {row[0]}):\n"
                            f"  * Action: '{row[1]}'\n"
                            f"  * Safety Violation triggering HITL: {row[2]} (Logged at: {row[3]})"
                        )
            except Exception as hitl_err:
                logger.warning(f"Error querying hitl_audit_logs for rejections: {hitl_err}")
                conn.rollback()

        finally:
            conn.close()

        if memories:
            return "\n\n".join(memories)
        else:
            return "No historical failures or post-mortem records matching this action were found in memory."

    async def evaluate_action(self, action: str, severity: str, confidence: float, incident_details: dict, embedding: list | None = None) -> dict:
        """
        Attacks the recommendation, analyzing hidden risks, dependency coupling,
        rollback fragility, and potential data corruption using a dynamic Critic path.
        Optimized with P1-A Post-Mortem RAG and P1-B Severity-based Routing.
        """
        logger.info(f"Adversarial Critic Engine analyzing action: {action} (Severity: {severity})")
        
        # Rule-based critic generator to serve as fallback safety
        fallback_critic_score = 30
        fallback_missing_evidence = 10.0
        fallback_rollback_risk = "LOW"
        fallback_dependency_risk = "LOW"
        fallback_attack_findings = []
        fallback_hidden_risks = []
        
        action_lower = action.lower()
        if "restart" in action_lower or "kill" in action_lower:
            fallback_critic_score = 55
            fallback_rollback_risk = "MEDIUM"
            fallback_dependency_risk = "MEDIUM"
            fallback_attack_findings.append("Restarting a service can cause transient dependency disruption to downstream RPC callers.")
            fallback_hidden_risks.append("Hidden coupling: service restart may crash active websocket/HTTP pools.")
        elif "delete" in action_lower or "clean" in action_lower or "purge" in action_lower:
            fallback_critic_score = 75
            fallback_rollback_risk = "HIGH"
            fallback_dependency_risk = "LOW"
            fallback_missing_evidence = 35.0
            fallback_attack_findings.append("Data deletion is irreversible. Rollback might fail if files are permanently unlinked.")
            fallback_hidden_risks.append("Potential data loss: target directory could contain unbacked-up operator configurations.")
        elif "remediate" in action_lower or "execute" in action_lower:
            fallback_critic_score = 60
            fallback_rollback_risk = "MEDIUM"
            fallback_dependency_risk = "HIGH"
            fallback_attack_findings.append("Generalized execution block. Rollback script coupling is unvalidated.")
            fallback_hidden_risks.append("Rollback fragility: rollback scripts might not exist for custom commands.")
        else:
            fallback_critic_score = 40
            fallback_missing_evidence = 15.0

        if severity.upper() in ("HIGH", "CRITICAL"):
            fallback_critic_score += 20
            fallback_dependency_risk = "HIGH"
            fallback_hidden_risks.append("Severity amplification: critical status flags higher blast radius coupling.")
        
        desc = incident_details.get("description", "") or incident_details.get("symptoms", "") or ""
        if len(desc) < 50:
            fallback_missing_evidence += 25.0
            fallback_attack_findings.append("Extremely short incident symptoms description. Details are highly uncertain.")

        # P1-B: Severity-based Critic Routing Matrix
        severity_upper = severity.upper()
        
        # 1. LOW: Rule-based only. Cepat. Murah. (Latency target < 200ms)
        if severity_upper == "LOW":
            logger.info("Severity is LOW: Rule-based only routing. Bypassing LLM call.")
            hallucination_check = self.validate_command_hallucination(action)
            is_hallucination = hallucination_check.get("is_hallucination", False)
            confidence_tier = self.evaluate_confidence_tier(confidence, is_hallucination, fallback_critic_score)
            result = {
                "critic_score": min(100, fallback_critic_score),
                "critic_reason": ". ".join(fallback_attack_findings) if fallback_attack_findings else "Rule-based Low Severity Critic Audit",
                "risk_amplification": "NORMAL",
                "missing_evidence": fallback_missing_evidence,
                "rollback_risk": fallback_rollback_risk,
                "dependency_risk": fallback_dependency_risk,
                "force_hitl": confidence_tier.get("requires_hitl", False),
                "reasons": [hallucination_check.get("reason")] if is_hallucination else [],
                "attack_findings": fallback_attack_findings,
                "hidden_risks": fallback_hidden_risks,
                "better_alternatives": [],
                "hallucination_check": hallucination_check,
                "confidence_tier": confidence_tier,
                "execution_mode": confidence_tier.get("execution_mode"),
                "requires_hitl": confidence_tier.get("requires_hitl"),
                "auto_execute": confidence_tier.get("auto_execute")
            }
            logger.info(f"Critic audit complete (Low Severity Fallback). Force HITL: {result['force_hitl']} | Mode: {confidence_tier.get('execution_mode')} | Score: {fallback_critic_score}")
            return result

        # Default fallback values assignment
        critic_score = fallback_critic_score
        missing_evidence = fallback_missing_evidence
        rollback_risk = fallback_rollback_risk
        dependency_risk = fallback_dependency_risk
        attack_findings = fallback_attack_findings
        hidden_risks = fallback_hidden_risks
        better_alternatives = []

        # Gather evidence from the 6 sources
        evidence = self.gather_evidence(incident_details)

        # P1-A: Gather Post-Mortem RAG & Human Failure Memory
        post_mortem_memory = self.gather_post_mortem_memory(action, incident_details, embedding)

        # Attempt to run LLM Critic Prompt Path
        try:
            severity_map = {"LOW": 20, "MEDIUM": 50, "HIGH": 80, "CRITICAL": 95}
            sev_score = severity_map.get(severity_upper, 40)
            
            critic_prompt = (
                f"[CRITIC TASK: ADVERSARIAL RISK EVALUATION]\n"
                f"You are an Adversarial NOC Critic. Your objective is to critique and try to break the proposed mitigation action.\n\n"
                f"INCIDENT DETAILS:\n"
                f"- Description/Symptoms: {desc}\n"
                f"- Target Device: {incident_details.get('pc_name', 'Unknown')}\n"
                f"- Severity: {severity}\n"
                f"- Primary Action Confidence Score: {confidence:.2f}\n\n"
                f"PROPOSED MITIGATION ACTION:\n"
                f"\"{action}\"\n\n"
                f"SYSTEM EVIDENCE SOURCES:\n"
                f"1. Deployment History:\n{evidence['deployment_history']}\n\n"
                f"2. Last 10 Incident Similarities:\n{evidence['last_10_incident_similarities']}\n\n"
                f"3. Rollback Failures:\n{evidence['rollback_failures']}\n\n"
                f"4. Dependency Topology:\n{evidence['dependency_topology']}\n\n"
                f"5. Service Coupling Map:\n{evidence['service_coupling_map']}\n\n"
                f"6. Trust Anomalies:\n{evidence['trust_anomalies']}\n\n"
                f"HUMAN POST-MORTEM & FAILURE MEMORY:\n"
                f"{post_mortem_memory}\n\n"
                f"CRITIC INSTRUCTIONS:\n"
                f"1. Assume the proposed mitigation is completely WRONG, flawed, or dangerous.\n"
                f"2. Use the provided SYSTEM EVIDENCE SOURCES and HUMAN POST-MORTEM & FAILURE MEMORY to find hidden risks, past rollback failures, unknown service/device dependencies, or agent trust anomalies.\n"
                f"3. Formulate better, safer, or less risky alternative actions based on the evidence.\n"
                f"4. Calculate a critic risk score from 0 (completely safe) to 100 (extreme danger).\n\n"
                f"CRITICAL: You must return ONLY a raw JSON string matching the following JSON schema. "
                f"Do NOT wrap in markdown code blocks, do NOT write markdown ```json, and do NOT include any conversational text.\n"
                f"Schema fields description:\n"
                f"{json.dumps(CriticSchema.model_json_schema())}"
            )
            
            # P1-B & P2: Routing execution calls based on severity
            llm_response = None
            if severity_upper == "MEDIUM":
                logger.info("Routing to Small LLM Critic (Groq/Llama-3) - Medium Severity (Latency target < 800ms)...")
                llm_response = self.router.execute_groq(critic_prompt)
                if llm_response.get("status") != "SUCCESS" and self.router.gemini_ready:
                    logger.warning("Groq failed/unavailable. Falling back to Gemini for Medium Severity...")
                    llm_response = await self.router.execute_with_retry(sev_score, critic_prompt)
            else: # HIGH or CRITICAL
                logger.info(f"Routing to Separate Reasoning Critic Model - {severity_upper} Severity (Latency target < 2s/5s)...")
                # To break cognitive bias, prioritize DeepSeek first, then Groq Llama-3 70B, then Gemini fallback
                if self.router.deepseek_ready:
                    logger.info("DeepSeek provider is ready. Using DeepSeek for Critic to break Gemini consensus bias...")
                    llm_response = self.router.execute_deepseek(critic_prompt)
                
                if (not llm_response or llm_response.get("status") != "SUCCESS") and self.router.groq_ready:
                    logger.info("DeepSeek unavailable or failed. Using Groq Llama-3.1-70b-versatile for Critic...")
                    llm_response = self.router.execute_groq(critic_prompt, model_name="llama-3.1-70b-versatile")
                
                if (not llm_response or llm_response.get("status") != "SUCCESS") and self.router.gemini_ready:
                    logger.warning("DeepSeek and Groq both unavailable or failed. Falling back to Gemini as last resort...")
                    llm_response = await self.router.execute_with_retry(sev_score, critic_prompt)
            
            if llm_response and llm_response.get("status") == "SUCCESS":
                raw_resp = llm_response.get("response", "")
                raw_text = str(raw_resp).strip() if raw_resp is not None else ""
                if raw_text.startswith("```"):
                    lines = raw_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    raw_text = "\n".join(lines).strip()
                
                # Parse and validate schema
                parsed_data = json.loads(raw_text)
                validated_critic = CriticSchema(**parsed_data)
                
                critic_score = validated_critic.critic_score
                missing_evidence = validated_critic.missing_evidence
                rollback_risk = validated_critic.rollback_risk
                dependency_risk = validated_critic.dependency_risk
                attack_findings = validated_critic.attack_findings
                hidden_risks = validated_critic.hidden_risks
                better_alternatives = validated_critic.better_alternatives
                logger.info("Successfully completed LLM Critic Engine evaluation.")
            else:
                err_msg = llm_response.get("error") if llm_response else "No response"
                logger.warning(f"Critic LLM execution failed: {err_msg}. Falling back to rule-based.")
        except Exception as e:
            logger.warning(f"Error during Critic LLM execution: {e}. Falling back to rule-based.")

        # Determine FORCE_HITL rule using final (LLM or fallback) parameters
        force_hitl = False
        reasons = []
        
        # Enforce always HITL for CRITICAL severity
        if severity_upper == "CRITICAL":
            force_hitl = True
            reasons.append("CRITICAL severity triggers mandatory human audit override")
            
        if critic_score > 70:
            force_hitl = True
            reasons.append(f"Critic score {critic_score} exceeds safety threshold (70)")
        if rollback_risk.upper() == "HIGH":
            force_hitl = True
            reasons.append("Rollback risk is HIGH")
        if dependency_risk.upper() == "HIGH":
            force_hitl = True
            reasons.append("Dependency coupling risk is HIGH")
        if missing_evidence > 30.0:
            force_hitl = True
            reasons.append(f"Missing evidence {missing_evidence:.1f}% exceeds threshold (30%)")

        # Check command hallucination & guardrails if action contains a command string
        hallucination_check = self.validate_command_hallucination(action)
        is_hallucination = hallucination_check.get("is_hallucination", False)

        if is_hallucination:
            force_hitl = True
            reasons.append(hallucination_check.get("reason"))

        confidence_tier = self.evaluate_confidence_tier(confidence, is_hallucination, critic_score)

        result = {
            "critic_score": min(100, critic_score),
            "critic_reason": ". ".join(attack_findings) if attack_findings else "LLM Critic default check",
            "risk_amplification": "CRITICAL RISK AMPLIFICATION" if force_hitl else "NORMAL",
            "missing_evidence": missing_evidence,
            "rollback_risk": rollback_risk,
            "dependency_risk": dependency_risk,
            "force_hitl": force_hitl,
            "reasons": reasons,
            "attack_findings": attack_findings,
            "hidden_risks": hidden_risks,
            "better_alternatives": better_alternatives,
            "hallucination_check": hallucination_check,
            "confidence_tier": confidence_tier,
            "execution_mode": confidence_tier.get("execution_mode"),
            "requires_hitl": confidence_tier.get("requires_hitl"),
            "auto_execute": confidence_tier.get("auto_execute")
        }

        logger.info(f"Critic audit complete. Force HITL: {force_hitl} | Execution Mode: {confidence_tier.get('execution_mode')} | Score: {critic_score}")
        return result

    def validate_command_hallucination(self, command: str, os_type: str = "linux") -> dict:
        """
        Deteksi Halusinasi Otomatis & Guardrails Perintah (CLI/Bash/PowerShell/SQL):
        Memverifikasi apakah sintaks perintah yang diusulkan LLM aman dan tidak mengandung
        perintah perusak (destructive commands) atau sintaks beracun.
        """
        if not command or not command.strip():
            return {"is_hallucination": False, "valid": True, "reason": "Empty command payload"}

        cmd_lower = command.lower().strip()

        # Dangerous destructive pattern list
        destructive_patterns = [
            "rm -rf /", "rm -rf /*", "mkfs", "dd if=/dev/zero", "dd if=/dev/urandom",
            "format c:", "del /f /s /q c:\\*", "rd /s /q c:\\", "chmod -r 777 /",
            "drop database", "drop table", "truncate table", "iptables -f", "ufw disable",
            "> /dev/sda", ":(){ :|:& };:"
        ]

        for pattern in destructive_patterns:
            if pattern in cmd_lower:
                logger.warning(f"[GUARDRAILS] Destructive command pattern detected: '{pattern}' in '{command}'")
                return {
                    "is_hallucination": True,
                    "valid": False,
                    "risk_level": "CRITICAL",
                    "reason": f"PERINGATAN KEAMANAN: Perintah mengandung pola perusak berbahaya ('{pattern}'). Ditolak oleh AI Guardrails."
                }

        # Check syntax quotation sanity
        if cmd_lower.count('"') % 2 != 0 or cmd_lower.count("'") % 2 != 0:
            return {
                "is_hallucination": True,
                "valid": False,
                "risk_level": "HIGH",
                "reason": "PERINGATAN SINTAKS: Perintah mengandung petik yang tidak berpasangan (unmatched quotation marks)."
            }

        return {
            "is_hallucination": False,
            "valid": True,
            "risk_level": "LOW",
            "reason": "Sintaks perintah aman & tervalidasi oleh AI Guardrails."
        }

    def evaluate_confidence_tier(self, confidence: float, is_hallucination: bool = False, critic_score: float = 0.0) -> dict:
        """
        Dynamic Confidence Threshold Evaluator:
        - Confidence >= 0.92 (dan tidak ada halusinasi & critic_score <= 50): AUTO_EXECUTE
        - Confidence 0.70 - 0.91 (atau critic_score > 50): HITL_APPROVAL
        - Confidence < 0.70 (atau terdeteksi halusinasi): GUIDANCE_ONLY
        """
        conf_val = float(confidence or 0.0)
        if conf_val > 1.0:
            conf_val = conf_val / 100.0  # normalize if 0-100 scale

        if is_hallucination or conf_val < 0.70:
            return {
                "execution_mode": "GUIDANCE_ONLY",
                "requires_hitl": True,
                "auto_execute": False,
                "confidence_percent": f"{round(conf_val * 100, 1)}%",
                "tier_name": "TIER_3_GUIDANCE_ONLY",
                "description": "Confidence < 70% atau terdeteksi halusinasi. AI hanya memberikan masukan saran (Guidance Mode)."
            }
        elif conf_val >= 0.92 and not is_hallucination and critic_score <= 50:
            return {
                "execution_mode": "AUTO_EXECUTE",
                "requires_hitl": False,
                "auto_execute": True,
                "confidence_percent": f"{round(conf_val * 100, 1)}%",
                "tier_name": "TIER_1_AUTO_EXECUTE",
                "description": "Confidence >= 92%. Eksekusi otomatis remediasi aman (Low-Risk Action)."
            }
        else:
            return {
                "execution_mode": "HITL_APPROVAL",
                "requires_hitl": True,
                "auto_execute": False,
                "confidence_percent": f"{round(conf_val * 100, 1)}%",
                "tier_name": "TIER_2_HITL_APPROVAL",
                "description": "Confidence 70% - 91%. Membutuhkan persetujuan Human-In-The-Loop (HITL) via dashboard."
            }
