import logging
import json
import uuid
import re
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, Optional, Tuple
from .knowledge_memory import KnowledgeMemoryManager

logger = logging.getLogger("COMMAND_HANDLER")

class TeachingCommandHandler:
    """
    Teaching Command Handler for Jarvis AI:
    Executes when receiving command: "Jarvis, simpan pengetahuan berikut"
    Workflow:
      1. Data Validation
      2. Normalization
      3. Metadata Extraction
      4. Generate UUID
      5. Generate Embedding
      6. Insert PostgreSQL (jarvis_knowledge_store)
      7. Insert pgvector (768-dim)
      8. Index Knowledge (BM25 tsvector & HNSW vector index)
      9. Audit Log (jarvis_audit_trail)
      10. Knowledge ready for RAG retrieval
      11. LLM does NOT remember internally (isolated external storage)
    """

    def __init__(self, knowledge_mgr: Optional[KnowledgeMemoryManager] = None):
        self.knowledge_mgr = knowledge_mgr or KnowledgeMemoryManager()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "[REDACTED_DB_PASS]")

    def _get_connection(self):
        try:
            from shared.db_pool import get_db_connection
            return get_db_connection()
        except ImportError:
            try:
                from SERVER.shared.db_pool import get_db_connection
                return get_db_connection()
            except ImportError:
                return psycopg2.connect(
                    host=self.db_host,
                    port=self.db_port,
                    database=self.db_name,
                    user=self.user,
                    password=self.password
                )

    def parse_teaching_command(self, raw_text: str) -> Dict[str, Any]:
        """
        Parses structured key-value lines or JSON block from user command.
        Example format:
          Jarvis, simpan pengetahuan berikut
          Judul: Solusi Flapping BGP
          Gejala: High Latency & Packet Loss
          Penyebab: Route Flapping pada Router Core
          Solusi: Terapkan BGP Route Dampening
          Kategori: NETWORK
          Tags: bgp, routing, dampening
          Confidence: 0.95
          Source: SENIOR_NETWORK_ENGINEER
          Reference: RFC 2439
          Severity: HIGH
          Environment: PRODUCTION
          Validation: VERIFIED
        """
        parsed = {
            "title": "",
            "symptoms": "",
            "root_cause": "",
            "solution": "",
            "category": "NETWORK",
            "tags": [],
            "confidence": 1.0,
            "source": "USER_TEACHING",
            "reference": "",
            "severity": "MEDIUM",
            "environment": "PRODUCTION",
            "validation": "VALIDATED"
        }

        # Try JSON block parse first
        if "{" in raw_text and "}" in raw_text:
            try:
                json_str = raw_text[raw_text.find("{"):raw_text.rfind("}")+1]
                data = json.loads(json_str)
                for k, v in data.items():
                    key_lower = k.lower().strip()
                    if key_lower in ["judul", "title"]: parsed["title"] = str(v)
                    elif key_lower in ["gejala", "symptoms"]: parsed["symptoms"] = str(v)
                    elif key_lower in ["penyebab", "root_cause", "cause"]: parsed["root_cause"] = str(v)
                    elif key_lower in ["solusi", "solution"]: parsed["solution"] = str(v)
                    elif key_lower in ["kategori", "category"]: parsed["category"] = str(v)
                    elif key_lower in ["tags", "tag"]:
                        parsed["tags"] = [t.strip() for t in str(v).split(",")] if isinstance(v, str) else list(v)
                    elif key_lower in ["confidence", "keyakinan"]: parsed["confidence"] = float(v)
                    elif key_lower in ["source", "sumber"]: parsed["source"] = str(v)
                    elif key_lower in ["reference", "referensi"]: parsed["reference"] = str(v)
                    elif key_lower in ["severity", "tingkat"]: parsed["severity"] = str(v)
                    elif key_lower in ["environment", "lingkungan"]: parsed["environment"] = str(v)
                    elif key_lower in ["validation", "validasi"]: parsed["validation"] = str(v)
                return parsed
            except Exception:
                pass

        # Key-Value Line Parser
        lines = raw_text.splitlines()
        for line in lines:
            line_str = line.strip()
            if not line_str or ":" not in line_str:
                continue

            parts = line_str.split(":", 1)
            key = parts[0].strip().lower()
            val = parts[1].strip()

            if key in ["judul", "title"]: parsed["title"] = val
            elif key in ["gejala", "symptoms"]: parsed["symptoms"] = val
            elif key in ["penyebab", "root_cause", "cause"]: parsed["root_cause"] = val
            elif key in ["solusi", "solution"]: parsed["solution"] = val
            elif key in ["kategori", "category"]: parsed["category"] = val
            elif key in ["tags", "tag"]: parsed["tags"] = [t.strip() for t in val.split(",") if t.strip()]
            elif key in ["confidence", "keyakinan"]:
                try: parsed["confidence"] = float(val)
                except Exception: pass
            elif key in ["source", "sumber"]: parsed["source"] = val
            elif key in ["reference", "referensi"]: parsed["reference"] = val
            elif key in ["severity", "tingkat"]: parsed["severity"] = val
            elif key in ["environment", "lingkungan"]: parsed["environment"] = val
            elif key in ["validation", "validasi"]: parsed["validation"] = val

        if not parsed["title"] and len(raw_text) > 0:
            parsed["title"] = f"Pengetahuan Baru ({raw_text[:30]}...)"
            parsed["solution"] = raw_text

        return parsed

    def process_teaching_command(self, raw_text: str, operator_name: str = "OPERATOR") -> Dict[str, Any]:
        """
        Full workflow for teaching command execution.
        """
        # 1. Validation & Parsing
        data = self.parse_teaching_command(raw_text)
        if not data["title"] or not data["solution"]:
            raise ValueError("Data pengetahuan tidak valid: Judul dan Solusi wajib diisi.")

        # 2. Normalization & Metadata Extraction
        category = data["category"].upper().strip() or "NETWORK"
        severity = data["severity"].upper().strip() or "MEDIUM"
        environment = data["environment"].upper().strip() or "PRODUCTION"
        confidence = max(0.0, min(1.0, float(data["confidence"])))
        tags = data["tags"] or ["user_teaching", category.lower()]

        # 3. Memory Governance Ingestion Gate (Validation, Policy Check, Deduplication, Audit)
        try:
            from .memory_governance import MemoryGovernanceManager
            gov_mgr = MemoryGovernanceManager(knowledge_mgr=self.knowledge_mgr)
            gov_res = gov_mgr.govern_new_knowledge_ingestion(
                title=data["title"],
                solution=data["solution"],
                category=category,
                symptoms=data["symptoms"],
                root_cause=data["root_cause"],
                tags=tags,
                severity=severity,
                confidence=confidence,
                source=data["source"],
                author=operator_name
            )
        except Exception as e:
            logger.error(f"[COMMAND_HANDLER] Memory Governance evaluation error: {e}")
            gov_res = {"status": "ERROR", "message": str(e), "is_active": False}

        if not gov_res.get("is_active"):
            return {
                "status": gov_res.get("status", "REJECTED_BY_GOVERNANCE"),
                "message": gov_res.get("message", "Pengetahuan tidak lolos evaluasi Memory Governance."),
                "title": data["title"],
                "category": category,
                "confidence": confidence,
                "requires_hitl": gov_res.get("requires_hitl", True),
                "completeness_score": gov_res.get("completeness_score", 0.0)
            }

        k_uuid = gov_res["uuid"]

        return {
            "status": "SUCCESS",
            "message": f"Pengetahuan '{data['title']}' lolos evaluasi Memory Governance, di-embed (pgvector 768-dim), dan diaktifkan di Knowledge Memory.",
            "uuid": k_uuid,
            "title": data["title"],
            "category": category,
            "confidence": confidence,
            "completeness_score": gov_res.get("completeness_score", 1.0)
        }
