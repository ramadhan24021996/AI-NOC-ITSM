"""
providers/gemini_provider.py
----------------------------
Google Gemini Multi-Modal & Tool Calling Provider for NOC Integration Gateway.
"""
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("gateway.providers.gemini")


class GeminiProvider:
    """Google Gemini Multi-Modal Inference Provider."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-pro"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model

    def is_configured(self) -> bool:
        return bool(self.api_key and not self.api_key.startswith("YOUR_"))

    def query(self, prompt: str, system_prompt: str = "") -> Dict[str, Any]:
        """Synchronous query to Gemini API."""
        if not self.is_configured():
            return {
                "provider": "gemini",
                "status": "FALLBACK",
                "model": self.model,
                "response": "Gemini API key not configured. Using rule engine fallback.",
                "confidence": 0.0,
            }

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return {
                "provider": "gemini",
                "status": "SUCCESS",
                "model": self.model,
                "response": response.text if hasattr(response, "text") else str(response),
                "confidence": 0.95,
            }
        except Exception as e:
            logger.error(f"[GeminiProvider] Query failed: {e}")
            return {
                "provider": "gemini",
                "status": "ERROR",
                "error": str(e),
                "confidence": 0.0,
            }
