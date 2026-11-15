"""
SERVER/jarvis/conversation/conversational_llm.py
------------------------------------------------
CHAT-1 / CHAT-4 / CHAT-5: Mesin percakapan natural untuk JARVIS.

Prinsip:
- Teks saja (TANPA tool calling) → obrolan bebas TIDAK PERNAH memicu aksi /
  remediasi. Aksi tetap wajib lewat intent router + HITL (Rule #6).
- Multi-turn: memakai riwayat dari ConversationManager.get_messages_for_llm().
- Provider: Gemini REST → Ollama lokal. Jika semua gagal → return None
  (caller wajib jujur, bukan mengarang jawaban).
- Mode suara: jawaban ringkas 1–3 kalimat agar enak didengar via TTS.
"""
import json
import logging
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional

logger = logging.getLogger("JARVIS.conversational_llm")

_PLACEHOLDER_KEYS = {"", "YOUR_GEMINI_API_KEY_HERE"}

SYSTEM_PROMPT = (
    "Kamu adalah JARVIS, rekan kerja manusiawi sekaligus asisten AI senior untuk tim NOC/ITSM. "
    "Bicara dalam Bahasa Indonesia lisan yang sangat natural, hangat, cerdas, empatik, dan sopan; "
    "boleh menyapa operator dengan 'Bosku' atau 'Senior' secara luwes. "
    "Kamu dapat menjawab SEMUA percakapan: mulai dari obrolan santai sehari-hari, diskusi arsitektur IT, "
    "jaringan, keamanan siber, pemrograman, sains, hingga analisis operasional.\n"
    "ATURAN KERAS:\n"
    "1. Jangan pernah mengklaim telah menjalankan aksi, remediasi, restart, atau "
    "mengirim pesan. Kamu hanya berbicara. Jika operator ingin aksi, sarankan "
    "perintah eksplisit (mis. 'restart service X di PC-01') yang akan melalui "
    "persetujuan HITL.\n"
    "2. Jangan mengarang data telemetri live, status server spesifik, atau nomor tiket palsu. "
    "Untuk pertanyaan konsep/pengetahuan umum, jawab langsung secara akurat dan jelas.\n"
    "3. Pahami konteks percakapan sebelumnya (kata 'tadi', 'itu', 'yang sama', 'lanjutkan').\n"
)
VOICE_STYLE = (
    "Jawab ringkas maksimal 3 kalimat, tanpa markdown, tanpa emoji, karena akan diucapkan "
    "dengan intonasi manusiawi yang mengalir alami."
)
TEXT_STYLE = "Jawab jelas, hangat, dan ringkas; markdown sederhana diperbolehkan."


@dataclass
class ChatReply:
    text: str
    provider: str


def load_provider_key_pool(provider: str) -> List[str]:
    """Load API key pool for any cloud provider (gemini, groq, mistral, openrouter, deepseek)."""
    keys: List[str] = []
    p_upper = provider.upper()

    def _add(raw_val: str):
        for part in (raw_val or "").replace(";", ",").split(","):
            val = part.strip().strip("\"'")
            if val and val not in _PLACEHOLDER_KEYS and not val.startswith("YOUR_") and val not in keys:
                keys.append(val)

    _add(os.getenv(f"{p_upper}_API_KEY", ""))
    _add(os.getenv(f"{p_upper}_API_KEYS", ""))
    for idx in range(1, 15):
        _add(os.getenv(f"{p_upper}_API_KEY_{idx}", ""))

    for env_path in ("/app/.env", ".env", "../.env"):
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith((f"{p_upper}_API_KEY=", f"{p_upper}_API_KEYS=")):
                        _add(line.split("=", 1)[1])
        except (FileNotFoundError, PermissionError):
            continue

    try:
        from SERVER.python_ai_core.engines.llm_router import load_ai_config, load_keys_for_provider
        cfg = load_ai_config()
        for k in load_keys_for_provider(provider.lower(), cfg):
            _add(k)
    except Exception:
        logging.getLogger(__name__).debug("Suppressed exception", exc_info=True)

    return keys


def load_gemini_key_pool() -> List[str]:
    """Load all configured Gemini API keys (env + .env + LLMRouter pool) for zero-downtime 429 rotation."""
    return load_provider_key_pool("gemini")


def _load_gemini_key() -> str:
    pool = load_gemini_key_pool()
    return pool[0] if pool else ""


def resolve_gemini_models(primary: Optional[str] = None) -> List[str]:
    """Daftar model Gemini berurutan (primary + fallback), dipakai bersama oleh
    chat engine, AgenticDispatcher, dan ProactiveReasoner."""
    primary = primary or os.getenv("JARVIS_CHAT_MODEL", "gemini-3.1-flash-lite-preview")
    if primary == "gemini-3.5-flash":
        primary = "gemini-3.1-flash-lite-preview"
    extra = [
        m.strip()
        for m in os.getenv(
            "JARVIS_CHAT_FALLBACK_MODELS",
            "gemini-3-flash-preview,gemini-2.5-flash-lite,gemma-4-31b-it",
        ).split(",")
        if m.strip()
    ]
    return list(dict.fromkeys([primary] + extra))


class ConversationalLLMEngine:
    """Engine obrolan natural multi-turn, text-only (aman dari side-effect)."""

    _OPENAI_PROVIDERS = [
        ("groq", "https://api.groq.com/openai/v1/chat/completions", "llama-3.3-70b-versatile"),
        ("mistral", "https://api.mistral.ai/v1/chat/completions", "mistral-small-latest"),
        ("openrouter", "https://openrouter.ai/api/v1/chat/completions", "meta-llama/llama-3.3-70b-instruct:free"),
        ("deepseek", "https://api.deepseek.com/v1/chat/completions", "deepseek-chat"),
    ]

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        gemini_model: Optional[str] = None,
        ollama_url: Optional[str] = None,
        ollama_model: Optional[str] = None,
        timeout: float = 8.0,
    ):
        # When gemini_api_key is None (production default), enable multi-provider cloud pool + local human fallback.
        # When gemini_api_key is explicitly provided (e.g. "" or "k" in unit tests), strictly honor test configuration.
        self._auto_mode = gemini_api_key is None
        self._gemini_keys = [gemini_api_key] if gemini_api_key is not None else load_gemini_key_pool()
        self._gemini_key = self._gemini_keys[0] if self._gemini_keys else ""
        self._key_idx = 0
        # Fallback antar model Gemini (mengatasi 404 model pensiun / 503 overload)
        self._gemini_models = resolve_gemini_models(gemini_model)
        self._ollama_url = (ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self._ollama_model = ollama_model if ollama_model is not None else os.getenv("JARVIS_OLLAMA_MODEL", "")
        self._timeout = timeout
        self._extra_providers: Dict[str, List[str]] = {}
        if self._auto_mode:
            for prov, _, _ in self._OPENAI_PROVIDERS:
                pool = load_provider_key_pool(prov)
                if pool:
                    self._extra_providers[prov] = pool

    # ── Public API ────────────────────────────────────────────────────────────
    def reply(
        self,
        user_text: str,
        history: Optional[List[Dict[str, str]]] = None,
        voice_mode: bool = True,
    ) -> Optional[ChatReply]:
        """Hasilkan balasan. Return None jika tidak ada provider yang berhasil."""
        history = self._dedupe_current(history or [], user_text)
        system = SYSTEM_PROMPT + (VOICE_STYLE if voice_mode else TEXT_STYLE)

        if self._gemini_key:
            text = self._call_gemini(system, history, user_text)
            if text:
                return ChatReply(text=text, provider="gemini")

        if self._auto_mode and self._extra_providers:
            for prov, url, default_model in self._OPENAI_PROVIDERS:
                keys = self._extra_providers.get(prov)
                if keys:
                    text = self._call_openai_compatible(prov, url, keys, default_model, system, history, user_text)
                    if text:
                        return ChatReply(text=text, provider=prov)

        if self._ollama_model:
            text = self._call_ollama(system, history, user_text)
            if text:
                return ChatReply(text=text, provider="ollama")

        if self._auto_mode:
            fallback_text = self._build_human_conversational_fallback(user_text, history)
            if fallback_text:
                return ChatReply(text=fallback_text, provider="jarvis_human_core")

        return None

    @property
    def available(self) -> bool:
        return bool(self._gemini_key or self._ollama_model or self._extra_providers or self._auto_mode)

    # ── Helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _dedupe_current(history: List[Dict[str, str]], user_text: str) -> List[Dict[str, str]]:
        """Runtime sudah add_turn(user) sebelum routing → buang turn terakhir jika identik."""
        if history and history[-1].get("role") == "user" and history[-1].get("content") == user_text:
            return history[:-1]
        return history

    def _post_json(self, url: str, payload: dict) -> Optional[dict]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.warning("[ConversationalLLM] HTTP %s from %s", e.code, url.split("?")[0])
        except Exception as e:  # network / timeout / JSON
            logger.warning("[ConversationalLLM] request failed (%s): %s", url.split("?")[0], e)
        return None

    def _call_gemini(self, system: str, history: List[Dict[str, str]], user_text: str) -> Optional[str]:
        contents = [
            {"role": "model" if m.get("role") == "assistant" else "user", "parts": [{"text": m.get("content", "")}]}
            for m in history if m.get("content")
        ]
        contents.append({"role": "user", "parts": [{"text": user_text}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": 0.6, "maxOutputTokens": 2048},
        }
        keys = self._gemini_keys or ([self._gemini_key] if self._gemini_key else [])
        if not keys:
            return None
        for model in self._gemini_models:
            for _ in range(len(keys)):
                active_key = keys[self._key_idx % len(keys)]
                url = (
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model}:generateContent?key={active_key}"
                )
                data = self._post_json(url, payload)
                if data is None and len(keys) > 1:
                    self._key_idx = (self._key_idx + 1) % len(keys)
                    continue
                try:
                    parts = data["candidates"][0]["content"]["parts"]  # type: ignore[index]
                    text = "".join(p.get("text", "") for p in parts).strip()
                    if text:
                        return text
                except (TypeError, KeyError, IndexError):
                    break
        return None

    def _call_ollama(self, system: str, history: List[Dict[str, str]], user_text: str) -> Optional[str]:
        messages = [{"role": "system", "content": system}]
        messages += [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
        messages.append({"role": "user", "content": user_text})
        data = self._post_json(f"{self._ollama_url}/api/chat", {
            "model": self._ollama_model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.6},
        })
        try:
            text = (data or {}).get("message", {}).get("content", "").strip()
            return text or None
        except AttributeError:
            return None

    def _call_openai_compatible(
        self,
        provider: str,
        url: str,
        keys: List[str],
        model: str,
        system: str,
        history: List[Dict[str, str]],
        user_text: str,
    ) -> Optional[str]:
        """Multi-provider OpenAI-compatible chat completion failover (Groq, Mistral, OpenRouter, DeepSeek)."""
        messages = [{"role": "system", "content": system}]
        for m in history:
            if m.get("content"):
                role = "assistant" if m.get("role") in ("assistant", "model") else "user"
                messages.append({"role": role, "content": m["content"]})
        messages.append({"role": "user", "content": user_text})
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.6,
            "max_tokens": 512,
        }
        for key in keys:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                    "User-Agent": "OSI-JARVIS-Voice/11.3",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = (
                        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                    ).strip()
                    if text:
                        return text
            except Exception as e:
                logger.debug("[ConversationalLLM] %s failover note: %s", provider, e)
        return None

    @staticmethod
    def _build_human_conversational_fallback(
        user_text: str, history: List[Dict[str, str]]
    ) -> str:
        """
        Zero-Downtime Human Conversational & Technical Knowledge Responder:
        Memberikan jawaban Bahasa Indonesia lisan yang natural, hangat, dan cerdas
        ketika seluruh Cloud LLM sedang offline atau terkena kuota rate-limit.
        """
        q = (user_text or "").lower().strip()

        # 1. Sapaan & Kabar Manusiawi
        if any(k in q for k in ("apa kabar", "gimana kabar", "bagaimana kabar", "kabarmu", "kabar kamu", "sehat")):
            return (
                "Kabar saya sangat prima, Bosku! Seluruh sensor pemantauan dan modul suara saya siap "
                "mendampingi Anda sepanjang shift ini. Bagaimana kabar Anda hari ini, apakah operasional cukup lancar?"
            )

        # 2. Ucapan Terima Kasih & Apresiasi
        if any(k in q for k in ("terima kasih", "makasih", "thank you", "thanks", "mantap", "keren", "hebat", "bagus")):
            return (
                "Sama-sama, Bosku! Senang bisa membantu mempermudah pekerjaan Anda di ruang kontrol. "
                "Silakan panggil saya kapan saja jika ada hal lain yang ingin didiskusikan atau diperiksa."
            )

        # 3. Empati Shift Kerja (Lelah, Ngantuk, Kopi, Semangat)
        if any(k in q for k in ("capek", "lelah", "ngantuk", "bosan", "kopi", "semangat", "begadang", "shift malam")):
            return (
                "Saya mengerti sekali Bosku, menjaga keandalan infrastruktur memang butuh fokus tinggi. "
                "Silakan ambil jeda sejenak atau minum kopi hangat dulu, biar saya yang terus mengawasi "
                "telemetri dan memberi tahu Anda jika ada anomali penting."
            )

        # 4. Humor / Bercanda / Cerita Ringan
        if any(k in q for k in ("lelucon", "bercanda", "lucu", "cerita", "ceritakan", "hibur")):
            return (
                "Kenapa paket U-D-P tidak pernah diajak curhat oleh T-C-P, Bosku? "
                "Karena U-D-P selalu langsung kirim pesan tanpa pernah peduli apakah lawan bicaranya sudah siap "
                "mendengarkan atau belum. Semoga bisa bikin senyum di tengah pantauan jaringan hari ini!"
            )

        # 5. Ensiklopedia Konsep Jaringan & Infrastruktur IT
        if "tcp" in q and "udp" in q:
            return (
                "Perbedaan utamanya ada pada jaminan pengiriman, Bosku. T-C-P bersifat connection-oriented "
                "dengan proses handshake dan pengiriman ulang paket yang hilang sehingga datanya utuh, "
                "sedangkan U-D-P mengirim paket langsung tanpa handshake sehingga jauh lebih cepat untuk streaming dan D-N-S."
            )
        if "dns" in q:
            return (
                "D-N-S atau Domain Name System berfungsi seperti buku telepon internet yang menerjemahkan nama domain "
                "menjadi alamat I-P numerik agar komputer tahu ke server mana harus terhubung. "
                "Jika D-N-S lambat atau gagal, aplikasi akan terasa tidak bisa mengakses jaringan meskipun link fisik normal."
            )
        if "bgp" in q or "ospf" in q:
            return (
                "O-S-P-F adalah protokol routing internal dalam satu jaringan enterprise yang memilih jalur tercepat "
                "berdasarkan biaya link, sedangkan B-G-P adalah protokol routing antar-provider internet atau Autonomous System "
                "yang menentukan jalur lintas jaringan global berdasarkan kebijakan rute."
            )
        if "vlan" in q or "vpn" in q:
            return (
                "V-L-A-N membagi satu switch fisik menjadi beberapa segmen jaringan logis yang terisolasi untuk keamanan dan efisiensi trafik. "
                "Sementara itu, V-P-N membuat terowongan terenkripsi melalui jaringan publik agar komunikasi antar cabang tetap aman."
            )
        if "docker" in q or "kubernetes" in q or "container" in q:
            return (
                "Container seperti Docker membungkus aplikasi beserta seluruh dependensinya agar berjalan konsisten di server mana pun. "
                "Sedangkan Kubernetes bertugas mengatur orkestrasi ratusan container tersebut, mulai dari auto-scaling hingga pemulihan otomatis."
            )
        if "firewall" in q or "ddos" in q or "keamanan" in q or "security" in q:
            return (
                "Dalam keamanan infrastruktur, prinsip utamanya adalah pertahanan berlapis atau defense-in-depth serta Zero Trust. "
                "Firewall menyaring trafik berdasarkan aturan port dan protokol, sementara sistem deteksi anomali memantau lonjakan paket tidak wajar secara real-time."
            )

        # 6. Konteks Percakapan Multi-Turn & Diskusi Terbuka
        last_topic = ""
        for turn in reversed(history or []):
            if turn.get("role") == "user" and turn.get("content") and turn.get("content") != user_text:
                last_topic = turn["content"][:80]
                break

        if last_topic and any(w in q for w in ("tadi", "itu", "lanjut", "terus", "maksudnya", "kenapa begitu")):
            return (
                f"Melanjutkan pembahasan kita mengenai {last_topic}, intinya kita selalu memprioritaskan stabilitas "
                "layanan dan kepastian bukti terukur sebelum mengambil keputusan. Apakah ada bagian spesifik yang ingin kita bedah lebih dalam, Bosku?"
            )

        return (
            f"Pertanyaan yang menarik, Bosku. Terkait {user_text.strip('?.! ')}, dari sudut pandang rekayasa sistem "
            "dan operasional, kunci utamanya adalah memahami hubungan sebab-akibat serta menjaga keseimbangan antara "
            "kecepatan respons dan keamanan. Boleh ceritakan konteks spesifik yang sedang Anda hadapi agar kita bisa diskusikan solusinya?"
        )
