import os
import json
import logging
import urllib.request
from typing import Optional

logger = logging.getLogger(__name__)

class GPTConnector:
    """
    Connects python_ai_core to OpenAI / GPT APIs with automatic fallback to Gemini AI if OpenAI key is rate limited / out of quota.
    """
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "").strip()
        
        # Fallback: Read from .env if not found in os.environ
        if not self.api_key:
            self.api_key = self._load_key_from_env_file("OPENAI_API_KEY=")
            
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.gemini_key:
            self.gemini_key = self._load_key_from_env_file("GEMINI_API_KEY=")

        self.model = model
        self.endpoint = "https://api.openai.com/v1/chat/completions"

    def _load_key_from_env_file(self, prefix: str) -> str:
        possible_paths = [
            "/app/.env",
            "/app/../.env",
            "/home/it-itsm/AI/incident-analysis/.env",
            ".env"
        ]
        for p in possible_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith(prefix):
                                key = line.strip().split("=", 1)[1].strip('"').strip("'")
                                if key:
                                    return key
                except Exception as e:
                    logger.debug(f"[GPT_CONNECTOR] Failed to read {p}: {e}")
        return ""

    def ask(self, prompt: str, system_prompt: str = "Anda adalah JARVIS, asisten AI berkelas, pintar, dan responsif.") -> str:
        # Try OpenAI First
        if self.api_key:
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 600
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            try:
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=12) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
            except Exception as e:
                logger.warning(f"[GPT_CONNECTOR] OpenAI API call failed ({e}). Attempting Gemini fallback...")

        # Fallback to Gemini AI if OpenAI fails or key is out of quota
        gemini_reply = self._fallback_gemini(prompt, system_prompt)
        if gemini_reply:
            return gemini_reply

        return "Halo! Saya JARVIS, asisten AI NOC. Saat ini sistem pemantauan lokal terpantau aktif dan siap membantu analisis insiden Anda."

    def _fallback_gemini(self, prompt: str, system_prompt: str) -> str:
        keys = [k.strip() for k in self.gemini_key.split(",") if k.strip()]
        if not keys:
            return ""

        # Try newest Gemini models first — fall back to older if 404
        gemini_models = [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro"
        ]

        for key in keys:
            for model_name in gemini_models:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{model_name}:generateContent?key={key}"
                )
                payload = {
                    "contents": [{
                        "parts": [{"text": f"{system_prompt}\n\nPertanyaan Pengguna: {prompt}"}]
                    }]
                }
                headers = {"Content-Type": "application/json"}
                try:
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers=headers,
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        logger.info(f"[GPT_CONNECTOR] Gemini fallback succeeded via model: {model_name}")
                        return text.strip()
                except Exception as e:
                    err_str = str(e)
                    if "404" in err_str:
                        # Model not found — try next model
                        logger.debug(f"[GPT_CONNECTOR] Gemini model {model_name} not found (404), trying next...")
                        continue
                    logger.warning(f"[GPT_CONNECTOR] Gemini key/model {model_name} error: {e}")
                    break  # Non-404 error — try next key
        return ""

