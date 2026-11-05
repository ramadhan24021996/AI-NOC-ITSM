"""
SERVER.memory.archiver.memory_archiver
=======================================
Component: Memory Archiver

Moves processed staging files from SERVER/memory/staging/ to SERVER/memory/archiver/storage/.
"""
import os
import shutil
import logging
from typing import Optional

logger = logging.getLogger("memory.archiver")

DEFAULT_ARCHIVE_DIR = os.path.join(os.path.dirname(__file__), "storage")


class MemoryArchiver:
    """
    Handles moving staging files into archive storage.
    """

    def __init__(self, archive_dir: Optional[str] = None):
        self.archive_dir = archive_dir or DEFAULT_ARCHIVE_DIR
        os.makedirs(self.archive_dir, exist_ok=True)

    def archive(self, source_filepath: str) -> str:
        if not os.path.exists(source_filepath):
            raise FileNotFoundError(f"Source file to archive not found: {source_filepath}")

        filename = os.path.basename(source_filepath)
        target_path = os.path.join(self.archive_dir, filename)
        shutil.move(source_filepath, target_path)

        logger.info(f"[MemoryArchiver] Archived {filename} -> {target_path}")
        return target_path
