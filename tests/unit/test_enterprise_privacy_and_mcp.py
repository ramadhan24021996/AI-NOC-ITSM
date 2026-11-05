"""
Unit Tests for Enterprise Privacy Auto-Redaction and MCP Adapter Layer
======================================================================
Tests:
 - PrivacyAutoRedactor (Password, Bearer Token, DB URI, PII Redaction)
 - MCPAdapterGateway (MCP Tool Registration, Anti-Context Rot Selector, Execution)
"""
import unittest
from typing import Dict, Any
from SERVER.security.privacy_redactor import PrivacyAutoRedactor
from SERVER.python_ai_core.adapters.mcp_adapter import MCPAdapterGateway, MCPToolDefinition


class TestEnterprisePrivacyAndMCP(unittest.TestCase):

    def test_privacy_auto_redactor_text(self):
        redactor = PrivacyAutoRedactor()

        # 1. Password Redaction
        text1 = "Jarvis, password DB adalah Secret1234"
        res1 = redactor.redact_text(text1)
        self.assertNotIn("Secret1234", res1)
        self.assertIn("[REDACTED_PASSWORD]", res1)

        # 2. Connection String Redaction
        text2 = "Connect to postgresql://admin:secretpass@127.0.0.1:5432/incident_db"
        res2 = redactor.redact_text(text2)
        self.assertNotIn("secretpass", res2)
        self.assertIn("postgresql://[REDACTED_URI]", res2)

        # 3. Bearer Token Redaction
        text3 = "Authorization Header: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        res3 = redactor.redact_text(text3)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", res3)
        self.assertIn("[REDACTED_TOKEN]", res3)

    def test_privacy_auto_redactor_dict_payload(self):
        redactor = PrivacyAutoRedactor()
        payload: Dict[str, Any] = {
            "user_id": "usr-101",
            "api_key": "sk-proj-secret12345678901234567890",
            "metadata": {
                "db_password": "MySecretPassWord123!",
                "connection": "postgres://user:pass@host:5432/db"
            }
        }
        redacted: Dict[str, Any] = redactor.redact_payload(payload)
        self.assertEqual(redacted["api_key"], "[REDACTED_SENSITIVE_FIELD]")
        self.assertEqual(redacted["metadata"]["db_password"], "[REDACTED_SENSITIVE_FIELD]")
        self.assertIn("[REDACTED_URI]", redacted["metadata"]["connection"])

    def test_mcp_adapter_gateway(self):
        gateway = MCPAdapterGateway()

        # 1. Anti-Context Rot Tool Selector Test
        query = "Tolong ambilkan metrik CPU dan memori dari prometheus"
        selected = gateway.select_relevant_tools(query, top_k=2)
        self.assertGreater(len(selected), 0)
        tool_names = [t.tool_name for t in selected]
        self.assertIn("get_metric_series", tool_names)

        # 2. Tool Execution Test — real subprocess call
        # In CI/test env without npx, this returns FAILED with a meaningful error.
        # In production env with npx + MCP servers, this returns SUCCESS with real output.
        res = gateway.execute_tool("prometheus_mcp", "get_metric_series", {"query": "node_cpu_seconds_total"})
        self.assertEqual(res.server_name, "prometheus_mcp")
        self.assertEqual(res.tool_name, "get_metric_series")
        self.assertIn(res.status, ("SUCCESS", "FAILED"))
        if res.status == "FAILED":
            # Must have a meaningful error message, not None or empty
            self.assertIsNotNone(res.error_message)
            self.assertGreater(len(res.error_message), 0)
        else:
            self.assertIsNotNone(res.output)

        # 3. Non-existent Tool Test
        res_fail = gateway.execute_tool("unknown_mcp", "unknown_tool", {})
        self.assertEqual(res_fail.status, "FAILED")

    def test_llm_voice_command_translator(self):
        from SERVER.jarvis.cognition.llm_command_translator import LLMVoiceCommandTranslator
        translator = LLMVoiceCommandTranslator()

        # Test voice transcript translation
        dto = translator.translate("Jarvis, jervis password DB adalah Secret123 tolong apruf INC-001")
        self.assertIn(dto.intent, ["HITL", "REMEDIATE", "QUERY"])
        self.assertNotIn("Secret123", dto.sanitized_transcript)
        self.assertIn("[REDACTED_PASSWORD]", dto.sanitized_transcript)
        self.assertIn("INC-001", dto.incident_id)
        self.assertIsNotNone(dto.explanation_id)


if __name__ == "__main__":
    unittest.main()
