"""
Unit Tests: P0-1 BM25 Production Fix
====================================
Tests for:
  - RAGEngine._sanitize_fts_query()
  - RAGEngine._build_fts_query_tokens()
  - RAGEngine.query_bm25_search() (DB calls mocked)

Run:
    python3 -m unittest tests.unit.test_bm25_production_fix -v
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Make sure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)


class TestSanitizeFtsQuery(unittest.TestCase):
    """Tests for RAGEngine._sanitize_fts_query()."""

    def setUp(self):
        from engines.rag_engine import RAGEngine
        self.engine = RAGEngine.__new__(RAGEngine)

    def test_removes_single_quotes(self):
        result = self.engine._sanitize_fts_query("printer's spooler")
        self.assertNotIn("'", result)
        self.assertIn("printer", result)
        self.assertIn("spooler", result)

    def test_removes_double_quotes(self):
        result = self.engine._sanitize_fts_query('"offline" device')
        self.assertNotIn('"', result)
        self.assertIn("offline", result)

    def test_removes_fts_special_chars(self):
        """All FTS special chars must be stripped to prevent tsquery injection."""
        special_queries = [
            "cpu & high",
            "printer | spooler",
            "!critical",
            "server:8080",
            "(kasir OR gudang)",
            "BGP*",
        ]
        for q in special_queries:
            result = self.engine._sanitize_fts_query(q)
            for char in "&|!:*()'\"":
                self.assertNotIn(char, result,
                    f"char '{char}' found in sanitized: '{result}' (from '{q}')")

    def test_removes_control_characters(self):
        result = self.engine._sanitize_fts_query("cpu\x00high\x1fmem")
        self.assertNotIn("\x00", result)
        self.assertNotIn("\x1f", result)
        self.assertIn("cpu", result)
        self.assertIn("mem", result)

    def test_collapses_multiple_whitespace(self):
        result = self.engine._sanitize_fts_query("cpu   high   usage")
        self.assertEqual("cpu high usage", result)

    def test_truncates_to_300_chars(self):
        long_query = "a " * 200  # 400 chars
        result = self.engine._sanitize_fts_query(long_query)
        self.assertLessEqual(len(result), 300)

    def test_empty_string(self):
        result = self.engine._sanitize_fts_query("")
        self.assertEqual("", result)

    def test_technical_noc_terms_preserved(self):
        """Critical NOC terms must survive sanitization."""
        q = "CPU RAM BGP OSPF VLAN kasir spooler RDP SLA NATS"
        result = self.engine._sanitize_fts_query(q)
        for term in ["CPU", "RAM", "BGP", "kasir", "spooler", "SLA", "NATS"]:
            self.assertIn(term, result, f"Term '{term}' missing from sanitized result: {result}")


class TestBuildFtsQueryTokens(unittest.TestCase):
    """Tests for RAGEngine._build_fts_query_tokens()."""

    def setUp(self):
        from engines.rag_engine import RAGEngine
        self.engine = RAGEngine.__new__(RAGEngine)

    def test_basic_query(self):
        result = self.engine._build_fts_query_tokens("cpu high kasir")
        self.assertIn("cpu", result)
        self.assertIn("kasir", result)
        self.assertIn("|", result)

    def test_filters_indonesian_stop_words(self):
        result = self.engine._build_fts_query_tokens("cpu dan RAM yang tinggi")
        token_list = [t.strip() for t in result.split("|")]
        self.assertNotIn("dan", token_list, f"'dan' found in tokens: {token_list}")
        self.assertNotIn("yang", token_list, f"'yang' found in tokens: {token_list}")
        self.assertIn("cpu", result)

    def test_filters_english_stop_words(self):
        result = self.engine._build_fts_query_tokens("the server is offline and critical")
        token_list = [t.strip() for t in result.split("|")]
        self.assertNotIn("the", token_list)
        self.assertNotIn("is", token_list)
        self.assertNotIn("and", token_list)
        self.assertIn("server", result)
        self.assertIn("offline", result)
        self.assertIn("critical", result)

    def test_filters_short_tokens(self):
        result = self.engine._build_fts_query_tokens("a b c cpu")
        tokens = [t.strip() for t in result.split("|")]
        for t in tokens:
            self.assertGreaterEqual(len(t.strip()), 2, f"Short token found: '{t}'")

    def test_respects_max_tokens(self):
        query = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo"
        result = self.engine._build_fts_query_tokens(query, max_tokens=8)
        tokens = [t.strip() for t in result.split("|")]
        self.assertLessEqual(len(tokens), 8)

    def test_fallback_on_all_stop_words(self):
        """If all tokens are stop words, should still return something non-empty."""
        result = self.engine._build_fts_query_tokens("dan atau yang di ke")
        self.assertIsNotNone(result)
        self.assertGreater(len(result.strip()), 0)

    def test_empty_query_no_exception(self):
        try:
            result = self.engine._build_fts_query_tokens("")
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Empty query raised: {e}")

    def test_noc_technical_query_all_terms_present(self):
        q = "CPU kasir spooler offline critical"
        result = self.engine._build_fts_query_tokens(q)
        for term in ["cpu", "kasir", "spooler", "offline", "critical"]:
            self.assertIn(term, result, f"'{term}' missing from tokens: {result}")

    def test_uses_pipe_separator(self):
        result = self.engine._build_fts_query_tokens("cpu spooler offline")
        self.assertIn("|", result)

    def test_special_chars_cleaned_before_tokenize(self):
        result = self.engine._build_fts_query_tokens("cpu & ram | !disk")
        self.assertNotIn("&", result)
        self.assertNotIn("!", result)


class TestQueryBm25SearchMocked(unittest.TestCase):
    """Tests for RAGEngine.query_bm25_search() with mocked DB connection."""

    def setUp(self):
        from engines.rag_engine import RAGEngine
        self.RAGEngine = RAGEngine
        self.engine = RAGEngine.__new__(RAGEngine)
        # Apply class-level constants manually
        self.engine._FTS_CONFIG = RAGEngine._FTS_CONFIG
        self.engine._INDONESIAN_STOP_WORDS = RAGEngine._INDONESIAN_STOP_WORDS
        self.engine._FTS_SPECIAL_CHARS = RAGEngine._FTS_SPECIAL_CHARS
        # Mock connection
        self.mock_conn = MagicMock()
        self.engine.conn = self.mock_conn

    def _cursor(self, rows=None, raises=None):
        c = MagicMock()
        c.__enter__ = MagicMock(return_value=c)
        c.__exit__ = MagicMock(return_value=False)
        if raises:
            c.execute.side_effect = raises
        else:
            c.fetchall.return_value = rows or []
        return c

    def test_happy_path_returns_dicts(self):
        row = {"incident_id": "KB-SOP-001", "title": "CPU High",
               "symptoms": "CPU > 95%", "root_cause": "runaway",
               "resolution": "kill process", "bm25_score": 0.42}
        self.mock_conn.cursor.return_value = self._cursor([row])
        results = self.engine.query_bm25_search("cpu high")
        self.assertEqual(1, len(results))
        self.assertEqual("KB-SOP-001", results[0]["incident_id"])

    def test_empty_query_no_db_call(self):
        results = self.engine.query_bm25_search("")
        self.assertEqual([], results)
        self.mock_conn.cursor.assert_not_called()

    def test_whitespace_query_no_db_call(self):
        results = self.engine.query_bm25_search("   ")
        self.assertEqual([], results)
        self.mock_conn.cursor.assert_not_called()

    def test_no_connection_returns_empty(self):
        self.engine.conn = None
        results = self.engine.query_bm25_search("cpu high")
        self.assertEqual([], results)

    def test_fts_failure_triggers_ilike_fallback(self):
        fallback_row = {
            "incident_id": "KB-GLD-002", "title": "Printer Offline",
            "symptoms": "printer stuck", "root_cause": "spooler hung",
            "resolution": "restart spooler", "bm25_score": 0.1,
        }
        primary = self._cursor(raises=Exception("FTS error"))
        fallback = self._cursor([fallback_row])
        self.mock_conn.cursor.side_effect = [primary, fallback]

        results = self.engine.query_bm25_search("printer offline")
        self.assertEqual(1, len(results))
        self.assertEqual("KB-GLD-002", results[0]["incident_id"])

    def test_both_fail_returns_empty(self):
        self.mock_conn.cursor.side_effect = [
            self._cursor(raises=Exception("FTS fail")),
            self._cursor(raises=Exception("ILIKE fail")),
        ]
        results = self.engine.query_bm25_search("printer offline")
        self.assertEqual([], results)

    def test_fts_config_is_simple(self):
        """REGRESSION GUARD: config must be 'simple', not 'english'."""
        self.assertEqual("simple", self.RAGEngine._FTS_CONFIG)

    def test_result_has_required_keys(self):
        row = {"incident_id": "KB-SOP-002", "title": "Memory Leak",
               "symptoms": "RAM high", "root_cause": "leak",
               "resolution": "restart", "bm25_score": 0.35}
        self.mock_conn.cursor.return_value = self._cursor([row])
        results = self.engine.query_bm25_search("ram memory leak")
        self.assertEqual(1, len(results))
        for k in ("incident_id", "title", "symptoms", "root_cause", "resolution", "bm25_score"):
            self.assertIn(k, results[0])


class TestBm25NocScenarios(unittest.TestCase):
    """Integration scenarios for realistic NOC queries (no DB)."""

    def setUp(self):
        from engines.rag_engine import RAGEngine
        self.engine = RAGEngine.__new__(RAGEngine)

    def _tokens(self, q):
        return self.engine._build_fts_query_tokens(q)

    def test_scenario_cpu_kasir(self):
        t = self._tokens("CPU kasir sangat tinggi melebihi 95%")
        self.assertIn("cpu", t)
        self.assertIn("kasir", t)

    def test_scenario_printer_offline(self):
        t = self._tokens("printer kasir offline tidak bisa print")
        self.assertIn("printer", t)
        self.assertIn("kasir", t)
        self.assertIn("offline", t)

    def test_scenario_bgp_flapping(self):
        t = self._tokens("BGP session flapping ke router core")
        token_list = [x.strip() for x in t.split("|")]
        self.assertNotIn("ke", token_list, "'ke' is stop word, must be filtered")
        self.assertIn("bgp", t)
        self.assertIn("flapping", t)

    def test_scenario_sql_injection_neutralized(self):
        malicious = "cpu; DROP TABLE knowledge_vectors --"
        t = self._tokens(malicious)
        self.assertNotIn(";", t)  # semicolon is now in _FTS_SPECIAL_CHARS
        self.assertNotIn("DROP TABLE", t)

    def test_scenario_version_number(self):
        t = self._tokens("nginx version 1.24.0 error 502")
        self.assertIn("nginx", t)
        self.assertIn("error", t)
        self.assertIn("502", t)

    def test_scenario_all_stopwords_no_crash(self):
        try:
            r = self._tokens("dan atau yang di ke dari ini itu")
            self.assertIsNotNone(r)
        except Exception as e:
            self.fail(f"All-stop-word query crashed: {e}")

    def test_regression_guard_class_constant(self):
        """This test must never be removed — regression guard for P0-1 fix."""
        from engines.rag_engine import RAGEngine
        self.assertEqual(
            "simple", RAGEngine._FTS_CONFIG,
            "REGRESSION P0-1: _FTS_CONFIG was changed back to 'english' or other config! "
            "This breaks BM25 for Bahasa Indonesia and technical NOC terms."
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
