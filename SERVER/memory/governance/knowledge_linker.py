"""
SERVER.memory.governance.knowledge_linker
==========================================
Component: Knowledge Linker

Extracts related operational topics (e.g., related: [Oracle RAC, PostgreSQL, Backup])
to establish relational links in RAG metadata.
"""
import re
import logging
from typing import List, Dict, Any, Set

logger = logging.getLogger("memory.governance.linker")

# Topic dictionary for relational tagging
KNOWN_TOPIC_KEYWORDS = {
    "Oracle RAC": ["oracle", "rac", "database oracle"],
    "PostgreSQL": ["postgres", "postgresql", "pgvector", "sql"],
    "BGP Routing": ["bgp", "router", "routing", "flap", "peering"],
    "Backup & Recovery": ["backup", "restore", "recovery", "disaster recovery", "jadwal backup"],
    "CPU Utilization": ["cpu", "core", "processor", "cpu spike"],
    "Memory Exhaustion": ["ram", "memory", "swap", "out of memory", "oom"],
    "Storage & Disk": ["disk", "storage", "partition", "fs", "iops"],
    "Netdata Telemetry": ["netdata", "telemetry", "metric", "collector"],
    "Kubernetes": ["k8s", "kubernetes", "pod", "deployment", "cluster"],
    "Nginx Web": ["nginx", "web server", "http", "load balancer"],
}


class KnowledgeLinker:
    """
    Extracts relational tags and linked topics for RAG graph metadata.
    """

    def extract_related_topics(
        self, transcript_md: str, cognitive_metadata: dict
    ) -> List[str]:
        text = (
            (transcript_md or "").lower()
            + " "
            + str(cognitive_metadata.get("entities", [])).lower()
            + " "
            + str(cognitive_metadata.get("topic", "")).lower()
        )

        matched_topics: Set[str] = set()

        for topic, keywords in KNOWN_TOPIC_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                matched_topics.add(topic)

        # Default fallback
        if not matched_topics:
            matched_topics.add("NOC Operations")

        sorted_topics = sorted(list(matched_topics))
        logger.debug(f"[KnowledgeLinker] Extracted topics: {sorted_topics}")
        return sorted_topics
