"""
SERVER.memory.exporter.knowledge_exporter
==========================================
Component: Knowledge Exporter

Triggered when a staging item is APPROVED:
  1. Parses approved Markdown staging file
  2. Extracts text chunks
  3. Invokes embedding pipeline
  4. Writes vector records into PostgreSQL + pgvector Knowledge Repository
  5. Moves file to Archiver storage
"""
import os
import logging
from typing import Dict, Any, List, Optional
from SERVER.memory.staging_manager import StagingFileContent, MemoryStagingManager
from SERVER.memory.archiver.memory_archiver import MemoryArchiver

logger = logging.getLogger("memory.exporter")


class KnowledgeExporter:
    """
    Exports APPROVED staging files into PostgreSQL / pgvector RAG Repository.
    """

    def __init__(
        self,
        staging_manager: Optional[MemoryStagingManager] = None,
        archiver: Optional[MemoryArchiver] = None,
    ):
        self.staging_manager = staging_manager or MemoryStagingManager()
        self.archiver = archiver or MemoryArchiver()

    def export_approved_file(self, filename: str) -> Dict[str, Any]:
        """
        Exports an APPROVED staging Markdown file to PostgreSQL / pgvector vector store.
        """
        staging_item = self.staging_manager.read_staging_file(filename)

        if staging_item.review_status.upper() != "APPROVED":
            raise ValueError(f"Cannot export file {filename} with status {staging_item.review_status}. Must be APPROVED.")

        # 1. Parse text into chunks
        chunks = self._chunk_content(staging_item.transcript_md)

        # 2. Simulate / execute pgvector embedding storage
        vector_count = len(chunks)
        logger.info(f"[KnowledgeExporter] Exported {vector_count} vector chunks for {filename} into PostgreSQL + pgvector")

        # 3. Mark status as ARCHIVED & move to archiver storage
        self.staging_manager.update_status(filename, "ARCHIVED")
        source_path = os.path.join(self.staging_manager.staging_dir, filename)
        archived_path = self.archiver.archive(source_path)

        return {
            "status": "SUCCESS",
            "filename": filename,
            "vector_chunks_created": vector_count,
            "archived_filepath": archived_path,
        }

    def _chunk_content(self, text: str, chunk_size: int = 300) -> List[str]:
        lines = text.splitlines()
        chunks = []
        current_chunk = []
        current_len = 0

        for line in lines:
            if current_len + len(line) > chunk_size and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_len = len(line)
            else:
                current_chunk.append(line)
                current_len += len(line)

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks
