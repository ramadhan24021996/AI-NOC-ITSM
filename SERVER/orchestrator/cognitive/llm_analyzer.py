"""
SERVER.orchestrator.cognitive.llm_analyzer
==========================================
Component: LLM Context Analyzer

Menganalisis kueri tanpa langsung menjawab:
  - Intent Detector (diagnose_incident, ask_knowledge, execute_action, learn_fact)
  - Entity Extractor (device hostnames, IP addresses, service names)
  - Urgency & Flag Evaluator (requires_rag, requires_tool, requires_memory)
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any

logger = logging.getLogger("orchestrator.cognitive.llm_analyzer")


@dataclass
class LLMAnalysisResult:
    intent: str
    entities: List[str]
    urgency: str
    requires_rag: bool
    requires_tool: bool
    requires_memory: bool
    intent_confidence: float = 0.98

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "entities": self.entities,
            "urgency": self.urgency,
            "requires_rag": self.requires_rag,
            "requires_tool": self.requires_tool,
            "requires_memory": self.requires_memory,
            "intent_confidence": self.intent_confidence,
        }


class LLMContextAnalyzer:
    """
    Analyzes inputs to extract Intent, Entities, Urgency, and Execution Flags.
    """

    def analyze(
        self, query_text: str, telemetry_context: Dict[str, Any]
    ) -> LLMAnalysisResult:
        query_lower = query_text.lower()
        severity = str(telemetry_context.get("severity", "medium")).lower()

        # 1. Entity Extraction
        entities: List[str] = []
        host_matches = re.findall(r"\b(srv-[a-z0-9-]+|node-[0-9]+|router-[0-9a-z-]+|host-[0-9a-z-]+)\b", query_lower)
        ip_matches = re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", query_text)
        entities.extend(host_matches)
        entities.extend(ip_matches)

        telem_host = telemetry_context.get("host") or telemetry_context.get("device_id")
        if telem_host and str(telem_host) not in entities:
            entities.append(str(telem_host))

        # 2. Intent Detection
        if any(kw in query_lower for kw in ["mulai hari ini", "catat", "ingat", "setiap jam", "pukul"]):
            intent = "learn_fact"
            req_memory = True
            req_tool = False
            req_rag = False
        elif any(kw in query_lower for kw in ["restart", "reboot", "clear cache", "isolate", "run probe", "scale"]):
            intent = "execute_action"
            req_tool = True
            req_rag = False
            req_memory = False
        elif any(kw in query_lower for kw in ["diagnosa", "kenapa", "investigasi", "troubleshoot", "down", "error", "spike"]):
            intent = "diagnose_incident"
            req_rag = True
            req_tool = True
            req_memory = False
        else:
            intent = "ask_knowledge"
            req_rag = True
            req_tool = False
            req_memory = False

        # 3. Urgency Determination
        urgency = "high" if severity in ["critical", "high"] else "medium"
        if intent == "execute_action" and urgency != "high":
            urgency = "high"

        result = LLMAnalysisResult(
            intent=intent,
            entities=list(set(entities)),
            urgency=urgency,
            requires_rag=req_rag,
            requires_tool=req_tool,
            requires_memory=req_memory,
            intent_confidence=0.98,
        )

        logger.debug(f"[LLMAnalyzer] Extracted intent={intent} | entities={result.entities} | urgency={urgency}")
        return result
