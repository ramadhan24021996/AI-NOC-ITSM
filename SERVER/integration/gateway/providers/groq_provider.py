"""
providers/groq_provider.py
--------------------------
Groq Ultra-Fast LPU Inference Provider for NOC Integration Gateway.
"""
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("gateway.providers.groq")


class GroqProvider:
    """Groq Ultra-Fast Inference Provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("YOUR_"))

    def query(self, prompt: str, system_prompt: str = "", temperature: float = 0.1) -> Dict[str, Any]:
        """Synchronous query to Groq LPU API."""
        if not self.is_configured():
            return {
                "provider": "groq",
                "status": "FALLBACK",
                "model": self.model,
                "response": "Groq API key not configured. Using rule engine fallback.",
                "confidence": 0.0,
            }

        try:
            import urllib.request
            import json

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt or "You are an ultra-fast NOC triage reasoning agent."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": temperature,
            }
            req = urllib.request.Request(
                f"{self.base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                choice = res_data.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content", "")
                return {
                    "provider": "groq",
                    "status": "SUCCESS",
                    "model": self.model,
                    "response": text,
                    "confidence": 0.90,
                }
        except Exception as e:
            logger.error(f"[GroqProvider] Query failed: {e}")
            return {
                "provider": "groq",
                "status": "ERROR",
                "error": str(e),
                "confidence": 0.0,
            }
