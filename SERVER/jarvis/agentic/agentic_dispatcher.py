"""
SERVER.jarvis.agentic.agentic_dispatcher — JARVIS Agentic ReAct Dispatcher
===========================================================================
Pilar 1 + 2: LLM Tool Calling + Deep Multi-Turn Memory dalam satu engine.

ARSITEKTUR HYBRID DISPATCH (ZERO DELETION):
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENTIC DISPATCHER                               │
│                                                                     │
│  Query → FastTrack Check → (bypass) → Handler langsung             │
│                  ↓ (bukan fast-track)                               │
│          Build Gemini messages[] dari conversation history          │
│                  ↓                                                  │
│      Gemini Tool Calling (memilih tool dari JarvisToolRegistry)     │
│                  ↓                                                  │
│    Execute via existing handler (regex/rules tetap berjalan)        │
│                  ↓                                                  │
│         ProactiveReasoner → insight 1-2 kalimat                     │
│                  ↓                                                  │
│      Update ConversationMemory (full sliding window 10 turn)        │
│                  ↓                                                  │
│             Fallback ke IntentRouter lama jika Gemini gagal         │
└─────────────────────────────────────────────────────────────────────┘

Layer Keandalan:
  Layer 1 (FastTrack): Deterministik, < 50ms, zero LLM
  Layer 2 (AgenticDispatcher): Gemini Tool Calling, ~500-800ms
  Layer 3 (IntentRouter Fallback): Existing regex rules, instant
  Layer 4 (GatewayFallback): UnifiedGateway RAG, ~1-2s
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from SERVER.jarvis.agentic.tool_registry import JarvisToolRegistry
from SERVER.jarvis.agentic.proactive_reasoner import ProactiveReasoner
from SERVER.contracts.schemas import StructuredActionContext

logger = logging.getLogger("jarvis.agentic.dispatcher")

# ── Fast-Track Patterns (bypass LLM — instant response) ──────────────────────
# Perintah deterministik ini tidak perlu LLM untuk dipahami
FAST_TRACK_PATTERNS: Dict[str, Tuple[str, str]] = {
    # pattern_keyword: (action_taken, panel_id or command)
    "volume up":         ("VOLUME_UP",   ""),
    "volume down":       ("VOLUME_DOWN", ""),
    "mute":              ("MUTE",        ""),
    "unmute":            ("UNMUTE",      ""),
    "buka panel network":("OPEN_PANEL",  "network"),
    "buka panel printer":("OPEN_PANEL",  "printer"),
    "buka panel pchealth":("OPEN_PANEL", "pchealth"),
    "buka jarvis":       ("OPEN_PANEL",  "jarvis-voice"),
    "minimize":          ("MINIMIZE_UI", ""),
    "maximize":          ("MAXIMIZE_UI", ""),
}

# Tool → Intent mapping untuk update action_context
TOOL_TO_INTENT: Dict[str, str] = {
    "get_live_incidents":    "GET_INCIDENTS_LIVE",
    "get_host_metrics":      "GET_HOST_METRICS_LIVE",
    "get_printer_status":    "GET_PRINTER_STATUS",
    "execute_remediation":   "EXECUTE_REMEDIATION",
    "search_knowledge":      "SEARCH_KNOWLEDGE_RAG",
    "open_dashboard_panel":  "OPEN_DASHBOARD_PANEL",
    "get_system_health":     "GET_SYSTEM_HEALTH",
    "get_network_topology":  "GET_NETWORK_TOPOLOGY",
    "answer_directly":       "DIRECT_ANSWER",
    "assign_field_engineer": "ASSIGN_FIELD_ENGINEER",
}

# ReAct Loop configuration
MAX_REACT_STEPS: int = 3       # Maks iterasi tool calling per query (cegah infinite loop)
REACT_STEP_TIMEOUT: float = 8.0  # Timeout per Gemini call dalam detik

# System prompt untuk Gemini sebagai JARVIS orchestrator
JARVIS_ORCHESTRATOR_PROMPT = """\
Kamu adalah JARVIS, Senior AI NOC Copilot untuk tim IT Enterprise.
Kamu memiliki akses ke berbagai tool real-time untuk membantu operator NOC.

ATURAN PENTING:
1. SELALU gunakan tool yang paling tepat untuk setiap permintaan operator.
2. Jika operator menyebut device/insiden dari percakapan sebelumnya tanpa menyebutnya ulang, 
   gunakan konteks percakapan untuk mengisi parameter tool secara otomatis.
3. Untuk pertanyaan yang tidak memerlukan data real-time (sapaan, identitas, penjelasan umum),
   gunakan tool 'answer_directly' dengan jawaban dalam Bahasa Indonesia humanis.
4. Untuk perintah remediasi (restart, flush, kill, clear), SELALU gunakan 'execute_remediation'.
5. Jangan menebak-nebak jika tidak ada konteks yang cukup — gunakan 'answer_directly' 
   dan minta klarifikasi dari operator.
6. Jawab dalam Bahasa Indonesia santai namun profesional.
7. Ketika menggunakan 'answer_directly', teks jawabannya harus plain text tanpa markdown.
"""


class AgenticDispatcher:
    """
    ReAct Loop Engine: Gemini Tool Calling → Existing Handler Execution.
    
    Dispatcher ini TIDAK menggantikan handler yang ada — ia adalah lapisan
    orchestrator yang memutuskan HANDLER MANA yang dipanggil berdasarkan
    pemahaman natural language dari Gemini.
    """

    def __init__(
        self,
        runtime_instance: Any,  # JarvisPresentationRuntime
        tool_registry: Optional[JarvisToolRegistry] = None,
        proactive_reasoner: Optional[ProactiveReasoner] = None,
    ):
        self.runtime = runtime_instance
        self.registry = tool_registry or JarvisToolRegistry()
        self.reasoner = proactive_reasoner or ProactiveReasoner()
        self._gemini_api_key = self._load_gemini_key()
        self._model = "gemini-1.5-flash"
        self._enabled = bool(self._gemini_api_key)

        if self._enabled:
            logger.info("[AgenticDispatcher] ✅ Gemini Tool Calling ACTIVE — Hybrid Dispatch enabled.")
        else:
            logger.warning("[AgenticDispatcher] ⚠️ Gemini key not found — fallback-only mode.")

    def _load_gemini_key(self) -> str:
        """Load Gemini API key dari environment atau .env file."""
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or key in ("YOUR_GEMINI_API_KEY_HERE", ""):
            for env_path in ["/app/.env", ".env", "../.env"]:
                try:
                    with open(env_path) as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith("GEMINI_API_KEY="):
                                val = line.split("=", 1)[1].strip().strip('"\'')
                                if val and val != "YOUR_GEMINI_API_KEY_HERE":
                                    return val
                except (FileNotFoundError, PermissionError):
                    continue
        return key if key and key != "YOUR_GEMINI_API_KEY_HERE" else ""

    # ─── Public API ───────────────────────────────────────────────────────────

    def dispatch(
        self,
        query_text: str,
        session_id: str,
        action_context: StructuredActionContext,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        context_dict: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], StructuredActionContext]:
        """
        Main dispatch method. Dipanggil dari jarvis_presentation_runtime.py
        sebagai alternatif untuk _dispatch_by_intent() lama.

        Args:
            query_text:           Query operator yang sudah dinormalisasi
            session_id:           ID sesi aktif
            action_context:       StructuredActionContext untuk diisi oleh handler
            conversation_history: List pesan [{role, content}] dari ConversationManager
            context_dict:         Dict konteks sesi (last_device, last_incident, dll)

        Returns:
            Tuple (answer_text | None, action_context).
            answer_text = None adalah sinyal ke runtime untuk menggunakan legacy IntentRouter.
        """
        t0 = time.time()

        # ── Layer 1: Fast-Track Check (< 1ms, zero LLM) ─────────────────────
        ft_result = self._fast_track_check(query_text, action_context)
        if ft_result is not None:
            return ft_result

        # ── Layer 2: Gemini Tool Calling ─────────────────────────────────────
        if self._enabled:
            try:
                answer, action_context = self._gemini_tool_calling(
                    query_text, conversation_history or [], context_dict or {}, action_context
                )
                elapsed_ms = int((time.time() - t0) * 1000)
                logger.info(
                    "[AgenticDispatcher] Agentic dispatch completed in %dms | action: %s",
                    elapsed_ms, action_context.action_taken
                )
                return answer, action_context
            except Exception as e:
                logger.warning(
                    "[AgenticDispatcher] Gemini tool calling failed (%s) — falling through to intent router.",
                    e
                )

        # ── Layer 3: Fallback ke existing IntentRouter (zero regression) ─────
        logger.info("[AgenticDispatcher] Using legacy intent router fallback.")
        return None, action_context  # Sinyal ke runtime untuk gunakan _dispatch_by_intent lama

    # ─── Fast-Track ───────────────────────────────────────────────────────────

    def _fast_track_check(
        self, query: str, action_context: StructuredActionContext
    ) -> Optional[Tuple[str, StructuredActionContext]]:
        """Cek apakah query cocok dengan fast-track pattern deterministik."""
        q = query.lower().strip()
        for pattern, (action, param) in FAST_TRACK_PATTERNS.items():
            if pattern in q:
                action_context.action_taken = action
                action_context.execution_status = "SUCCESS"
                if action == "OPEN_PANEL" and hasattr(self.runtime, "browser_control"):
                    try:
                        self.runtime.browser_control.open_panel(param)
                    except Exception:
                        pass
                return f"[FAST-TRACK] {action} executed.", action_context
        return None

    # ─── Hybrid ReAct Loop (Fast-Track + Deep Reasoning) ─────────────────────

    def _gemini_tool_calling(
        self,
        query: str,
        history: List[Dict[str, str]],
        ctx: Dict[str, Any],
        action_context: StructuredActionContext,
    ) -> Tuple[str, StructuredActionContext]:
        """
        Hybrid ReAct Loop: Reason → Act → Observe → Reason → … → Final Answer

        Alur per iterasi:
          1. Kirim messages[] + tool schema ke Gemini
          2. Jika Gemini pilih tool → eksekusi → append hasil ke messages[] → ulangi
          3. Jika Gemini hasilkan teks → STOP → teks itu adalah jawaban final yang
             sudah mensintesis SEMUA data dari semua tool sebelumnya
          4. Setelah MAX_REACT_STEPS tanpa STOP → gabung semua hasil manual

        Dibanding single-pass:
          + Query kompleks bisa panggil 2-3 tool berurutan
          + Gemini melihat HASIL setiap tool sebelum memutuskan langkah berikut
          + Jawaban final mensintesis SEMUA data yang dikumpulkan
          + Fallback: jika semua step gagal, kembalikan akumulasi hasil tool
        """
        tool_schemas = self.registry.get_all_schemas()
        messages = self._build_messages(query, history, ctx)

        # Tracking lintas iterasi
        collected_results: List[str] = []        # Semua teks hasil tool
        last_tool_name: str = "answer_directly"  # Tool terakhir yang dipanggil
        step = 0

        while step < MAX_REACT_STEPS:
            step += 1
            logger.info(
                "[AgenticDispatcher] 🤔 ReAct Step %d/%d | messages=%d",
                step, MAX_REACT_STEPS, len(messages)
            )

            # ── REASON: Panggil Gemini ────────────────────────────────────────
            gemini_response = self._call_gemini_with_tools(messages, tool_schemas)

            if not gemini_response:
                logger.warning("[AgenticDispatcher] Gemini empty at step %d", step)
                break

            # ── CHECK: Gemini beri jawaban teks langsung? (STOP condition) ────
            direct_text = self._extract_text_response(gemini_response)
            if direct_text:
                logger.info(
                    "[AgenticDispatcher] ✅ ReAct STOP step %d — final answer synthesized from %d tool(s).",
                    step, len(collected_results)
                )
                action_context.action_taken = TOOL_TO_INTENT.get(
                    last_tool_name, "AGENTIC_SYNTHESIS"
                )
                action_context.execution_status = "SUCCESS"

                # ProactiveReasoner insight setelah jawaban final
                if self.reasoner.is_enabled:
                    insight = self.reasoner.generate_insight(
                        tool_name=last_tool_name,
                        tool_result_text=direct_text,
                        user_query=query,
                        context=ctx,
                    )
                    if insight:
                        direct_text = direct_text.rstrip() + "\n\n💡 " + insight

                return direct_text, action_context

            # ── ACT: Parse tool call dari response ────────────────────────────
            tool_call = self._parse_tool_call(gemini_response)
            if not tool_call:
                logger.warning("[AgenticDispatcher] No tool call and no text at step %d", step)
                break

            tool_name = tool_call.get("name", "answer_directly")
            tool_args = tool_call.get("args", {})
            last_tool_name = tool_name
            logger.info(
                "[AgenticDispatcher] 🔧 ReAct Act step %d: tool='%s' args=%s",
                step, tool_name, tool_args
            )

            # ── OBSERVE: Eksekusi tool dan kumpulkan hasil ────────────────────
            tool_result_text, action_context = self._execute_tool(
                tool_name, tool_args, query, ctx, action_context
            )
            collected_results.append(f"[Tool: {tool_name}]\n{tool_result_text}")

            # answer_directly adalah terminal — tidak perlu iterasi lanjut
            if tool_name == "answer_directly":
                final = tool_args.get("answer", tool_result_text)
                action_context.execution_status = "SUCCESS"
                return final, action_context

            # ── FEED BACK: Append model tool call + function result ke messages ─
            # Gemini API format: model menyatakan functionCall,
            # lalu kita kirim functionResponse sebagai "user" turn
            model_turn = gemini_response.get("candidates", [{}])[0].get("content", {})
            messages.append(model_turn)   # Model menyatakan tool call
            messages.append({             # Kita memberikan hasil observasi
                "role": "user",
                "parts": [{
                    "functionResponse": {
                        "name": tool_name,
                        "response": {"result": tool_result_text[:2000]}  # Cap agar tidak overflow
                    }
                }]
            })

        # ── FALLBACK SYNTHESIS: Loop selesai tanpa STOP text ─────────────────
        # Gemini tidak menghasilkan jawaban teks — gabungkan semua hasil tool
        if collected_results:
            logger.info(
                "[AgenticDispatcher] ReAct exhausted %d steps — manual synthesis from %d results.",
                step, len(collected_results)
            )
            combined = "\n\n".join(collected_results)
            action_context.execution_status = "SUCCESS"
            action_context.action_taken = "REACT_SYNTHESIS"

            if self.reasoner.is_enabled:
                insight = self.reasoner.generate_insight(
                    tool_name="multi_tool_analysis",
                    tool_result_text=combined,
                    user_query=query,
                    context=ctx,
                )
                if insight:
                    combined = combined.rstrip() + "\n\n💡 " + insight

            return combined, action_context

        raise RuntimeError("ReAct loop produced no results after all steps")



    def _build_messages(
        self, query: str, history: List[Dict[str, str]], ctx: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Build Gemini messages array dari conversation history + query baru.
        Ini adalah implementasi Deep Multi-Turn Memory (Pilar 2).
        Format: [{"role": "user/model", "parts": [{"text": ...}]}]
        """
        messages = []

        # System instruction dimasukkan sebagai pesan pertama dari model
        # (Gemini tidak punya system role terpisah di API v1beta)
        ctx_note = ""
        if ctx.get("last_device"):
            ctx_note += f"\n[KONTEKS] Perangkat terakhir dibahas: {ctx['last_device']}"
        if ctx.get("last_incident"):
            ctx_note += f"\n[KONTEKS] Insiden terakhir: {ctx['last_incident']}"
        if ctx.get("last_action"):
            ctx_note += f"\n[KONTEKS] Aksi terakhir dieksekusi: {ctx['last_action']}"

        system_msg = JARVIS_ORCHESTRATOR_PROMPT
        if ctx_note:
            system_msg += f"\n\nKONTEKS PERCAKAPAN AKTIF:{ctx_note}"

        # Inject system prompt sebagai user message pertama (Gemini format)
        messages.append({
            "role": "user",
            "parts": [{"text": system_msg}]
        })
        messages.append({
            "role": "model",
            "parts": [{"text": "Siap! Saya JARVIS, siap membantu operasional NOC Anda."}]
        })

        # Inject conversation history (Pilar 2: sliding window 10 turn)
        for turn in history[-10:]:
            role = "user" if turn.get("role") == "user" else "model"
            messages.append({
                "role": role,
                "parts": [{"text": turn.get("content", "")}]
            })

        # Query baru dari operator
        messages.append({
            "role": "user",
            "parts": [{"text": query}]
        })

        return messages

    def _call_gemini_with_tools(
        self, messages: List[Dict[str, Any]], tool_schemas: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Panggil Gemini REST API dengan tool schemas."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent?key={self._gemini_api_key}"
        )

        # Build function declarations
        function_declarations = [
            {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"]
            }
            for t in tool_schemas
        ]

        payload = {
            "contents": messages,
            "tools": [{"function_declarations": function_declarations}],
            "tool_config": {"function_calling_config": {"mode": "AUTO"}},
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 500,
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8")[:200]
            except Exception:
                pass
            logger.warning("[AgenticDispatcher] Gemini HTTP %s: %s | %s", e.code, e.reason, body)
            return None
        except Exception as e:
            logger.warning("[AgenticDispatcher] Gemini request failed: %s", e)
            return None

    def _parse_tool_call(self, response: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse tool call dari Gemini response."""
        try:
            candidates = response.get("candidates", [])
            if not candidates:
                return None
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            for part in parts:
                if "functionCall" in part:
                    fc = part["functionCall"]
                    return {
                        "name": fc.get("name", "answer_directly"),
                        "args": fc.get("args", {})
                    }
        except Exception as e:
            logger.debug("[AgenticDispatcher] Tool call parse error: %s", e)
        return None

    def _extract_text_response(self, response: Dict[str, Any]) -> str:
        """Extract teks respons langsung dari Gemini jika tidak ada tool call."""
        try:
            candidates = response.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "text" in part:
                        return part["text"].strip()
        except Exception:
            pass
        return ""

    # ─── Tool Executors (memanggil handler yang sudah ada) ────────────────────

    def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        query: str,
        ctx: Dict[str, Any],
        action_context: StructuredActionContext,
    ) -> Tuple[str, StructuredActionContext]:
        """
        Route tool call ke handler yang sudah ada.
        Ini adalah inti dari Hybrid Dispatch — semua logic lama tetap berjalan.
        """
        action_context.action_taken = TOOL_TO_INTENT.get(tool_name, tool_name.upper())

        rt = self.runtime  # JarvisPresentationRuntime instance

        try:
            # ── get_live_incidents ────────────────────────────────────────────
            if tool_name == "get_live_incidents":
                return self._tool_get_incidents(args, query, rt, action_context)

            # ── get_host_metrics ─────────────────────────────────────────────
            elif tool_name == "get_host_metrics":
                device = args.get("device_name", "") or ctx.get("last_device", "")
                return self._tool_get_metrics(device, query, rt, action_context)

            # ── get_printer_status ───────────────────────────────────────────
            elif tool_name == "get_printer_status":
                device = args.get("device_name", "") or ctx.get("last_device", "")
                return self._tool_get_printer(device, query, rt, action_context)

            # ── execute_remediation ──────────────────────────────────────────
            elif tool_name == "execute_remediation":
                action_name = args.get("action_name", "")
                device = args.get("device_name", "") or ctx.get("last_device", "")
                incident_id = args.get("incident_id", "") or ctx.get("last_incident", "")
                return self._tool_execute_remediation(action_name, device, incident_id, query, rt, action_context)

            # ── search_knowledge ─────────────────────────────────────────────
            elif tool_name == "search_knowledge":
                search_query = args.get("query", query)
                return self._tool_search_knowledge(search_query, rt, action_context)

            # ── open_dashboard_panel ─────────────────────────────────────────
            elif tool_name == "open_dashboard_panel":
                panel_id = args.get("panel_id", "overview")
                return self._tool_open_panel(panel_id, rt, action_context)

            # ── get_system_health ────────────────────────────────────────────
            elif tool_name == "get_system_health":
                return self._tool_get_system_health(rt, action_context)

            # ── get_network_topology ─────────────────────────────────────────
            elif tool_name == "get_network_topology":
                return self._tool_get_topology(rt, action_context)

            # ── answer_directly ──────────────────────────────────────────────
            elif tool_name == "answer_directly":
                answer = args.get("answer", "")
                action_context.execution_status = "SUCCESS"
                return answer, action_context

            # ── assign_field_engineer ────────────────────────────────────────
            elif tool_name == "assign_field_engineer":
                return self._tool_assign_engineer(args, query, rt, action_context)

            else:
                logger.warning("[AgenticDispatcher] Unknown tool '%s' — using gateway fallback.", tool_name)
                return self._fallback_gateway(query, rt, action_context)

        except Exception as e:
            logger.error("[AgenticDispatcher] Tool '%s' execution error: %s", tool_name, e)
            action_context.execution_status = "FAILED"
            return f"Maaf Bosku, ada error saat menjalankan {tool_name}: {e}", action_context

    # ─── Individual Tool Implementations ──────────────────────────────────────

    def _tool_get_incidents(self, args, query, rt, action_context):
        """Panggil existing handler untuk live incidents."""
        from SERVER.jarvis.command.intent_router import IntentResult, JarvisIntent
        intent_result = IntentResult(intent=JarvisIntent.QUERY, confidence=0.99)
        intent_result.target_device = ""
        persona = rt.persona_reg.get("noc_engineer")
        answer, action_context = rt._handle_query(query, intent_result, persona, action_context)
        # Override action_taken dengan yang lebih spesifik
        if "incident" in (action_context.action_taken or "").lower() or "GET_INCIDENTS" not in (action_context.action_taken or ""):
            action_context.action_taken = "GET_INCIDENTS_LIVE"
        return answer, action_context

    def _tool_get_metrics(self, device, query, rt, action_context):
        """Panggil handler untuk host metrics."""
        from SERVER.jarvis.command.intent_router import IntentResult, JarvisIntent
        intent_result = IntentResult(intent=JarvisIntent.QUERY, confidence=0.99)
        intent_result.target_device = device
        persona = rt.persona_reg.get("noc_engineer")
        # Inject device ke query jika belum ada
        enriched_query = f"{query} {device}".strip() if device and device not in query else query
        answer, action_context = rt._handle_query(enriched_query, intent_result, persona, action_context)
        action_context.action_taken = "GET_HOST_METRICS_LIVE"
        return answer, action_context

    def _tool_get_printer(self, device, query, rt, action_context):
        """Panggil handler untuk printer status."""
        from SERVER.jarvis.command.intent_router import IntentResult, JarvisIntent
        intent_result = IntentResult(intent=JarvisIntent.QUERY, confidence=0.99)
        intent_result.target_device = device
        persona = rt.persona_reg.get("noc_engineer")
        enriched_query = f"status printer {device}".strip() if device else "status printer"
        answer, action_context = rt._handle_query(enriched_query, intent_result, persona, action_context)
        action_context.action_taken = "GET_PRINTER_STATUS"
        return answer, action_context

    def _tool_execute_remediation(self, action_name, device, incident_id, query, rt, action_context):
        """Panggil existing remediation handler — tetap melewati HITL safety gate."""
        from SERVER.jarvis.command.intent_router import IntentResult, JarvisIntent
        intent_result = IntentResult(intent=JarvisIntent.REMEDIATE, confidence=0.99)
        intent_result.target_device = device
        intent_result.target_incident = incident_id
        # Simpan action_name di extracted_entities (field Dict[str,str] yang valid di IntentResult)
        intent_result.extracted_entities["action_name"] = action_name
        session = rt.session_mgr.get_session("agentic-session") or rt.session_mgr.create_session("agentic-session", "voice_user")
        # Inject action_name ke query agar handler regex bisa menangkap intent remediation
        enriched_query = f"{action_name} {device} {incident_id}".strip()
        answer, action_context = rt._handle_remediate(enriched_query, intent_result, "agentic-session", session, action_context)

        return answer, action_context

    def _tool_search_knowledge(self, search_query, rt, action_context):
        """Panggil gateway untuk RAG knowledge search."""
        action_context.action_taken = "SEARCH_KNOWLEDGE_RAG"
        try:
            resp = rt.noc_bridge._get(f"/api/rag/search?q={urllib.parse.quote(search_query)}")
            if resp and resp.success and resp.data:
                results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
                if results:
                    lines = ["📚 KNOWLEDGE BASE RESULTS:"]
                    for i, r in enumerate(results[:3], 1):
                        title = r.get("title", r.get("name", f"Dokumen {i}"))
                        snippet = r.get("snippet", r.get("content", ""))[:200]
                        lines.append(f"  {i}. {title}\n     {snippet}")
                    action_context.execution_status = "SUCCESS"
                    return "\n".join(lines), action_context
        except Exception:
            pass
        # Fallback: cari via gateway
        return self._fallback_gateway(search_query, rt, action_context)

    def _tool_open_panel(self, panel_id, rt, action_context):
        """Buka panel dashboard via browser control."""
        action_context.action_taken = "OPEN_DASHBOARD_PANEL"
        action_context.execution_status = "SUCCESS"
        panel_map = {
            "overview": "p-overview", "pchealth": "p-pchealth",
            "network": "p-network", "printer": "p-printer",
            "rca": "p-rca", "incidents": "p-incidents",
            "ai-governance": "p-gov", "fleet": "p-fleet",
            "training": "p-training", "jarvis-voice": "p-jarvis",
        }
        panel_selector = panel_map.get(panel_id, f"p-{panel_id}")
        try:
            if hasattr(rt, "browser_control") and rt.browser_control:
                rt.browser_control.click_panel(panel_selector)
        except Exception:
            pass
        return f"✅ Panel '{panel_id}' telah dibuka di dashboard.", action_context

    def _tool_get_system_health(self, rt, action_context):
        """Get system health via NOC bridge."""
        action_context.action_taken = "GET_SYSTEM_HEALTH"
        try:
            resp = rt.noc_bridge._get("/api/system/health")
            if resp and resp.success:
                action_context.execution_status = "SUCCESS"
                return resp.summary or "Semua service berjalan normal.", action_context
        except Exception:
            pass
        action_context.execution_status = "PARTIAL"
        return "Status sistem: cek manual diperlukan (bridge tidak merespons).", action_context

    def _tool_get_topology(self, rt, action_context):
        """Get network topology."""
        action_context.action_taken = "GET_NETWORK_TOPOLOGY"
        try:
            resp = rt.noc_bridge._get("/api/topology")
            if resp and resp.success and resp.data:
                action_context.execution_status = "SUCCESS"
                return resp.summary or "Topologi jaringan berhasil diambil.", action_context
        except Exception:
            pass
        action_context.execution_status = "PARTIAL"
        return "Data topologi tidak tersedia saat ini.", action_context

    def _tool_assign_engineer(self, args, query, rt, action_context):
        """Assign field engineer via Telegram dispatcher."""
        action_context.action_taken = "ASSIGN_FIELD_ENGINEER"
        incident_id = args.get("incident_id", "")
        engineer = args.get("engineer_name", "")
        location = args.get("location", "")
        try:
            if hasattr(rt, "field_dispatcher") and rt.field_dispatcher:
                rt.field_dispatcher.dispatch(
                    incident_id=incident_id,
                    engineer_name=engineer,
                    location=location,
                    query=query
                )
                action_context.execution_status = "SUCCESS"
                return f"✅ Teknisi '{engineer}' ditugaskan ke insiden {incident_id} di {location}.", action_context
        except Exception as e:
            logger.warning("[AgenticDispatcher] Field dispatch error: %s", e)
        action_context.execution_status = "FAILED"
        return f"Gagal menugaskan teknisi. Silakan dispatch manual via Telegram.", action_context

    def _fallback_gateway(self, query, rt, action_context):
        """Fallback ke UnifiedGateway jika tidak ada tool yang cocok."""
        action_context.action_taken = "GATEWAY_FALLBACK"
        session = rt.session_mgr.get_session("agentic-fallback") or rt.session_mgr.create_session("agentic-fallback", "voice_user")
        return rt._handle_gateway_fallback(query, "agentic-fallback", session, action_context)
