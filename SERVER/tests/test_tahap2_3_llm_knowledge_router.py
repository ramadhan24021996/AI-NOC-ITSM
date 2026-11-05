"""
Tahap 2.3 — LLM & Knowledge Router (Dispatcher Layer) Test Suite
=================================================================
DoD Criteria:
1. LLMDispatcher, RAGDispatcher, EmbeddingDispatcher, ProviderSelector
   dapat diimpor dari SERVER.orchestrator.dispatcher tanpa error.
2. ProviderSelector memilih provider yang benar berdasarkan severity tier.
3. Isolation Rule: dispatcher TIDAK mengimpor python_ai_core secara langsung
   dari luar SERVER.orchestrator (arsitektur wiring terjaga).
4. Dispatchers menggunakan lazy initialization (engine tidak dimuat tanpa dipanggil).
5. EmbeddingDispatcher.embed() menghasilkan vector deterministik (local fallback).
6. ProviderSelector menggunakan routing table yang konsisten dengan LLMRouter.
7. Semua dispatcher 100% backward compatible — tidak ada perubahan pada core engines.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap23LLMKnowledgeRouter(unittest.TestCase):

    # ── Test 1: Import dari dispatcher layer ──────────────────────────────────
    def test_dispatcher_imports(self):
        """Semua komponen Tahap 2.3 dapat diimpor dari SERVER.orchestrator.dispatcher."""
        from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher
        from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher
        from SERVER.orchestrator.dispatcher.embedding_dispatcher import EmbeddingDispatcher
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector, ProviderTier

        self.assertTrue(callable(LLMDispatcher))
        self.assertTrue(callable(RAGDispatcher))
        self.assertTrue(callable(EmbeddingDispatcher))
        self.assertTrue(callable(ProviderSelector))

    # ── Test 2: ProviderSelector — Tier mapping benar ─────────────────────────
    def test_provider_selector_tier_mapping(self):
        """ProviderSelector memetakan severity score ke tier yang benar."""
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector, ProviderTier
        sel = ProviderSelector()

        self.assertEqual(sel.score_to_tier(95), ProviderTier.CRITICAL)
        self.assertEqual(sel.score_to_tier(85), ProviderTier.CRITICAL)
        self.assertEqual(sel.score_to_tier(84), ProviderTier.MEDIUM)
        self.assertEqual(sel.score_to_tier(60), ProviderTier.MEDIUM)
        self.assertEqual(sel.score_to_tier(59), ProviderTier.LOW)
        self.assertEqual(sel.score_to_tier(0), ProviderTier.LOW)

    # ── Test 3: ProviderSelector — Primary provider dipilih jika tersedia ─────
    def test_provider_selector_selects_primary(self):
        """ProviderSelector memilih primary provider jika tersedia."""
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector
        sel = ProviderSelector()

        # CRITICAL tier → primary: deepseek
        result = sel.select(severity_score=90, available_providers=["deepseek", "gemini", "groq"])
        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.model, "deepseek-reasoner")
        self.assertEqual(result.tier.value, "critical")
        self.assertEqual(result.latency_budget_ms, 15000)
        self.assertEqual(result.token_budget, 128000)

    # ── Test 4: ProviderSelector — Fallback jika primary tidak tersedia ───────
    def test_provider_selector_fallback_chain(self):
        """ProviderSelector jatuh ke fallback jika primary tidak tersedia."""
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector
        sel = ProviderSelector()

        # CRITICAL tier, deepseek tidak tersedia → fallback ke gemini
        result = sel.select(severity_score=90, available_providers=["gemini"])
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(result.model, "gemini-1.5-pro")

    # ── Test 5: ProviderSelector — Rule engine fallback jika semua offline ────
    def test_provider_selector_all_offline_rule_engine(self):
        """ProviderSelector jatuh ke rule_engine jika semua provider offline."""
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector
        sel = ProviderSelector()

        result = sel.select(severity_score=70, available_providers=[])
        self.assertEqual(result.provider, "rule_engine")

    # ── Test 6: ProviderSelector — describe_routing_table format benar ────────
    def test_provider_selector_routing_table_structure(self):
        """Routing table memiliki struktur yang benar untuk semua tier."""
        from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector
        sel = ProviderSelector()

        table = sel.describe_routing_table()
        for tier in ("critical", "medium", "low"):
            self.assertIn(tier, table)
            self.assertIn("primary", table[tier])
            self.assertIn("fallback_chain", table[tier])
            self.assertIn("latency_budget_ms", table[tier])
            self.assertIn("token_budget", table[tier])

    # ── Test 7: EmbeddingDispatcher — local embedding adalah list float[768] ──
    def test_embedding_dispatcher_local_fallback(self):
        """EmbeddingDispatcher.embed() menghasilkan vector deterministik panjang 768."""
        from SERVER.orchestrator.dispatcher.embedding_dispatcher import EmbeddingDispatcher
        disp = EmbeddingDispatcher()

        text = "CPU spike 98% pada PEKALONGAN-PC-01 selama 15 menit."
        vector = disp.embed(text)

        self.assertIsInstance(vector, list)
        self.assertEqual(len(vector), 768)
        self.assertTrue(all(isinstance(v, float) for v in vector))

        # Deterministic: hasil harus sama untuk input yang sama
        vector2 = disp.embed(text)
        self.assertEqual(vector, vector2)

    # ── Test 8: EmbeddingDispatcher — lazy initialization (engine None awalnya)
    def test_embedding_dispatcher_lazy_init(self):
        """EmbeddingDispatcher tidak memuat engine sebelum dipanggil."""
        from SERVER.orchestrator.dispatcher.embedding_dispatcher import EmbeddingDispatcher
        disp = EmbeddingDispatcher()
        # _engine harus None sebelum dipanggil
        self.assertIsNone(disp._engine)
        # Setelah dipanggil, engine dimuat
        disp.embed("test input")
        self.assertIsNotNone(disp._engine)

    # ── Test 9: LLMDispatcher — lazy initialization (router None awalnya) ─────
    def test_llm_dispatcher_lazy_init(self):
        """LLMDispatcher tidak memuat LLMRouter sebelum dipanggil."""
        from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher
        disp = LLMDispatcher()
        # _router harus None sebelum dipanggil
        self.assertIsNone(disp._router)

    # ── Test 10: RAGDispatcher — lazy initialization (engine None awalnya) ────
    def test_rag_dispatcher_lazy_init(self):
        """RAGDispatcher tidak memuat RAGEngine sebelum dipanggil."""
        from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher
        disp = RAGDispatcher()
        self.assertIsNone(disp._engine)

    # ── Test 11: Architecture isolation — dispatcher tidak diimpor di jarvis ──
    def test_no_direct_llm_import_in_jarvis(self):
        """
        Aturan Arsitektur: SERVER/jarvis TIDAK BOLEH mengimpor python_ai_core secara langsung.
        Seluruh akses AI harus melalui SERVER/orchestrator/dispatcher.
        """
        import ast
        jarvis_root = os.path.join(PROJECT_ROOT, "SERVER", "jarvis")
        violations = []
        for root, _, files in os.walk(jarvis_root):
            for f in files:
                if f.endswith(".py"):
                    fp = os.path.join(root, f)
                    with open(fp, encoding="utf-8") as fh:
                        try:
                            tree = ast.parse(fh.read(), filename=fp)
                        except SyntaxError:
                            continue
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.Import, ast.ImportFrom)):
                            module = getattr(node, "module", "") or ""
                            for alias in getattr(node, "names", []):
                                full = f"{module}.{alias.name}" if module else alias.name
                                if "python_ai_core" in full or "llm_router" in full:
                                    violations.append(f"{fp}: imports {full}")
        self.assertEqual(
            violations, [],
            f"Architecture isolation violated! Jarvis imported AI engine directly:\n"
            + "\n".join(violations)
        )

    # ── Test 12: Backward compat — core engines PUBLIC API tetap tidak berubah─
    def test_core_engine_public_api_unchanged(self):
        """
        Backward compatibility: python_ai_core/engines/llm_router.py dan rag_engine.py
        masih memiliki fungsi publik yang sama (get_router, get_rag_engine, LLMRouter, RAGEngine).
        """
        import importlib
        import sys

        # Sementara tambahkan path python_ai_core ke sys.path untuk test ini
        core_root = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
        if core_root not in sys.path:
            sys.path.insert(0, core_root)
        engines_root = os.path.join(core_root, "engines")
        if engines_root not in sys.path:
            sys.path.insert(0, engines_root)

        import ast

        llm_router_path = os.path.join(engines_root, "llm_router.py")
        with open(llm_router_path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        # Include AsyncFunctionDef because execute_with_retry is declared as `async def`
        defined_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }

        # Pastikan semua public interface yang digunakan dispatcher masih ada
        self.assertIn("LLMRouter", defined_names, "LLMRouter class must remain in llm_router.py")
        self.assertIn("get_router", defined_names, "get_router() must remain in llm_router.py")
        self.assertIn("execute_with_retry", defined_names, "execute_with_retry() must remain")
        self.assertIn("execute_groq", defined_names, "execute_groq() must remain")
        self.assertIn("execute_deepseek", defined_names, "execute_deepseek() must remain")

        rag_engine_path = os.path.join(engines_root, "rag_engine.py")
        with open(rag_engine_path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())

        # Include AsyncFunctionDef because embed_and_query_async is declared as `async def`
        defined_names_rag = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertIn("RAGEngine", defined_names_rag, "RAGEngine class must remain in rag_engine.py")
        self.assertIn("get_rag_engine", defined_names_rag, "get_rag_engine() must remain")
        self.assertIn("embed_and_query", defined_names_rag, "embed_and_query() must remain")
        self.assertIn("embed_and_query_async", defined_names_rag, "embed_and_query_async() must remain")
        self.assertIn("ingest_incremental_resolution", defined_names_rag, "ingest_incremental_resolution() must remain")


if __name__ == "__main__":
    unittest.main()
