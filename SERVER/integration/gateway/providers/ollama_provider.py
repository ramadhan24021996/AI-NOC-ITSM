"""
providers/ollama_provider.py
----------------------------
Local Ollama Offline Fallback Inference Provider for NOC Integration Gateway.
"""
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("gateway.providers.ollama")


class OllamaProvider:
    """Local Ollama Inference Provider."""

    def __init__(self, base_url: Optional[str] = None, model: str = "qwen2.5-coder:7b"):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model

    def is_available(self) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def query(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Synchronous query to local Ollama API."""
        try:
            import urllib.request
            import json

            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt or "You are a local offline NOC reasoning agent.",
                "stream": False,
            }
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                text = res_data.get("response", "")
                return {
                    "provider": "ollama",
                    "status": "SUCCESS",
                    "model": self.model,
                    "response": text,
                    "confidence": 0.85,
                }
        except Exception as e:
            logger.warning(f"[OllamaProvider] Query failed: {e}")
            return {
                "provider": "ollama",
                "status": "FALLBACK",
                "error": str(e),
                "confidence": 0.0,
            }
