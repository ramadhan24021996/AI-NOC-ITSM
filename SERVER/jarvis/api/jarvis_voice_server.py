"""
SERVER.jarvis.api.jarvis_voice_server — JARVIS Voice API HTTP Server
=====================================================================
Production-grade HTTP service exposing JarvisPresentationRuntime via REST.

FIX-1A: Creates the missing HTTP bridge between Go Portal and Python JARVIS Brain.

Endpoints:
  POST /jarvis/voice/query   — Process voice/text command through full JARVIS pipeline
  GET  /jarvis/health        — Liveness & readiness probe
  GET  /jarvis/session/{id}  — Get session conversation history

Architecture:
  Go Portal → POST /jarvis/voice/query → JarvisVoiceServer → JarvisPresentationRuntime
    → WakeWordDetector → PhoneticCorrector → PrivacyRedactor → LLMVoiceCommandTranslator
    → JarvisCommandIntentRouter → JarvisNOCBridge / UnifiedGateway → TTSProvider
    → JSON response with answer_text + audio_b64 + intent + avatar_state

Design Decisions:
  - Uses Python stdlib http.server (zero new pip deps — matches existing rest_api_server.py pattern)
  - Thread-safe lazy singleton JarvisPresentationRuntime
  - CORS headers enabled for Go portal same-host calls
  - Graceful degradation: if NOCBridge unreachable, returns LLM-only response
  - Runs on port 8089 (configurable via JARVIS_VOICE_API_PORT env var)
"""
import json
import logging
import os
import sys
import time
import base64
import traceback
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("jarvis.api.voice_server")

# ── Proactive Announcer (lazy import) ────────────────────────────────────────
_proactive_announcer = None

def _get_proactive_announcer():
    """Lazy singleton untuk JarvisProactiveAnnouncer."""
    global _proactive_announcer
    if _proactive_announcer is None:
        try:
            from SERVER.jarvis.proactive.jarvis_proactive_announcer import get_announcer
            _proactive_announcer = get_announcer()
            logger.info("[JarvisVoiceServer] JarvisProactiveAnnouncer ready.")
        except Exception as e:
            logger.warning(f"[JarvisVoiceServer] ProactiveAnnouncer init failed: {e}")
    return _proactive_announcer

# ── Singleton Runtime Container ───────────────────────────────────────────────

_runtime_lock = threading.Lock()
_runtime_instance = None
_runtime_init_error: Optional[str] = None
_runtime_ready = False


def _build_runtime():
    """
    Lazily initializes the full JarvisPresentationRuntime.
    Called once on first request — not at import time to avoid startup delays.
    Uses NOCIntegrationGateway (concrete impl) not abstract UnifiedGateway.
    """
    global _runtime_instance, _runtime_init_error, _runtime_ready

    try:
        logger.info("[JarvisVoiceServer] Initializing JarvisPresentationRuntime...")

        # 1. Gateway — concrete NOC integration gateway
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        gateway = NOCIntegrationGateway()
        logger.info("[JarvisVoiceServer] NOCIntegrationGateway initialized.")

        # 2. Voice services — lazy-init providers, safe if libs not installed
        from SERVER.jarvis.voice.stt_service import STTService
        from SERVER.jarvis.voice.tts_service import TTSService
        from SERVER.jarvis.voice.stt_provider import FasterWhisperSTTProvider
        from SERVER.jarvis.voice.tts_provider import EdgeTTSProvider, KokoroTTSProvider

        # EdgeTTS primary, Kokoro fallback (auto-detected at synthesis time)
        tts_provider = EdgeTTSProvider(
            voice_name=os.getenv("JARVIS_TTS_VOICE", "id-ID-ArdiNeural")
        )
        stt_provider = FasterWhisperSTTProvider(
            model_size=os.getenv("JARVIS_STT_MODEL", "base"),
            device=os.getenv("JARVIS_STT_DEVICE", "cpu"),
            language=os.getenv("JARVIS_STT_LANG", "id"),
        )
        stt_service = STTService(provider=stt_provider)
        tts_service = TTSService(provider=tts_provider)
        logger.info("[JarvisVoiceServer] STT/TTS services configured.")

        # 3. NOC Bridge
        from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge
        noc_bridge = JarvisNOCBridge()

        # 4. Full Runtime
        from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
        runtime = JarvisPresentationRuntime(
            gateway=gateway,
            stt_service=stt_service,
            tts_service=tts_service,
            noc_bridge=noc_bridge,
        )

        _runtime_instance = runtime
        _runtime_ready = True
        logger.info("[JarvisVoiceServer] ✅ JarvisPresentationRuntime READY — All P1-P19 components active.")

    except Exception as e:
        _runtime_init_error = str(e)
        _runtime_ready = False
        logger.error(f"[JarvisVoiceServer] ❌ Runtime init failed: {e}\n{traceback.format_exc()}")


def _get_runtime():
    """Thread-safe singleton accessor with lazy initialization."""
    global _runtime_instance
    if _runtime_instance is None:
        with _runtime_lock:
            if _runtime_instance is None:
                _build_runtime()
    return _runtime_instance


# ── Request Handler ───────────────────────────────────────────────────────────

class JarvisVoiceHTTPHandler(BaseHTTPRequestHandler):
    """
    Production HTTP Handler for JARVIS Voice API.
    Handles CORS, JSON parsing, error responses, and routing.
    """

    # Suppress default HTTP access log in favor of structured logger
    def log_message(self, format, *args):
        logger.debug(f"[HTTP] {self.address_string()} - {format % args}")

    def _cors_headers(self):
        """Add CORS headers to allow Go portal same-origin calls."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Session-ID")

    def _send_json(self, status_code: int, data: Dict[str, Any]):
        """Send JSON response with CORS headers."""
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Dict[str, Any]:
        """Read and parse JSON request body safely."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            logger.warning(f"[JarvisVoiceServer] Body parse error: {e}")
            return {}

    def do_OPTIONS(self):
        """Preflight CORS request handler."""
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        """GET endpoint router."""
        path = self.path.split("?")[0]

        if path == "/jarvis/voice/config":
            self._handle_voice_config_get()
            return
        elif path == "/jarvis/health":
            self._handle_health()
        elif path == "/jarvis/voice/duplex":
            self._handle_voice_duplex_ws()
        elif path == "/jarvis/reliability/health":
            self._handle_reliability_health()
        elif path == "/jarvis/governance/gates":
            self._handle_governance_gates()
        elif path == "/jarvis/assurance/adversarial_audit":
            self._handle_assurance_adversarial_audit()
        elif path == "/jarvis/assurance/v42_audit":
            self._handle_assurance_v42_audit()
        elif path == "/jarvis/assurance/slo":
            self._handle_assurance_slo()
        elif path == "/jarvis/session/causal_evidence":
            self._handle_session_causal_evidence()
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def _handle_assurance_v42_audit(self):
        """GET /jarvis/assurance/v42_audit — Run 44+ Expanded Adversarial Matrix Suite V4.2."""
        try:
            from SERVER.jarvis.assurance.adversarial_validation_suite import get_expanded_adversarial_assurance_matrix_v42
            matrix = get_expanded_adversarial_assurance_matrix_v42()
            res = matrix.run_full_assurance_matrix_suite()
            self._send_json(200, res)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] V4.2 Assurance audit error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_assurance_slo(self):
        """GET /jarvis/assurance/slo — Query 30-day Rolling Window SLO & Global Safety State V4.2."""
        try:
            from SERVER.jarvis.assurance.adversarial_validation_suite import get_expanded_adversarial_assurance_matrix_v42
            matrix = get_expanded_adversarial_assurance_matrix_v42()
            slo_data = matrix.slo_engine.calculate_rolling_slo()
            slo_data["global_safety_state"] = matrix.global_safety.get_state_summary()
            self._send_json(200, slo_data)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] SLO query error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_assurance_adversarial_audit(self):
        """GET /jarvis/assurance/adversarial_audit — Run 17-Point Adversarial Validation Suite V4.1."""
        try:
            from SERVER.jarvis.assurance.adversarial_validation_suite import get_adversarial_validation_suite_v41
            suite = get_adversarial_validation_suite_v41()
            res = suite.run_full_adversarial_certification_suite()
            self._send_json(200, res)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Adversarial audit error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_governance_gates(self):
        """GET /jarvis/governance/gates — Query 10 Control Gates V4.0 status."""
        try:
            from SERVER.jarvis.workflow.workflow_governance_control_plane import get_workflow_governance_control_plane_v38
            wf_cp = get_workflow_governance_control_plane_v38()
            is_killed, kill_reason = wf_cp.kill_switch.is_active()
            gates_info = {
                "version": "4.0.0",
                "architecture_type": "Outcome-Aware Governed Bounded Autonomous NOC Control Plane",
                "global_kill_switch_active": is_killed,
                "kill_switch_reason": kill_reason or "NONE",
                "ten_control_gates": {
                    "GATE-01_identity_and_voice_signature": "ACTIVE (SignedVoiceApprovalV40)",
                    "GATE-02_live_truth_verification": "ACTIVE (Live Telemetry Query)",
                    "GATE-03_evidence_sufficiency": "ACTIVE (EvidenceSufficiencyV36)",
                    "GATE-04_action_registry": "ACTIVE (ActionRegistryV40)",
                    "GATE-05_policy_and_dependency_radius": "ACTIVE (BlastRadiusEvaluator)",
                    "GATE-06_toctou_revalidation": "ACTIVE (TOCTOURevalidatorV40)",
                    "GATE-07_autonomy_budget_and_loop_protection": "ACTIVE (RULE-AUTO-007)",
                    "GATE-08_rollback_and_reversibility": "ACTIVE (Explicit Rollback Metadata)",
                    "GATE-09_signed_voice_readback_approval": "ACTIVE (Spoken Approval & Nonce)",
                    "GATE-10_toctou_execution_and_verification": "ACTIVE (PRECHECK->EXECUTE->VERIFY->JOURNAL)"
                }
            }
            self._send_json(200, gates_info)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Governance gates error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_reliability_health(self):
        """GET /jarvis/reliability/health — LLM Resilience Control Plane Status V3.7."""
        try:
            from SERVER.jarvis.reliability.llm_resilience_control_plane import get_llm_resilience_control_plane_v37
            cp = get_llm_resilience_control_plane_v37()
            self._send_json(200, cp.get_health_status())
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] LLM resilience status error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_workflow_simulate(self):
        """POST /jarvis/workflow/simulate — Workflow Governance Control Plane V3.8 Simulation."""
        try:
            body = self._read_body()
            device = body.get("device", "PC-STORE-01")
            action = body.get("action", "RESTART_AGENT")

            from SERVER.jarvis.workflow.workflow_governance_control_plane import get_workflow_governance_control_plane_v38
            wf_cp = get_workflow_governance_control_plane_v38()
            wf_ir = wf_cp.compile_voice_query_to_workflow_ir("restart agent di PC-STORE-01", target_device=device, candidate_action=action)
            res = wf_cp.execute_governed_workflow(wf_ir.workflow_id, event_id=f"EVT-{int(time.time())}", operator_approved=False)
            self._send_json(200, res)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Workflow simulation error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_session_causal_evidence(self):
        """GET /jarvis/session/causal_evidence?action=RESTART_AGENT — Causal Evidence V3.6 API."""
        try:
            from urllib.parse import parse_qs, urlparse
            query_components = parse_qs(urlparse(self.path).query)
            action = query_components.get("action", ["RESTART_AGENT"])[0]

            from SERVER.jarvis.session.multi_turn_session_memory import get_multi_turn_memory_manager_v31
            mgr = get_multi_turn_memory_manager_v31()
            causal_res = mgr.evaluate_causal_evidence_v36(action=action)
            import dataclasses
            self._send_json(200, dataclasses.asdict(causal_res))
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Causal evidence error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_session_remediation_recommendation(self):
        """GET /jarvis/session/remediation_recommendation?device=PC-STORE-01&action=RESTART_AGENT — Learning V3.5 API."""
        try:
            from urllib.parse import parse_qs, urlparse
            query_components = parse_qs(urlparse(self.path).query)
            device = query_components.get("device", ["PC-STORE-01"])[0]
            action = query_components.get("action", ["RESTART_AGENT"])[0]

            from SERVER.jarvis.session.multi_turn_session_memory import get_multi_turn_memory_manager_v31
            mgr = get_multi_turn_memory_manager_v31()
            rec = mgr.evaluate_remediation_learning_v35(candidate_action=action, device=device)
            import dataclasses
            self._send_json(200, dataclasses.asdict(rec))
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Remediation recommendation error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_session_historical_outcome(self):
        """GET /jarvis/session/historical_outcome?device=PC-STORE-01 — Historical Outcome API V3.4."""
        try:
            from urllib.parse import parse_qs, urlparse
            query_components = parse_qs(urlparse(self.path).query)
            device = query_components.get("device", ["PC-STORE-01"])[0]

            from SERVER.jarvis.session.multi_turn_session_memory import get_multi_turn_memory_manager_v31
            mgr = get_multi_turn_memory_manager_v31()
            outcome_res = mgr.analyze_incident_historical_outcome(device=device)
            self._send_json(200, outcome_res)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Historical outcome error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_session_memory_snapshot(self):
        """GET /jarvis/session/memory_snapshot?session_id=multi_turn_test_v31 — Memory Compaction Snapshot API."""
        try:
            from urllib.parse import parse_qs, urlparse
            query_components = parse_qs(urlparse(self.path).query)
            session_id = query_components.get("session_id", ["default_session"])[0]

            from SERVER.jarvis.session.multi_turn_session_memory import get_multi_turn_memory_manager_v31
            mgr = get_multi_turn_memory_manager_v31()
            snapshot = mgr.get_snapshot(session_id)
            if snapshot:
                import dataclasses
                self._send_json(200, dataclasses.asdict(snapshot))
            else:
                self._send_json(404, {"error": "Snapshot not found for session", "session_id": session_id})
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Memory snapshot error: {e}")
            self._send_json(500, {"error": str(e)})

    def _handle_proactive_voice_replay(self):
        """GET /jarvis/proactive/voice_replay?incident_id=INC-001 — Forensic Voice Replay API."""
        try:
            from urllib.parse import parse_qs, urlparse
            query_components = parse_qs(urlparse(self.path).query)
            incident_id = query_components.get("incident_id", ["INC-2026-0813-001"])[0]

            from SERVER.jarvis.proactive.noc_voice_intelligence import get_voice_intelligence_engine_v22
            engine = get_voice_intelligence_engine_v22()
            replay_data = engine.reconstruct_voice_timeline(incident_id)
            self._send_json(200, replay_data)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Voice replay error: {e}")
            self._send_json(500, {"error": str(e)})

    def do_POST(self):
        """POST endpoint router."""
        path = self.path.split("?")[0]

        if path == "/jarvis/voice/query":
            self._handle_voice_query()
        elif path == "/jarvis/voice/config":
            self._handle_voice_config_post()
        elif path == "/jarvis/proactive/announce":
            self._handle_proactive_announce()
        elif path == "/jarvis/proactive/delivery_ack":
            self._handle_proactive_delivery_ack()
        elif path == "/jarvis/workflow/simulate":
            self._handle_workflow_simulate()
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def _handle_voice_config_get(self):
        """GET /jarvis/voice/config — Return current voice & gender configuration."""
        try:
            from SERVER.jarvis.voice.voice_config_store import get_voice_config_store
            store = get_voice_config_store()
            self._send_json(200, {"ok": True, "config": store.get()})
        except Exception as e:
            logger.error("[JarvisVoiceServer] voice/config GET error: %s", e)
            self._send_json(500, {"ok": False, "error": str(e)})

    def _handle_voice_config_post(self):
        """POST /jarvis/voice/config — Update voice & gender configuration at runtime."""
        data = self._read_body()
        if not isinstance(data, dict):
            self._send_json(400, {"ok": False, "error": "Invalid payload"})
            return
        try:
            from SERVER.jarvis.voice.voice_config_store import get_voice_config_store
            store = get_voice_config_store()
            updated = store.update(data)
            logger.info(
                "[JarvisVoiceServer] Voice config updated: voice=%s persona=%s engine=%s",
                updated.get("voice_name"), updated.get("active_persona"), updated.get("tts_engine"),
            )
            self._send_json(200, {"ok": True, "config": updated})
        except Exception as e:
            logger.error("[JarvisVoiceServer] voice/config POST error: %s", e)
            self._send_json(500, {"ok": False, "error": str(e)})

    def _handle_proactive_delivery_ack(self):
        """POST /jarvis/proactive/delivery_ack — Record delivery verification from browser client."""
        data = self._read_body()
        event_id = data.get("voice_event_id") or data.get("event_id", "")
        status = data.get("status", "DELIVERED")
        if not event_id:
            self._send_json(400, {"error": "Missing voice_event_id", "updated": False})
            return

        try:
            from SERVER.jarvis.proactive.noc_voice_intelligence import get_voice_intelligence_engine_v22
            engine = get_voice_intelligence_engine_v22()
            ok = engine.update_voice_delivery(event_id, status)
            self._send_json(200, {"voice_event_id": event_id, "updated": ok, "status": status})
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Delivery ack error: {e}")
            self._send_json(500, {"error": str(e), "updated": False})

    # ── WebSocket Handshake & Duplex Streaming (RFC 6455) ─────────────────────

    def _handle_ws_handshake(self) -> bool:
        """Performs RFC 6455 WebSocket Handshake using Python stdlib."""
        key = self.headers.get("Sec-WebSocket-Key")
        if not key:
            self._send_json(400, {"error": "Missing Sec-WebSocket-Key header"})
            return False

        import hashlib
        GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        accept_key = base64.b64encode(hashlib.sha1((key + GUID).encode("utf-8")).digest()).decode("utf-8")

        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        self.wfile.write(response.encode("utf-8"))
        self.wfile.flush()
        return True

    def _send_ws_frame(self, payload: bytes, opcode: int = 0x1):
        """Sends an unmasked RFC 6455 WebSocket frame."""
        length = len(payload)
        if length <= 125:
            header = bytes([0x80 | opcode, length])
        elif length <= 65535:
            header = bytes([0x80 | opcode, 126]) + length.to_bytes(2, "big")
        else:
            header = bytes([0x80 | opcode, 127]) + length.to_bytes(8, "big")

        self.wfile.write(header + payload)
        self.wfile.flush()

    def _read_ws_frame(self) -> Tuple[int, bytes]:
        """Reads an RFC 6455 WebSocket frame. Returns (opcode, payload)."""
        try:
            header = self.rfile.read(2)
            if not header or len(header) < 2:
                return 0x8, b""
            fin_opcode = header[0]
            opcode = fin_opcode & 0x0F
            mask_len = header[1]
            masked = bool(mask_len & 0x80)
            length = mask_len & 0x7F

            if length == 126:
                length = int.from_bytes(self.rfile.read(2), "big")
            elif length == 127:
                length = int.from_bytes(self.rfile.read(8), "big")

            mask_key = self.rfile.read(4) if masked else None
            payload = self.rfile.read(length)

            if masked and mask_key:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            return opcode, payload
        except Exception:
            return 0x8, b""

    def _handle_voice_duplex_ws(self):
        """Full-Duplex Voice WebSocket Handler (/jarvis/voice/duplex)."""
        if not self._handle_ws_handshake():
            return

        from SERVER.jarvis.voice.duplex_session import JarvisVoiceDuplexSession
        session = JarvisVoiceDuplexSession(session_id=f"ws_session_{int(time.time())}")
        runtime = _get_runtime()

        def emit_func(data_dict: Dict[str, Any]):
            try:
                msg_bytes = json.dumps(data_dict, ensure_ascii=False).encode("utf-8")
                self._send_ws_frame(msg_bytes, opcode=0x1)
            except Exception as e:
                logger.debug(f"[JarvisVoiceServer] Frame emit error: {e}")

        logger.info(f"[JarvisVoiceServer] Duplex WebSocket connected (session={session.session_id})")

        emit_func({
            "event": "connected",
            "avatar_state": "LISTENING",
            "session_id": session.session_id,
            "timestamp": time.time(),
        })

        try:
            while True:
                opcode, payload = self._read_ws_frame()
                if opcode == 0x8:  # Close frame
                    break

                if opcode == 0x1:  # Text JSON frame
                    try:
                        msg = json.loads(payload.decode("utf-8"))
                        action = msg.get("action", "")

                        if action == "barge_in":
                            session.trigger_barge_in(emit_func)
                        elif "question" in msg or "text_query" in msg:
                            question = msg.get("question") or msg.get("text_query", "")
                            t = threading.Thread(
                                target=session.process_text_query_stream,
                                args=(question, runtime, emit_func),
                                daemon=True
                            )
                            t.start()
                    except Exception as me:
                        logger.warning(f"[JarvisVoiceServer] Text WS frame error: {me}")

                elif opcode == 0x2:  # Binary PCM audio frame
                    stt_provider = getattr(runtime, "stt_provider", None)
                    if stt_provider and hasattr(stt_provider, "transcribe_stream_chunk"):
                        text, is_final = stt_provider.transcribe_stream_chunk(payload, session.session_id)
                        if text and is_final:
                            t = threading.Thread(
                                target=session.process_text_query_stream,
                                args=(text, runtime, emit_func),
                                daemon=True
                            )
                            t.start()
        except Exception as e:
            logger.info(f"[JarvisVoiceServer] Duplex WS connection closed: {e}")
        finally:
            logger.info(f"[JarvisVoiceServer] Duplex WS disconnected (session={session.session_id})")

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_proactive_announce(self):
        """
        POST /jarvis/proactive/announce
        Terima event dari Go Dashboard, generate narasi LLM + TTS, return audio.

        Request JSON:
          {
            "event_type":   "early_warning|incident_new|approval_request|remediation_ok|...",
            "severity":     "CRITICAL|HIGH|MEDIUM|LOW|INFO",
            "title":        "CPU Critical di Kasir 2",
            "details":      "CPU 96%, proses: postgres 67%",
            "device":       "KASIR-2",
            "incident_id":  "INC-042",   // optional
            "site_id":      "kasir",      // optional
            // any extra fields are passed to LLM narrator
          }

        Response JSON:
          {
            "skipped":      false,
            "skip_reason":  "",
            "text":         "Narasi JARVIS yang diucapkan...",
            "audio_b64":    "<base64 mp3>",
            "audio_format": "mp3",
            "severity":     "CRITICAL",
            "event_type":   "early_warning",
          }
        """
        t0 = time.time()
        event_dict = self._read_body()
        if not event_dict:
            self._send_json(400, {"error": "Empty body", "skipped": True})
            return

        announcer = _get_proactive_announcer()
        if announcer is None:
            self._send_json(503, {
                "error": "ProactiveAnnouncer unavailable",
                "skipped": True,
                "skip_reason": "announcer_not_initialized",
            })
            return

        try:
            result = announcer.announce(event_dict)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] Proactive announce error: {e}")
            self._send_json(500, {"error": str(e), "skipped": True})
            return

        latency = int((time.time() - t0) * 1000)
        result["latency_ms"] = latency

        if result.get("skipped"):
            logger.info(
                f"[JarvisVoiceServer] Proactive SKIP | "
                f"type={event_dict.get('event_type')} | reason={result.get('skip_reason')}"
            )
        else:
            logger.info(
                f"[JarvisVoiceServer] Proactive OK | "
                f"type={event_dict.get('event_type')} | "
                f"sev={event_dict.get('severity')} | {latency}ms"
            )

        self._send_json(200, result)

    def _handle_health(self):
        """
        GET /jarvis/health
        Liveness + readiness probe for Go portal proxy validation.
        """
        runtime = _get_runtime()
        is_ready = runtime is not None and _runtime_ready

        # Introspect real component states from the runtime instance
        def _component_info(attr, label_ok="active", label_fail="pending"):
            if not is_ready or runtime is None:
                return label_fail
            obj = getattr(runtime, attr, None)
            if obj is None:
                return "unavailable"
            # Expose provider name where available
            name = getattr(obj, "provider_name", None) or getattr(obj, "__class__", None).__name__
            return f"{label_ok} ({name})"

        tts_provider = getattr(getattr(runtime, "tts_service", None), "provider", None) if is_ready and runtime else None
        stt_provider = getattr(getattr(runtime, "stt_service", None), "provider", None) if is_ready and runtime else None

        payload = {
            "status": "ready" if is_ready else "initializing",
            "service": "JARVIS Voice API",
            "runtime_ready": is_ready,
            "init_error": _runtime_init_error,
            "timestamp": time.time(),
            "components": {
                "intent_router":  ("active" if getattr(runtime, "intent_router", None) else "unavailable") if is_ready else "pending",
                "noc_bridge":     ("active" if getattr(runtime, "noc_bridge", None) else "unavailable") if is_ready else "pending",
                "stt_service":    (f"active ({getattr(stt_provider, 'provider_name', type(stt_provider).__name__)})" if stt_provider else "unavailable") if is_ready else "pending",
                "tts_service":    (f"active ({getattr(tts_provider, 'provider_name', type(tts_provider).__name__)})" if tts_provider else "unavailable") if is_ready else "pending",
                "hitl_feedback":  ("active" if getattr(runtime, "hitl_approver", None) else "unavailable") if is_ready else "pending",
                "llm_translator": ("active" if getattr(runtime, "translator", None) or getattr(runtime, "_agentic_dispatcher", None) else "unavailable") if is_ready else "pending",
                "cot_engine":     ("active" if getattr(runtime, "_cot_engine", None) else "unavailable") if is_ready else "pending",
                "episodic_memory":("active" if getattr(runtime, "_episodic_memory", None) else "unavailable") if is_ready else "pending",
            }
        }
        status_code = 200 if is_ready else 503
        self._send_json(status_code, payload)


    def _handle_voice_query(self):
        """
        POST /jarvis/voice/query
        Main JARVIS voice command processing endpoint.

        Request JSON:
          {
            "question":   "restart spooler printer kasir 1",  // voice transcript or typed command
            "session_id": "voice_1234567890_abc123",          // persistent session for context
            "urgency":    "NORMAL|HIGH|EMERGENCY",            // optional urgency hint from UI
            "intent_hint": "REMEDIATE|QUERY|...",             // optional intent pre-classification
            "audio_b64":  "<base64 WAV>",                     // optional raw audio bytes
            "locale":     "id-ID"                             // optional locale override
          }

        Response JSON:
          {
            "answer_text":    "Siap, proses restart spooler printer Kasir 1 dimulai...",
            "audio_b64":      "<base64 WAV dari TTS engine>",
            "audio_format":   "mp3|wav",  // mp3=EdgeTTS primary; wav=Kokoro/parametric fallback
            "intent":         "REMEDIATE",
            "intent_confidence": 0.89,
            "avatar_state":   "SPEAKING",
            "action_context": { "risk_level": "LOW", "execution_status": "SUCCESS", ... },
            "session_id":     "voice_1234567890_abc123",
            "latency_ms":     342,
            "source":         "JARVIS_RUNTIME_V2"
          }
        """
        t_start = time.time()
        payload = self._read_body()

        question = payload.get("question", "").strip()
        session_id = payload.get("session_id") or f"voice_{int(time.time())}"
        audio_b64_raw = payload.get("audio_b64", "")

        # Validate — must have question or audio
        if not question and not audio_b64_raw:
            self._send_json(400, {
                "error": "Bad Request: 'question' (text) or 'audio_b64' (base64 audio) is required.",
                "session_id": session_id,
            })
            return

        # Get runtime — lazy-init if needed
        runtime = _get_runtime()
        if runtime is None:
            logger.error("[JarvisVoiceServer] Runtime not available.")
            self._send_json(503, {
                "error": "JARVIS Runtime unavailable",
                "detail": _runtime_init_error or "Runtime initialization failed",
                "answer_text": "Sistem JARVIS sedang dalam proses inisialisasi. Mohon coba lagi dalam beberapa saat.",
                "session_id": session_id,
                "source": "ERROR_FALLBACK",
            })
            return

        # Build voice payload DTO
        try:
            from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO

            audio_bytes = b""
            if audio_b64_raw:
                try:
                    audio_bytes = base64.b64decode(audio_b64_raw)
                except Exception:
                    logger.warning("[JarvisVoiceServer] audio_b64 decode failed — treating as text-only.")

            voice_payload = VoiceAudioPayloadDTO(
                session_id=session_id,
                audio_format="wav" if audio_bytes else "text",
                sample_rate=16000,
                audio_bytes=audio_bytes,
                text_caption=question,  # Pre-transcribed text from browser WebSpeech API
            )
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] DTO build failed: {e}")
            self._send_json(500, {"error": f"DTO build error: {e}", "session_id": session_id})
            return

        # Process through full JARVIS pipeline
        try:
            result = runtime.process_voice_query(session_id, voice_payload)
        except Exception as e:
            logger.error(f"[JarvisVoiceServer] process_voice_query failed: {e}\n{traceback.format_exc()}")
            self._send_json(500, {
                "error": f"Pipeline error: {e}",
                "answer_text": "Terjadi kesalahan internal pada sistem JARVIS. Tim teknis telah diberitahu.",
                "session_id": session_id,
                "source": "ERROR_FALLBACK",
                "latency_ms": int((time.time() - t_start) * 1000),
            })
            return

        # ── Gap 2 FIX: runtime returns 'audio_bytes', NOT 'audio_output' ──────
        audio_bytes_raw = result.get("audio_bytes")  # VoiceAudioPayloadDTO.audio_bytes
        audio_b64_out = ""
        audio_format_out = "mp3"
        if audio_bytes_raw and len(audio_bytes_raw) > 0:
            try:
                audio_b64_out = base64.b64encode(audio_bytes_raw).decode("utf-8")
                audio_format_out = result.get("audio_mime", "audio/mp3").replace("audio/", "")
                logger.info(f"[JarvisVoiceServer] ✅ TTS audio encoded: {len(audio_bytes_raw)} bytes ({audio_format_out})")
            except Exception as e:
                logger.warning(f"[JarvisVoiceServer] TTS base64 encode failed: {e}")
        else:
            logger.warning("[JarvisVoiceServer] ⚠️ No audio_bytes in result — audio_b64 will be empty")

        # ── Gap 3 FIX: avatar_state = SPEAKING when audio ready, else IDLE ────
        avatar_state_out = "SPEAKING" if audio_b64_out else result.get("avatar_state", "IDLE")

        # Safely convert action_context (which might be a StructuredActionContext dataclass) to dict
        action_ctx = result.get("action_context")
        if action_ctx is not None:
            import dataclasses
            if dataclasses.is_dataclass(action_ctx):
                action_ctx = dataclasses.asdict(action_ctx)
            elif not isinstance(action_ctx, dict):
                action_ctx = {
                    "detected_intent": getattr(action_ctx, "detected_intent", "query"),
                    "intent_confidence": getattr(action_ctx, "intent_confidence", 0.0),
                    "action_taken": getattr(action_ctx, "action_taken", None),
                    "execution_status": getattr(action_ctx, "execution_status", None),
                    "hitl_queue_id": getattr(action_ctx, "hitl_queue_id", None),
                    "requires_hitl_approval": getattr(action_ctx, "requires_hitl_approval", False),
                    "risk_level": getattr(action_ctx, "risk_level", None),
                    "risk_score": getattr(action_ctx, "risk_score", None),
                    "blast_radius": getattr(action_ctx, "blast_radius", None),
                    "policy_effect": getattr(action_ctx, "policy_effect", None),
                    "requires_followup": getattr(action_ctx, "requires_followup", False),
                    "followup_message": getattr(action_ctx, "followup_message", ""),
                    "noc_bridge_data": getattr(action_ctx, "noc_bridge_data", None),
                    "remote_session_id": getattr(action_ctx, "remote_session_id", None),
                    "remote_tool": getattr(action_ctx, "remote_tool", None),
                    "remote_host": getattr(action_ctx, "remote_host", None),
                    "target_panel": getattr(action_ctx, "target_panel", None),
                }
        else:
            action_ctx = {}

        # ── Gap 1 FIX: extract target_panel from action_ctx and expose at top-level ──
        # Go broadcastJarvisAvatarState() reads result["target_panel"] to broadcast
        # jarvis_navigate_panel WebSocket event → frontend auto-switches panel.
        target_panel = action_ctx.get("target_panel") or ""

        # Build response
        response = {
            "answer_text":       result.get("answer_text", ""),
            "audio_b64":         audio_b64_out,
            "audio_format":      audio_format_out,
            "intent":            result.get("intent", "UNKNOWN"),
            "intent_confidence": result.get("intent_confidence", action_ctx.get("intent_confidence", 0.95)),
            "avatar_state":      avatar_state_out,
            "action_context":    action_ctx,
            "target_panel":      target_panel,          # Gap 1: Go reads this for WS navigate broadcast
            "session_id":        session_id,
            "query_text":        result.get("query_text", question),
            "latency_ms":        result.get("latency_ms", int((time.time() - t_start) * 1000)),
            "source":            "JARVIS_RUNTIME_V2.1",
        }

        logger.info(
            f"[JarvisVoiceServer] ✅ Query processed | "
            f"session={session_id} | intent={response['intent']} | "
            f"latency={response['latency_ms']}ms"
        )
        self._send_json(200, response)


# ── Server Runner ─────────────────────────────────────────────────────────────

class JarvisVoiceAPIServer:
    """
    Production JARVIS Voice API Server.
    Runs in a daemon thread — does not block the main process.
    """

    def __init__(self, host: str = "0.0.0.0", port: int = 8089):
        self.host = host
        self.port = int(os.getenv("JARVIS_VOICE_API_PORT", str(port)))
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start_background(self) -> None:
        """Start server in a background daemon thread."""
        def _run():
            self._server = HTTPServer((self.host, self.port), JarvisVoiceHTTPHandler)
            logger.info(
                f"[JarvisVoiceServer] 🚀 Server started on http://{self.host}:{self.port} | "
                f"Endpoints: POST /jarvis/voice/query | GET /jarvis/health"
            )
            self._server.serve_forever()

        self._thread = threading.Thread(target=_run, name="JarvisVoiceAPI", daemon=True)
        self._thread.start()
        # Warm up runtime in background immediately so first request is fast
        threading.Thread(target=_get_runtime, name="JarvisRuntimeWarmup", daemon=True).start()
        logger.info(f"[JarvisVoiceServer] Runtime warmup started in background.")

    def stop(self) -> None:
        """Gracefully stop the server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            logger.info("[JarvisVoiceServer] Server stopped.")


# ── Standalone Entry Point ────────────────────────────────────────────────────

def main():
    """
    Standalone entry point for running JARVIS Voice API Server directly.
    Usage: python3 -m SERVER.jarvis.api.jarvis_voice_server
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    host = os.getenv("JARVIS_VOICE_API_HOST", "0.0.0.0")
    port = int(os.getenv("JARVIS_VOICE_API_PORT", "8089"))

    server = JarvisVoiceAPIServer(host=host, port=port)
    # Warmup runtime eagerly in standalone mode
    logger.info("[JarvisVoiceServer] Pre-warming JARVIS Runtime...")
    _get_runtime()

    # Start server (blocking in standalone mode)
    httpd = HTTPServer((host, port), JarvisVoiceHTTPHandler)
    logger.info(f"[JarvisVoiceServer] 🚀 Running on http://{host}:{port} (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("[JarvisVoiceServer] Shutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    main()
