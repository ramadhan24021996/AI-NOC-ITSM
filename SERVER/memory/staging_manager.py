"""
SERVER.memory.staging_manager
=============================
Component: Memory Staging Manager

Manages creation, parsing, and lifecycle status updates for Markdown staging files
stored in SERVER/memory/staging/ with full Knowledge Governance metadata.
"""
import os
import re
import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("memory.staging.manager")

DEFAULT_STAGING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "staging"))


@dataclass
class StagingFileContent:
    filename: str
    session_id: str
    timestamp: str
    operator: str
    persona: str
    cognitive_metadata: Dict[str, Any]
    transcript_md: str
    review_status: str = "DRAFT"  # DRAFT, UNDER_REVIEW, APPROVED, REJECTED, ARCHIVED
    version: str = "v1"
    overall_quality_score: int = 90
    duplicate_similarity: int = 0
    related_topics: List[str] = field(default_factory=list)


class MemoryStagingManager:
    """
    Manages local Markdown staging files with Knowledge Governance YAML frontmatter.
    """

    def __init__(self, staging_dir: Optional[str] = None):
        self.staging_dir = staging_dir or DEFAULT_STAGING_DIR
        os.makedirs(self.staging_dir, exist_ok=True)

    def create_staging_file(
        self,
        session_id: str,
        user_query: str,
        assistant_response: str,
        cognitive_payload: Optional[Dict[str, Any]] = None,
        operator: str = "Operator",
        persona: str = "Senior System Engineer",
        source: str = "conversation",
    ) -> str:
        cog = cognitive_payload or {}
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        date_today = time.strftime("%Y-%m-%d")
        file_date_str = time.strftime("%Y%m%d_%H%M%S")
        safe_session = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
        filename = f"conversation_{file_date_str}_{safe_session[:12]}.md"
        filepath = os.path.join(self.staging_dir, filename)

        # Extract YAML frontmatter fields
        intent = cog.get("analysis_result", {}).get("intent", "diagnose_incident")
        goal = cog.get("goal_payload", {}).get("active_goal", "Find RCA")
        stage = cog.get("context_state", {}).get("stage", "Diagnosis")
        entities = cog.get("analysis_result", {}).get("entities", [])
        knowledge_gap = cog.get("knowledge_gap", {}).get("has_gap", False)
        memory_candidate = cog.get("memory_candidate", {}).get("is_candidate", False)
        confidence = cog.get("confidence_scorecard", {}).get("overall_confidence", 0.95)

        yaml_frontmatter = (
            "---\n"
            f"session_id: {session_id}\n"
            f"timestamp: \"{timestamp_str}\"\n"
            f"operator: {operator}\n"
            f"persona: {persona}\n"
            f"version: v1\n"
            f"previous_version: None\n"
            f"source: {source}\n"
            f"intent: {intent}\n"
            f"goal: {goal}\n"
            f"stage: {stage}\n"
            f"entities:\n"
            + "".join(f"  - {e}\n" for e in entities)
            + f"knowledge_gap: {str(knowledge_gap).lower()}\n"
            f"memory_candidate: {str(memory_candidate).lower()}\n"
            f"ai_confidence: {confidence}\n"
            f"reviewer_confidence: 0.98\n"
            f"completeness: 90\n"
            f"consistency: 95\n"
            f"evidence: 95\n"
            f"readability: 90\n"
            f"overall_quality_score: 90\n"
            f"duplicate_similarity: 0\n"
            f"related_topics:\n  - NOC Operations\n"
            f"created_date: {date_today}\n"
            f"last_review_date: {date_today}\n"
            f"next_review_date: 2027-01-01\n"
            f"review_status: DRAFT\n"
            f"approved_by: None\n"
            f"approved_at: None\n"
            f"approval_reason: None\n"
            "---\n\n"
        )

        md_body = (
            f"# Conversation Record ({session_id})\n\n"
            f"**Session ID**: `{session_id}`  \n"
            f"**Tanggal**: {timestamp_str}  \n"
            f"**Operator**: {operator}  \n"
            f"**Persona**: {persona}  \n\n"
            f"---  \n\n"
            f"## Percakapan\n\n"
            f"**Operator**:\n{user_query}\n\n"
            f"**Jarvis**:\n{assistant_response}\n\n"
            f"---  \n\n"
            f"## Context & Cognitive State\n\n"
            f"- **Intent**: `{intent}`\n"
            f"- **Goal**: `{goal}`\n"
            f"- **Stage**: `{stage}`\n"
            f"- **Entities**: {', '.join(entities) if entities else 'None'}\n"
            f"- **Knowledge Gap**: {knowledge_gap}\n"
            f"- **Memory Candidate**: {memory_candidate}\n"
            f"- **AI Confidence**: {confidence}\n"
        )

        full_content = yaml_frontmatter + md_body

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        logger.info(f"[MemoryStagingManager] Created staging file with governance: {filename}")
        return filename

    def read_staging_file(self, filename: str) -> StagingFileContent:
        filepath = os.path.join(self.staging_dir, filename)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Staging file not found: {filename}")

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        parts = content.split("---", 2)
        if len(parts) >= 3:
            yaml_raw = parts[1]
            md_body = parts[2].strip()
        else:
            yaml_raw = ""
            md_body = content

        metadata = self._parse_yaml_simple(yaml_raw)

        try:
            quality_score = int(metadata.get("overall_quality_score", 90))
            if quality_score > 100:  # Fix scaling if over 100
                quality_score = int(quality_score / 10.0)
        except Exception as e:
            logger.error("[StagingManager] Operation failed: %s", e, exc_info=True)
            quality_score = 90

        try:
            dup_sim = int(metadata.get("duplicate_similarity", 0))
        except Exception as e:
            logger.error("[StagingManager] Operation failed: %s", e, exc_info=True)
            dup_sim = 0

        return StagingFileContent(
            filename=filename,
            session_id=metadata.get("session_id", ""),
            timestamp=metadata.get("timestamp", ""),
            operator=metadata.get("operator", "Operator"),
            persona=metadata.get("persona", "Senior System Engineer"),
            cognitive_metadata=metadata,
            transcript_md=md_body,
            review_status=metadata.get("review_status", "DRAFT"),
            version=metadata.get("version", "v1"),
            overall_quality_score=quality_score,
            duplicate_similarity=dup_sim,
            related_topics=metadata.get("related_topics", ["NOC Operations"]),
        )

    def update_status(self, filename: str, new_status: str, audit_info: Optional[Dict[str, str]] = None) -> bool:
        filepath = os.path.join(self.staging_dir, filename)
        if not os.path.exists(filepath):
            return False

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        if "review_status:" in content:
            updated_content = re.sub(
                r"review_status:\s*[A-Z_]+", f"review_status: {new_status}", content
            )
        else:
            updated_content = content.replace("---\n", f"---\nreview_status: {new_status}\n", 1)

        if audit_info:
            for k, v in audit_info.items():
                if f"{k}:" in updated_content:
                    updated_content = re.sub(rf"{k}:\s*.*", f"{k}: {v}", updated_content)
                else:
                    updated_content = updated_content.replace("---\n", f"---\n{k}: {v}\n", 1)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(updated_content)

        logger.info(f"[MemoryStagingManager] Updated {filename} status to {new_status}")
        return True

    def write_file_content(self, filename: str, content: str) -> bool:
        filepath = os.path.join(self.staging_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return True

    def list_files(self, status_filter: Optional[str] = None) -> List[str]:
        if not os.path.exists(self.staging_dir):
            return []

        files = sorted(os.listdir(self.staging_dir), reverse=True)
        md_files = [f for f in files if f.endswith(".md")]

        if not status_filter:
            return md_files

        filtered = []
        for filename in md_files:
            try:
                st = self.read_staging_file(filename)
                if st.review_status.upper() == status_filter.upper():
                    filtered.append(filename)
            except Exception as e:
                logger.error("[StagingManager] Operation failed: %s", e, exc_info=True)
                pass
        return filtered

    def _parse_yaml_simple(self, yaml_str: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        entities = []
        related = []
        in_entities = False
        in_related = False

        for line in yaml_str.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            if line_str == "entities:":
                in_entities = True
                in_related = False
                continue
            elif line_str == "related_topics:":
                in_related = True
                in_entities = False
                continue

            if in_entities:
                if line_str.startswith("- "):
                    entities.append(line_str[2:].strip())
                    continue
                else:
                    in_entities = False

            if in_related:
                if line_str.startswith("- "):
                    related.append(line_str[2:].strip())
                    continue
                else:
                    in_related = False

            if ":" in line_str:
                k, v = line_str.split(":", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if v == "true":
                    v = True
                elif v == "false":
                    v = False
                result[k] = v

        result["entities"] = entities
        result["related_topics"] = related or ["NOC Operations"]
        return result
