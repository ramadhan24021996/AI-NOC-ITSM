"""
Regression & Governance Test Suite for AI Incident Analysis (WS-IA1 .. WS-IA5)
==============================================================================
Verifies:
- WS-IA1: Go Portal Strict Rule #6 Dual-Evidence & NATS approval.decision wiring
- WS-IA2: ActionVerifier 'success' contract, POST_REMEDIATION_EVIDENCE, & incident_triage verification trigger fix
- WS-IA3: ConsensusEngine Honest Confidence Degradation (zero hallucinated Winmgmt/Spooler fallback)
- WS-IA4: LLMRouter Process-Wide Singleton, Multi-Key Gemini 3.1/2.5 rotation, & Zombie Retry Loop quarantine
- WS-IA5: 3-Tier Cognitive Funnel & adaptive debate rounds
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_ws_ia1_go_portal_rule6_and_nats_approval_contract():
    """
    WS-IA1:
    1. DirectApproveTimeline must NOT increment validated_knowledge_base or broadcast 'RESOLVED'.
    2. DirectApproveTimeline and ApproveMitigation must publish 'approval.decision' to NATS.
    3. GetIncidents must coalesce missing status to 'OPEN', not 'RESOLVED'.
    4. closed_loop.go and state_machine.go must enforce Rule #6 GuardTransition + POST_REMEDIATION_EVIDENCE.
    """
    incident_go = (REPO_ROOT / "portal/dashboard/incident/incident.go").read_text(encoding="utf-8")
    closed_loop_go = (REPO_ROOT / "portal/dashboard/incident/closed_loop.go").read_text(encoding="utf-8")
    state_machine_go = (REPO_ROOT / "portal/dashboard/incident/state_machine.go").read_text(encoding="utf-8")

    # 1. GetIncidents default status is 'OPEN'
    assert "COALESCE(s.status, i.raw_data->>'status', 'OPEN') as status" in incident_go
    assert "COALESCE(s.status, i.raw_data->>'status', 'RESOLVED') as status" not in incident_go

    # 2. DirectApproveTimeline section check
    direct_approve_block = incident_go.split("func (h *Handler) DirectApproveTimeline")[1].split(
        "func (h *Handler) DirectRejectTimeline"
    )[0]
    assert "validated_knowledge_base" not in direct_approve_block, (
        "DirectApproveTimeline must NEVER run RLOF positive learning on HITL approval click (Rule #6 violation)"
    )
    assert '"incident.resolved"' not in direct_approve_block, (
        "DirectApproveTimeline must NEVER publish or broadcast incident.resolved before execution & verification"
    )
    assert '"approval.decision"' in direct_approve_block
    assert '"status":      "IN_PROGRESS"' in direct_approve_block

    # 3. ApproveMitigation & RejectMitigation publish approval.decision with approvedIncidentID / rejectedIncidentID
    approve_mit_block = incident_go.split("func (h *Handler) ApproveMitigation")[1].split(
        "func (h *Handler) RejectMitigation"
    )[0]
    assert '"approval.decision"' in approve_mit_block
    assert "approvedIncidentID" in approve_mit_block

    # 4. closed_loop.go enforces 2 consecutive healthy checks + GuardTransition + POST_REMEDIATION_EVIDENCE
    assert "consecutiveHealthy >= 2" in closed_loop_go
    assert "POST_REMEDIATION_EVIDENCE" in closed_loop_go
    assert "GuardTransition(db, incidentID, StatePendingVerification, StateResolved)" in closed_loop_go

    # 5. state_machine.go checks POST_REMEDIATION_EVIDENCE >= EXECUTION_EVIDENCE
    assert "POST_REMEDIATION_EVIDENCE" in state_machine_go
    assert "EXECUTION_EVIDENCE" in state_machine_go
    assert "post_ev.created_at >= exec_ev.created_at" in state_machine_go


def test_ws_ia2_action_verifier_and_triage_background_verification():
    """
    WS-IA2:
    1. ActionVerifier returns {'status': 'SUCCESS', 'success': True, ...} on predicate pass
       and {'success': False, 'failure_reason': ...} on failure.
    2. incident_triage.py runs run_background_verification ONLY when action_executed starts with
       AUTO_EXECUTED or EXECUTING_ (never inside the else: branch!).
    """
    from SERVER.python_ai_core.verification.action_verifier import ActionVerifier

    verifier = ActionVerifier(db_conn=None, rollback_engine=None, shadow_mode=True)
    verifier._fetch_current_metrics = MagicMock(
        return_value={"status": "ONLINE", "cpu_percent": 25.0, "ram_percent": 40.0}
    )

    res = asyncio.run(
        verifier.verify_execution(
            incident_id=101,
            execution_id="exec-101",
            action_name="DEFAULT",
            pc_name="PC-TEST-01",
        )
    )
    assert res["status"] == "SUCCESS"
    assert res["success"] is True

    # Failure path
    fail_res = asyncio.run(
        verifier._handle_failure(101, "DEFAULT", "PC-TEST-01", "exec-101", 0, 50, False, "VERIFY_TIMEOUT")
    )
    assert fail_res["success"] is False
    assert fail_res["failure_reason"] == "VERIFY_TIMEOUT"

    # Check incident_triage.py indentation & condition
    triage_src = (
        REPO_ROOT / "SERVER/python_ai_core/supervisor/handlers/incident_triage.py"
    ).read_text(encoding="utf-8")
    assert 'action_executed.startswith("AUTO_EXECUTED")' in triage_src
    # Ensure run_background_verification is before 'else:\n            exec_id = None'
    idx_verify = triage_src.index("run_background_verification(")
    idx_else_none = triage_src.index("else:\n            exec_id = None")
    assert idx_verify < idx_else_none, "run_background_verification must run inside the if-executed block, NOT in else!"


def test_ws_ia3_consensus_engine_honest_degradation():
    """
    WS-IA3:
    ConsensusEngine._simulated_verdict must NEVER fabricate 0.92 Winmgmt or 0.80 Spooler verdicts.
    When all cloud providers fail, get_consensus_verdict must degrade confidence honestly (<= 0.45)
    and force HIGH risk (HITL) without mutating caller's historical_context list.
    """
    from SERVER.python_ai_core.engines.consensus_engine import ConsensusEngine

    engine = ConsensusEngine()
    degraded = engine._simulated_verdict("Gemini-Test", "INCIDENT: CPU 99%", reason="HTTP 429")
    assert degraded["unavailable"] is True
    assert degraded["confidence"] == 0.0
    assert "Winmgmt" not in degraded["recommended_action"]
    assert "Spooler" not in degraded["recommended_action"]

    # Force all 3 cloud models to return degraded/unavailable verdicts
    engine.execute_model_a_gemini = AsyncMock(return_value=degraded)
    engine.execute_model_b_deepseek = AsyncMock(return_value=degraded)
    engine.execute_model_c_groq = AsyncMock(return_value=degraded)
    engine.execute_model_d_local_nli = AsyncMock(
        return_value={"model": "local-nli", "recommended_action": "Restart Nginx", "confidence": 0.40}
    )

    caller_history = [{"incident_id": 1, "recommended_action": "Restart Nginx", "similarity": 0.91}]
    verdict = asyncio.run(
        engine.get_consensus_verdict(
            incident_details={"type": "CPU_SPIKE", "description": "High CPU on web node"},
            historical_context=caller_history,
        )
    )
    # Caller's list must not be mutated with local_nli_verdict
    assert len(caller_history) == 1
    assert verdict["confidence"] <= 0.45
    assert verdict["risk_level"] == "HIGH"


def test_ws_ia4_llm_router_singleton_and_zombie_retry_quarantine():
    """
    WS-IA4:
    1. get_router() returns the exact same singleton instance across calls, and new LLMRouter()
       instances share _SHARED_COGNITIVE without re-initializing SQLite schemas.
    2. Retired gemini-1.5-flash / gemini-1.5-pro are replaced with gemini-3.1-flash-lite-preview / gemini-2.5-flash.
    3. ai_supervisor.py passes nc_client=nc to ai_retry_handler, and incident_retry.py quarantines NULL device_name rows.
    """
    from SERVER.python_ai_core.engines.llm_router import LLMRouter, get_router

    r1 = get_router()
    r2 = get_router()
    r3 = LLMRouter()
    assert r1 is r2
    assert r1.memory_graph is r3.memory_graph
    assert r1.key_manager is r3.key_manager

    route_low = r1._plan_route(30)
    route_high = r1._plan_route(90)
    all_models = [item["model"] if isinstance(item, dict) else item[1] for item in route_low + route_high]
    assert "gemini-1.5-flash" not in all_models
    assert "gemini-1.5-pro" not in all_models
    assert r1.route_incident(30) == "gemini-3.1-flash-lite-preview"
    assert r1.route_incident(90) == "gemini-2.5-flash"

    sup_src = (REPO_ROOT / "SERVER/python_ai_core/ai_supervisor.py").read_text(encoding="utf-8")
    retry_src = (REPO_ROOT / "SERVER/python_ai_core/supervisor/handlers/incident_retry.py").read_text(encoding="utf-8")
    assert "await ai_retry_handler(msg, nc_client=nc)" in sup_src
    assert "ABANDONED_NO_DEVICE" in retry_src
    assert "UPDATE incident_states SET status = 'ANALYZING'" in retry_src


def test_ws_ia5_three_tier_cognitive_funnel():
    """
    WS-IA5:
    incident_triage.py implements Tier-1 HypothesisEngine fast-track, adaptive max_debate_rounds,
    conditional OutputAdapterFacade synthesis with gemini-3.1-flash-lite-preview, and PENDING_VERIFICATION governance hook.
    """
    triage_src = (
        REPO_ROOT / "SERVER/python_ai_core/supervisor/handlers/incident_triage.py"
    ).read_text(encoding="utf-8")
    assert "Tier-1 Deterministic Hypothesis Fast-Track" in triage_src
    assert "max_debate_rounds = 2 if severity_score >= 85 else 1" in triage_src
    assert 'model_version="gemini-3.1-flash-lite-preview"' in triage_src
    assert 'model_version="gemini-1.5-flash"' not in triage_src
    assert 'human_resolution="PENDING_VERIFICATION"' in triage_src


def test_ws_ia6_system_wide_embeddings_taxonomy_and_auditor():
    """
    WS-IA6:
    1. EnterpriseLayerProfile in osi_taxonomy.py provides primary_layer, primary_name,
       secondary_layers, confidence_score, and dict-compatible .get().
    2. LLMRouter provides centralized embed_text_768(text), and knowledge_worker / KnowledgeMemory
       use it with deterministic 768-dim fallback.
    3. docker-compose.yml passes OSI_SECURITY_KEY & volume mounts to ai-consensus, ai-critic,
       ai-policy, ai-rag, and ai-daemons, and defaults ENABLE_CHAOS_MONKEY to false.
    4. portal/state_machine.go enforces Rule #6 Dual-Evidence Binding and portal/server_auditor.go
       checks AI Sub-Agents in agent_heartbeats + AI REST/JARVIS endpoints.
    """
    from SERVER.python_ai_core.cognition.osi_taxonomy import classify_incident_layer
    from SERVER.python_ai_core.engines.llm_router import get_router

    profile = classify_incident_layer("OSPF neighbor down and packet loss on gateway router, HTTP 503 timeout")
    assert isinstance(profile.primary_layer, int)
    assert profile.primary_layer == 3
    assert isinstance(profile.primary_name, str) and profile.primary_name
    assert isinstance(profile.secondary_layers, list)
    assert isinstance(profile.confidence_score, float) and 0.0 < profile.confidence_score <= 1.0
    assert profile.get("primary_layer") == 3

    router = get_router()
    assert hasattr(router, "embed_text_768")

    compose_src = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "ENABLE_CHAOS_MONKEY=${ENABLE_CHAOS_MONKEY:-false}" in compose_src
    assert "ENABLE_CHAOS_MONKEY=true" not in compose_src

    portal_sm = (REPO_ROOT / "portal/state_machine.go").read_text(encoding="utf-8")
    assert "RULE_6_VIOLATION" in portal_sm
    assert "POST_REMEDIATION_EVIDENCE" in portal_sm

    auditor_src = (REPO_ROOT / "portal/server_auditor.go").read_text(encoding="utf-8")
    assert "aiSubAgentOnlineCount" in auditor_src
    assert 'checkTCP("osi-python-ai-core:8088")' in auditor_src
    assert 'checkTCP("osi-jarvis-voice-server:8089")' in auditor_src

    kw_src = (REPO_ROOT / "SERVER/python_ai_core/learning/knowledge_worker.py").read_text(encoding="utf-8")
    assert "with PGConnection() as conn:" in kw_src
    assert "PGConnection().__enter__()" not in kw_src

    pool_src = (REPO_ROOT / "SERVER/shared/db_pool.py").read_text(encoding="utf-8")
    assert "class _PooledConnectionProxy:" in pool_src


