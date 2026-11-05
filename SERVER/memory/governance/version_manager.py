"""
SERVER.memory.governance.version_manager
========================================
Component: Knowledge Version Manager

Manages immutable version snapshots in SERVER/memory/versions/:
  - oracle_rac_v1.md
  - oracle_rac_v2.md
  - oracle_rac_v3.md
Supports version incrementing and instant rollbacks.
"""
import os
import re
import shutil
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("memory.governance.version")

DEFAULT_VERSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "versions"))


class KnowledgeVersionManager:
    """
    Manages version snapshots and rollback capabilities for Knowledge Base SOPs.
    """

    def __init__(self, versions_dir: Optional[str] = None):
        self.versions_dir = versions_dir or DEFAULT_VERSIONS_DIR
        os.makedirs(self.versions_dir, exist_ok=True)

    def create_version_snapshot(self, base_name: str, source_filepath: str) -> Dict[str, Any]:
        """
        Creates an immutable version snapshot file (_v1.md, _v2.md) in versions_dir.
        """
        if not os.path.exists(source_filepath):
            raise FileNotFoundError(f"Source file for version snapshot not found: {source_filepath}")

        safe_base = self._sanitize_base_name(base_name)
        next_ver_num = self._get_next_version_number(safe_base)
        version_filename = f"{safe_base}_v{next_ver_num}.md"
        target_path = os.path.join(self.versions_dir, version_filename)

        shutil.copy2(source_filepath, target_path)

        logger.info(f"[KnowledgeVersionManager] Created snapshot: {version_filename} (v{next_ver_num})")
        return {
            "base_name": safe_base,
            "version": f"v{next_ver_num}",
            "version_num": next_ver_num,
            "version_filename": version_filename,
            "version_filepath": target_path,
        }

    def list_versions(self, base_name: str) -> List[Dict[str, Any]]:
        safe_base = self._sanitize_base_name(base_name)
        pattern = re.compile(rf"^{re.escape(safe_base)}_v(\d+)\.md$")
        results = []

        if not os.path.exists(self.versions_dir):
            return []

        for fn in os.listdir(self.versions_dir):
            match = pattern.match(fn)
            if match:
                ver_num = int(match.group(1))
                filepath = os.path.join(self.versions_dir, fn)
                results.append({
                    "version": f"v{ver_num}",
                    "version_num": ver_num,
                    "filename": fn,
                    "filepath": filepath,
                    "created_at": os.path.getmtime(filepath),
                })

        return sorted(results, key=lambda x: x["version_num"], reverse=True)

    def rollback_to_version(self, base_name: str, target_version: str, target_filepath: str) -> bool:
        """
        Rolls back content of target_filepath to a previous version snapshot.
        """
        safe_base = self._sanitize_base_name(base_name)
        ver_str = target_version.lower() if target_version.startswith("v") else f"v{target_version}"
        version_filename = f"{safe_base}_{ver_str}.md"
        version_filepath = os.path.join(self.versions_dir, version_filename)

        if not os.path.exists(version_filepath):
            raise FileNotFoundError(f"Version snapshot file not found: {version_filename}")

        shutil.copy2(version_filepath, target_filepath)
        logger.info(f"[KnowledgeVersionManager] Rolled back {base_name} to {ver_str}")
        return True

    def _get_next_version_number(self, safe_base: str) -> int:
        versions = self.list_versions(safe_base)
        if not versions:
            return 1
        return versions[0]["version_num"] + 1

    def _sanitize_base_name(self, base_name: str) -> str:
        s = re.sub(r"\.md$", "", base_name, flags=re.IGNORECASE)
        s = re.sub(r"_v\d+$", "", s, flags=re.IGNORECASE)
        return re.sub(r"[^a-zA-Z0-9_-]", "_", s).lower()
