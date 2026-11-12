"""
Enterprise AI OS — Obsidian Hot-Reload Sync Daemon
Sprint Q: Knowledge Pipeline — Layer 4 (L4_ObsidianSyncDaemon)

Daemon ini memonitor directory Obsidian Vault secara real-time menggunakan
watchdog filesystem events. Setiap kali file .md berubah (create/modify/delete),
daemon langsung:
  1. Parse frontmatter & content via ObsidianVaultParser
  2. Kirim ke Knowledge Auto-Builder untuk indexing ulang RAG
  3. Publish event ke NATS: knowledge.vault.changed
  4. Update cognitive_memory.db dengan knowledge baru

Hot-Reload: Tidak perlu restart container — perubahan langsung aktif < 2 detik.

NATS Topics Published:
  knowledge.vault.changed    → setiap file berubah
  knowledge.vault.sync_done  → batch sync selesai
  dashboard.obsidian_status  → health metrics setiap 30 detik
"""

import os
import sys
import time
import json
import asyncio
import logging
import hashlib
import threading
from pathlib import Path
from typing import Dict, Any, Set, Optional, List
from datetime import datetime, timezone

# Ensure parent path resolvable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.obsidian_vault_parser import ObsidianVaultParser

logging.basicConfig(
    level=logging.INFO,
    format="[OBSIDIAN-SYNC] %(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("OBSIDIAN_SYNC_DAEMON")

# ── Configuration ──────────────────────────────────────────────────────────────
_DEFAULT_VAULT_DIR = "/app/auto_generated_sops" if os.path.isdir("/app/auto_generated_sops") else os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "auto_generated_sops"
)
VAULT_DIR = os.environ.get("OBSIDIAN_VAULT_DIR", _DEFAULT_VAULT_DIR)
SCAN_INTERVAL_SEC = int(os.environ.get("OBSIDIAN_SCAN_INTERVAL_SEC", "5"))
STATS_PUBLISH_INTERVAL_SEC = int(os.environ.get("OBSIDIAN_STATS_INTERVAL_SEC", "30"))
BATCH_DEBOUNCE_SEC = float(os.environ.get("OBSIDIAN_DEBOUNCE_SEC", "2.0"))
MAX_FILE_SIZE_KB = int(os.environ.get("OBSIDIAN_MAX_FILE_KB", "512"))
NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")


class VaultFileTracker:
    """
    Tracks file modification times & hashes to detect real changes.
    Prevents false positives from OS timestamp changes without content change.
    """

    def __init__(self):
        self._file_hashes: Dict[str, str] = {}
        self._lock = threading.RLock()

    def compute_hash(self, file_path: str) -> Optional[str]:
        """Compute MD5 hash of file content. Return None if file unreadable."""
        try:
            with open(file_path, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def has_changed(self, file_path: str) -> bool:
        """Return True jika file content benar-benar berubah sejak tracking terakhir."""
        new_hash = self.compute_hash(file_path)
        if new_hash is None:
            return False
        with self._lock:
            old_hash = self._file_hashes.get(file_path)
            if old_hash != new_hash:
                self._file_hashes[file_path] = new_hash
                return True
        return False

    def mark_deleted(self, file_path: str):
        with self._lock:
            self._file_hashes.pop(file_path, None)

    def get_tracked_count(self) -> int:
        with self._lock:
            return len(self._file_hashes)


class ObsidianHotReloadSyncDaemon:
    """
    Production-grade Obsidian Vault Hot-Reload Sync Daemon.
    
    Polling-based (tidak perlu inotify/watchdog package external).
    Menggunakan hash comparison untuk detect perubahan content real.
    
    Lifecycle:
      start() → scan loop + stats loop running concurrently
      stop()  → graceful shutdown
    """

    def __init__(
        self,
        vault_dir: str = VAULT_DIR,
        nc=None,  # NATS connection (opsional, inject dari luar)
        on_file_changed=None,  # Callback(file_path, parsed_data)
    ):
        self.vault_dir = Path(vault_dir)
        self.nc = nc
        self.on_file_changed = on_file_changed
        self.running = False
        self._tracker = VaultFileTracker()
        self._pending_batch: Dict[str, Dict[str, Any]] = {}  # file_path → parsed_data
        self._batch_lock = threading.RLock()
        self._stats = {
            "daemon_start": datetime.now(timezone.utc).isoformat(),
            "vault_dir": str(self.vault_dir),
            "total_files_tracked": 0,
            "total_changes_detected": 0,
            "total_syncs_published": 0,
            "total_errors": 0,
            "last_change_at": None,
            "last_sync_at": None,
            "status": "starting",
        }

    # ── Vault Scanning ─────────────────────────────────────────────────────────

    def _scan_vault_for_md_files(self) -> List[Path]:
        """Return semua file .md di vault yang ukurannya di bawah MAX_FILE_SIZE_KB."""
        md_files = []
        if not self.vault_dir.exists():
            logger.warning(f"Vault directory tidak ditemukan: {self.vault_dir}")
            return md_files

        for md_file in self.vault_dir.rglob("*.md"):
            try:
                size_kb = md_file.stat().st_size / 1024
                if size_kb > MAX_FILE_SIZE_KB:
                    logger.debug(f"Skip large file ({size_kb:.0f}KB): {md_file.name}")
                    continue
                # Skip hidden files / obsidian internal
                if any(part.startswith(".") for part in md_file.parts):
                    continue
                md_files.append(md_file)
            except Exception as e:
                logger.debug(f"Cannot stat {md_file}: {e}")

        return md_files

    def _process_changed_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse file .md yang berubah. Return parsed data atau None jika error."""
        try:
            parsed = ObsidianVaultParser.parse_file(str(file_path))
            if not parsed:
                # Fallback: baca raw content
                content = file_path.read_text(encoding="utf-8", errors="replace")
                parsed = {
                    "file_path": str(file_path),
                    "file_name": file_path.stem,
                    "content": content,
                    "frontmatter": {},
                    "backlinks": [],
                    "word_count": len(content.split()),
                }
            parsed["_sync_timestamp"] = datetime.now(timezone.utc).isoformat()
            parsed["_source"] = "obsidian_hot_reload_daemon"
            return parsed
        except Exception as e:
            logger.error(f"Parse error on {file_path.name}: {e}")
            self._stats["total_errors"] += 1
            return None

    async def _publish_nats_event(self, subject: str, payload: Dict[str, Any]):
        """Publish event ke NATS jika connection tersedia."""
        if not self.nc:
            return
        try:
            await self.nc.publish(subject, json.dumps(payload).encode())
        except Exception as e:
            logger.debug(f"NATS publish failed ({subject}): {e}")

    # ── Main Scan Loop ─────────────────────────────────────────────────────────

    async def _scan_loop(self):
        """
        Core scan loop: setiap SCAN_INTERVAL_SEC scan semua .md files,
        detect perubahan via hash, queue ke batch, flush setelah DEBOUNCE.
        """
        logger.info(
            f"[SCAN LOOP] Started | vault={self.vault_dir} | "
            f"interval={SCAN_INTERVAL_SEC}s | debounce={BATCH_DEBOUNCE_SEC}s"
        )
        last_flush_time = time.monotonic()

        while self.running:
            await asyncio.sleep(SCAN_INTERVAL_SEC)
            if not self.running:
                break

            try:
                md_files = self._scan_vault_for_md_files()
                self._stats["total_files_tracked"] = self._tracker.get_tracked_count()

                for md_file in md_files:
                    if not self.running:
                        break

                    if self._tracker.has_changed(str(md_file)):
                        logger.info(f"📝 Change detected: {md_file.name}")
                        parsed = self._process_changed_file(md_file)

                        if parsed:
                            with self._batch_lock:
                                self._pending_batch[str(md_file)] = parsed
                            self._stats["total_changes_detected"] += 1
                            self._stats["last_change_at"] = datetime.now(timezone.utc).isoformat()

                            # Publish immediate lightweight event ke NATS
                            await self._publish_nats_event("knowledge.vault.changed", {
                                "file": md_file.name,
                                "file_path": str(md_file),
                                "tags": parsed.get("frontmatter", {}).get("tags", []),
                                "word_count": parsed.get("word_count", 0),
                                "timestamp": parsed["_sync_timestamp"],
                            })

                # Flush batch setelah debounce period
                now = time.monotonic()
                if (now - last_flush_time) >= BATCH_DEBOUNCE_SEC:
                    with self._batch_lock:
                        if self._pending_batch:
                            await self._flush_batch(dict(self._pending_batch))
                            self._pending_batch.clear()
                    last_flush_time = now

            except Exception as e:
                logger.error(f"[SCAN LOOP] Error: {e}")
                self._stats["total_errors"] += 1

    async def _flush_batch(self, batch: Dict[str, Dict[str, Any]]):
        """
        Flush batch perubahan: trigger callback dan publish sync_done event.
        Ini yang memanggil Knowledge Auto-Builder / RAG indexing.
        """
        logger.info(f"🔄 Flushing {len(batch)} changed file(s) to knowledge pipeline...")

        # Panggil callback jika ada (Knowledge Auto-Builder)
        if self.on_file_changed:
            for file_path, parsed_data in batch.items():
                try:
                    if asyncio.iscoroutinefunction(self.on_file_changed):
                        await self.on_file_changed(file_path, parsed_data)
                    else:
                        self.on_file_changed(file_path, parsed_data)
                except Exception as e:
                    logger.error(f"Callback error for {file_path}: {e}")

        # Publish batch summary ke NATS
        await self._publish_nats_event("knowledge.vault.sync_done", {
            "files_count": len(batch),
            "files": [Path(fp).name for fp in batch.keys()],
            "source": "obsidian_hot_reload_daemon",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._stats["total_syncs_published"] += 1
        self._stats["last_sync_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"✅ Batch flush complete: {len(batch)} file(s) sent to pipeline.")

    # ── Stats Loop ─────────────────────────────────────────────────────────────

    async def _stats_loop(self):
        """Publish health stats ke NATS 'dashboard.obsidian_status' setiap 30 detik."""
        while self.running:
            await asyncio.sleep(STATS_PUBLISH_INTERVAL_SEC)
            if not self.running:
                break
            self._stats["status"] = "running"
            self._stats["total_files_tracked"] = self._tracker.get_tracked_count()
            await self._publish_nats_event("dashboard.obsidian_status", dict(self._stats))
            logger.info(
                f"[STATS] files_tracked={self._stats['total_files_tracked']} | "
                f"changes={self._stats['total_changes_detected']} | "
                f"syncs={self._stats['total_syncs_published']} | "
                f"errors={self._stats['total_errors']}"
            )

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def start(self):
        """
        Mulai daemon: jalankan scan_loop + stats_loop secara concurrent.
        Panggil dengan: asyncio.create_task(daemon.start())
        """
        self.running = True
        self._stats["status"] = "running"
        logger.info(
            f"🚀 Obsidian Hot-Reload Sync Daemon STARTED\n"
            f"   Vault: {self.vault_dir}\n"
            f"   Scan interval: {SCAN_INTERVAL_SEC}s\n"
            f"   Debounce: {BATCH_DEBOUNCE_SEC}s\n"
            f"   Stats publish: {STATS_PUBLISH_INTERVAL_SEC}s\n"
            f"   Max file size: {MAX_FILE_SIZE_KB}KB"
        )

        # Jalankan initial full scan untuk populate tracker
        await self._initial_full_scan()

        # Concurrent scan loop + stats loop
        await asyncio.gather(
            self._scan_loop(),
            self._stats_loop(),
            return_exceptions=True,
        )

    async def _initial_full_scan(self):
        """
        Lakukan full scan saat startup untuk populate file tracker.
        Files yang sudah ada di vault tidak dikirim ke pipeline,
        hanya di-register ke tracker (baseline state).
        """
        logger.info("🔍 Initial full vault scan (baseline population)...")
        md_files = self._scan_vault_for_md_files()
        for md_file in md_files:
            # Just compute & store hash tanpa trigger change event
            self._tracker.compute_hash.__func__  # warm up
            _ = self._tracker.has_changed(str(md_file))  # register hash

        logger.info(
            f"✅ Baseline scan complete: {len(md_files)} .md files registered."
        )
        self._stats["total_files_tracked"] = self._tracker.get_tracked_count()

        # Publish startup event ke NATS
        await self._publish_nats_event("dashboard.obsidian_status", {
            **self._stats,
            "event": "daemon_started",
            "initial_files_scanned": len(md_files),
        })

    async def stop(self):
        """Graceful shutdown."""
        logger.info("🛑 Obsidian Sync Daemon shutting down...")
        self.running = False
        self._stats["status"] = "stopped"
        await self._publish_nats_event("dashboard.obsidian_status", {
            **self._stats, "event": "daemon_stopped"
        })

    def get_stats(self) -> Dict[str, Any]:
        """Return current stats dict (thread-safe copy)."""
        return dict(self._stats)


# ── Standalone Entry Point ─────────────────────────────────────────────────────

async def daemon_main(nc=None):
    """
    Entry point untuk daemon_runner.py.
    
    Usage di daemon_runner.py:
        from daemons.obsidian_sync_daemon import daemon_main as obsidian_daemon
        asyncio.create_task(obsidian_daemon(nc=nats_connection))
    """
    daemon = ObsidianHotReloadSyncDaemon(nc=nc)
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(daemon_main())
