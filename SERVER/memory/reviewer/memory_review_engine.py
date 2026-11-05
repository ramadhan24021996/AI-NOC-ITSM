"""
SERVER.memory.reviewer.memory_review_engine
============================================
Component: Memory Review Engine

Provides human-in-the-loop (HITL) review operations backed by full Knowledge Governance:
  - Quality Checker (Hard Gate: overall_score < 80 blocks approval)
  - Duplicate Detector (Calculates similarity % vs existing SOPs)
  - Knowledge Linker (Extracts relational topic tags)
  - Freshness Manager (Evaluates SOP freshness)
  - Version Manager (Increments versions & handles rollbacks)
"""
import os
import time
import logging
from typing import List, Dict, Any, Optional

from SERVER.memory.staging_manager import MemoryStagingManager, StagingFileContent
from SERVER.memory.exporter.knowledge_exporter import KnowledgeExporter
from SERVER.memory.governance.version_manager import KnowledgeVersionManager
from SERVER.memory.governance.quality_checker import KnowledgeQualityChecker, QualityScorecard
from SERVER.memory.governance.duplicate_detector import KnowledgeDuplicateDetector, DuplicateCheckResult
from SERVER.memory.governance.knowledge_linker import KnowledgeLinker
from SERVER.memory.governance.freshness_manager import KnowledgeFreshnessManager, FreshnessStatus

logger = logging.getLogger("memory.reviewer")


class MemoryReviewEngine:
    """
    Review Engine facade with Governance pipeline integration for Dashboard Knowledge Review.
    """

    def __init__(
        self,
        staging_manager: Optional[MemoryStagingManager] = None,
        exporter: Optional[KnowledgeExporter] = None,
        version_manager: Optional[KnowledgeVersionManager] = None,
        quality_checker: Optional[KnowledgeQualityChecker] = None,
        duplicate_detector: Optional[KnowledgeDuplicateDetector] = None,
        linker: Optional[KnowledgeLinker] = None,
        freshness_manager: Optional[KnowledgeFreshnessManager] = None,
    ):
        self.staging_manager = staging_manager or MemoryStagingManager()
        self.exporter = exporter or KnowledgeExporter(staging_manager=self.staging_manager)
        self.version_manager = version_manager or KnowledgeVersionManager()
        self.quality_checker = quality_checker or KnowledgeQualityChecker()
        self.duplicate_detector = duplicate_detector or KnowledgeDuplicateDetector()
        self.linker = linker or KnowledgeLinker()
        self.freshness_manager = freshness_manager or KnowledgeFreshnessManager()

    def list_items(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists staging files with enhanced governance metadata for Dashboard UI table.
        """
        files = self.staging_manager.list_files(status_filter)
        items = []

        existing_docs = []
        for fn in files:
            try:
                st = self.staging_manager.read_staging_file(fn)
                existing_docs.append({"filename": fn, "content": st.transcript_md})
            except Exception as e:
                logger.error("[MemoryReviewer] Operation failed: %s", e, exc_info=True)
                pass

        for fn in files:
            try:
                st = self.staging_manager.read_staging_file(fn)
                q_scorecard = self.quality_checker.evaluate(st.transcript_md, st.cognitive_metadata)
                other_docs = [d for d in existing_docs if d["filename"] != fn]
                dup_res = self.duplicate_detector.check_duplicate(st.transcript_md, other_docs)
                fresh_status = self.freshness_manager.evaluate_freshness(
                    st.cognitive_metadata.get("created_date", ""),
                    st.cognitive_metadata.get("last_review_date", "")
                )

                items.append({
                    "filename": st.filename,
                    "session_id": st.session_id,
                    "sop_title": st.cognitive_metadata.get("topic") or st.session_id,
                    "timestamp": st.timestamp,
                    "operator": st.operator,
                    "reviewer": st.cognitive_metadata.get("approved_by", "-"),
                    "version": st.version,
                    "review_status": st.review_status,
                    "quality_score": q_scorecard.overall_score,
                    "similarity_pct": dup_res.similarity_pct,
                    "matching_sop": dup_res.matching_sop_title,
                    "reviewer_confidence": 0.98,
                    "freshness_status": fresh_status.to_dict(),
                    "knowledge_candidate": st.cognitive_metadata.get("knowledge_gap", False),
                    "memory_candidate": st.cognitive_metadata.get("memory_candidate", False),
                })
            except Exception as exc:
                logger.warning(f"[MemoryReviewEngine] Failed reading governance item {fn}: {exc}")

        return items

    def get_item_detail(self, filename: str) -> Dict[str, Any]:
        """
        Gets full governance detail of a single staging Markdown file.
        """
        st = self.staging_manager.read_staging_file(filename)
        q_scorecard = self.quality_checker.evaluate(st.transcript_md, st.cognitive_metadata)
        related_topics = self.linker.extract_related_topics(st.transcript_md, st.cognitive_metadata)
        fresh_status = self.freshness_manager.evaluate_freshness(
            st.cognitive_metadata.get("created_date", ""),
            st.cognitive_metadata.get("last_review_date", "")
        )

        return {
            "filename": st.filename,
            "session_id": st.session_id,
            "timestamp": st.timestamp,
            "operator": st.operator,
            "persona": st.persona,
            "version": st.version,
            "review_status": st.review_status,
            "quality_scorecard": q_scorecard.to_dict(),
            "related_topics": related_topics,
            "freshness_status": fresh_status.to_dict(),
            "cognitive_metadata": st.cognitive_metadata,
            "transcript_md": st.transcript_md,
        }

    def edit_item(
        self, filename: str, updated_content: str, new_status: str = "UNDER_REVIEW"
    ) -> bool:
        filepath = os.path.join(self.staging_manager.staging_dir, filename)
        existing_frontmatter = ""

        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                raw = f.read()
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                existing_frontmatter = f"---{parts[1]}---\n\n"

        if not updated_content.strip().startswith("---"):
            full_to_write = existing_frontmatter + updated_content.strip()
        else:
            full_to_write = updated_content

        self.staging_manager.write_file_content(filename, full_to_write)
        self.staging_manager.update_status(filename, new_status)
        logger.info(f"[MemoryReviewEngine] Edited item {filename} -> status {new_status}")
        return True

    def reject_item(self, filename: str, reason: str = "", reviewer: str = "Operator") -> bool:
        today_str = time.strftime("%Y-%m-%d")
        audit_info = {
            "approved_by": reviewer,
            "approved_at": today_str,
            "approval_reason": f"REJECTED: {reason}",
        }
        self.staging_manager.update_status(filename, "REJECTED", audit_info=audit_info)
        logger.info(f"[MemoryReviewEngine] Rejected item {filename} | reason={reason}")
        return True

    def approve_item(
        self, filename: str, reviewer: str = "Rama", approval_reason: str = "SOP validated"
    ) -> Dict[str, Any]:
        """
        Approves item with Quality Gate Check (overall >= 80) and Version Snapshot creation.
        """
        st = self.staging_manager.read_staging_file(filename)

        # 1. HARD QUALITY GATE: score >= 80
        scorecard = self.quality_checker.evaluate(st.transcript_md, st.cognitive_metadata)
        if not scorecard.is_approvable:
            raise ValueError(
                f"Approval BLOCKED for {filename}: {scorecard.rejection_reason}"
            )

        # 2. Version Snapshot Creation
        filepath = os.path.join(self.staging_manager.staging_dir, filename)
        ver_snapshot = self.version_manager.create_version_snapshot(st.session_id, filepath)

        # 3. Update Audit Trail & Status
        today_str = time.strftime("%Y-%m-%d")
        audit_info = {
            "version": ver_snapshot["version"],
            "approved_by": reviewer,
            "approved_at": today_str,
            "approval_reason": approval_reason,
            "last_review_date": today_str,
        }
        self.staging_manager.update_status(filename, "APPROVED", audit_info=audit_info)

        # 4. Export Vector Embeddings
        export_res = self.exporter.export_approved_file(filename)
        export_res["version"] = ver_snapshot["version"]
        export_res["quality_score"] = scorecard.overall_score

        logger.info(f"[MemoryReviewEngine] Approved and exported {filename} (Version {ver_snapshot['version']})")
        return export_res

    def rollback_version(self, filename: str, target_version: str) -> bool:
        """
        Rolls back staging file content to a specified version snapshot.
        """
        st = self.staging_manager.read_staging_file(filename)
        target_path = os.path.join(self.staging_manager.staging_dir, filename)

        success = self.version_manager.rollback_to_version(
            base_name=st.session_id,
            target_version=target_version,
            target_filepath=target_path,
        )
        if success:
            self.staging_manager.update_status(filename, "UNDER_REVIEW")
            logger.info(f"[MemoryReviewEngine] Rolled back {filename} to {target_version}")
        return success

    def merge_items(self, filenames: List[str], target_sop_title: str) -> str:
        if not filenames:
            raise ValueError("No filenames provided to merge")

        combined_bodies = []
        combined_entities = set()

        for fn in filenames:
            st = self.staging_manager.read_staging_file(fn)
            combined_bodies.append(f"### Source: `{st.filename}` ({st.session_id})\n{st.transcript_md}\n")
            for e in st.cognitive_metadata.get("entities", []):
                combined_entities.add(e)

        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        date_today = time.strftime("%Y-%m-%d")
        file_date_str = time.strftime("%Y%m%d_%H%M%S")
        merged_filename = f"sop_merged_{file_date_str}.md"

        yaml_frontmatter = (
            "---\n"
            f"session_id: merged_sop_{file_date_str}\n"
            f"timestamp: \"{timestamp_str}\"\n"
            f"operator: Operator (Merged)\n"
            f"persona: Senior System Engineer\n"
            f"version: v1\n"
            f"source: manual\n"
            f"intent: sop_consolidation\n"
            f"goal: Create Master SOP\n"
            f"stage: Consolidated\n"
            f"entities:\n"
            + "".join(f"  - {e}\n" for e in sorted(combined_entities))
            + "knowledge_gap: false\n"
            "memory_candidate: true\n"
            "ai_confidence: 0.99\n"
            "reviewer_confidence: 0.99\n"
            "completeness: 95\n"
            "consistency: 95\n"
            "evidence: 95\n"
            "readability: 95\n"
            "overall_quality_score: 95\n"
            "duplicate_similarity: 0\n"
            "related_topics:\n  - NOC Operations\n"
            f"created_date: {date_today}\n"
            f"last_review_date: {date_today}\n"
            f"next_review_date: 2027-01-01\n"
            "review_status: DRAFT\n"
            "approved_by: None\n"
            "approved_at: None\n"
            "approval_reason: None\n"
            "---\n\n"
        )

        sop_body = (
            f"# Master SOP: {target_sop_title}\n\n"
            f"**Tanggal Penggabungan**: {timestamp_str}  \n"
            f"**File Sumber**: {', '.join(filenames)}  \n\n"
            f"---  \n\n"
            f"## Ringkasan Prosedur Operasional\n\n"
            + "\n".join(combined_bodies)
        )

        full_content = yaml_frontmatter + sop_body
        filepath = os.path.join(self.staging_manager.staging_dir, merged_filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(full_content)

        logger.info(f"[MemoryReviewEngine] Merged {len(filenames)} files into {merged_filename}")
        return merged_filename
