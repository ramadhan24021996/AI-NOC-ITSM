import json
import logging
import os
from typing import Dict, Any, Optional

from ai_supervisor import execute_validated_llm
from schemas.knowledge_v2_schema import KnowledgePayloadSchema

logger = logging.getLogger("KNOWLEDGE_CURATOR")

class KnowledgeCurator:
    def __init__(self):
        self.prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "DOCUMENTATION", "prompts", "knowledge_curator.md"
        )
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        try:
            with open(self.prompt_path, "r") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load Knowledge Curator prompt: {e}")
            return "You are the Knowledge Curator AI for OSI AIOps Enterprise. Output strict JSON."

    async def curate_document(
        self,
        router,
        raw_document_text: str,
        document_metadata: Optional[Dict[str, Any]] = None
    ) -> KnowledgePayloadSchema:
        """
        Takes unstructured text (like a raw SOP, Post Mortem, Vendor Doc, etc),
        and curates it into the Enterprise AIOps Knowledge Object V2 schema.
        """
        if not document_metadata:
            document_metadata = {}

        prompt = (
            f"{self.system_prompt}\n\n"
            f"--- CURRENT DOCUMENT CONTEXT ---\n"
            f"{json.dumps(document_metadata, indent=2)}\n\n"
            f"[RAW DOCUMENT TEXT]\n"
            f"{raw_document_text}\n\n"
            f"Generate the final Knowledge Payload JSON now."
        )

        try:
            logger.info("Sending document to LLM for curation into Knowledge V2 Schema...")
            # We use the router to execute the LLM inference with strict schema validation
            payload: KnowledgePayloadSchema = await execute_validated_llm(
                router=router,
                severity_score=90, # High priority for knowledge ingestion
                prompt=prompt,
                schema_class=KnowledgePayloadSchema,
                max_attempts=3
            )
            logger.info(f"Successfully curated document into Knowledge Object. Root Cause: {payload.root_cause.primary_root_cause}")
            return payload
            
        except Exception as e:
            logger.error(f"Failed to curate document: {e}")
            raise e

_curator_instance = None

def get_knowledge_curator() -> KnowledgeCurator:
    global _curator_instance
    if _curator_instance is None:
        _curator_instance = KnowledgeCurator()
    return _curator_instance
