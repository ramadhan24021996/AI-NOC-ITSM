"""
Obsidian Vault Synchronization Daemon.
Monitors directory changes in DOCUMENTATION/obsidian_vault and automatically reloads
the SOP Catalog and Knowledge Store in real-time (Hot-Reload with Zero Downtime).
"""

import os
import sys
import time
import logging
import threading
from typing import Optional, Callable

try:
    from governance.sop_registry_engine import SOPRegistryEngine
except ImportError:
    from governance.sop_registry_engine import SOPRegistryEngine

logger = logging.getLogger("ObsidianSyncDaemon")


class ObsidianSyncDaemon:
    """
    Production-ready Hot-Reload Daemon for Obsidian Vault.
    Provides background thread monitoring with debouncing and safe exception boundaries.
    """

    def __init__(
        self,
        vault_dir: str,
        sop_engine: SOPRegistryEngine,
        poll_interval_sec: float = 3.0,
        on_reload_callback: Optional[Callable[[int], None]] = None
    ):
        self.vault_dir = vault_dir
        self.sop_engine = sop_engine
        self.poll_interval_sec = poll_interval_sec
        self.on_reload_callback = on_reload_callback

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_snapshot: dict = {}

    def _get_vault_snapshot(self) -> dict:
        """Returns a snapshot dictionary mapping filepath -> mtime for all .md files."""
        snapshot = {}
        if not os.path.exists(self.vault_dir):
            return snapshot

        try:
            for root, _, files in os.walk(self.vault_dir):
                for f in files:
                    if f.endswith(".md"):
                        full_path = os.path.join(root, f)
                        try:
                            snapshot[full_path] = os.path.getmtime(full_path)
                        except OSError:
                            pass
        except Exception as e:
            logger.error("[OBSIDIAN DAEMON] Error creating snapshot: %s", e)

        return snapshot

    def start(self):
        """Starts the background sync monitoring thread."""
        if self._running:
            logger.warning("[OBSIDIAN DAEMON] Daemon is already running.")
            return

        self._running = True
        self._last_snapshot = self._get_vault_snapshot()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ObsidianSyncWorker")
        self._thread.start()
        logger.info("[OBSIDIAN DAEMON] Started monitoring Vault '%s' (Interval: %.1fs)",
                    self.vault_dir, self.poll_interval_sec)

    def stop(self):
        """Stops the sync daemon thread cleanly."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        logger.info("[OBSIDIAN DAEMON] Sync daemon stopped.")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self._running:
            try:
                time.sleep(self.poll_interval_sec)
                current_snapshot = self._get_vault_snapshot()

                if current_snapshot != self._last_snapshot:
                    logger.info("[OBSIDIAN DAEMON] Detected file changes in Vault. Triggering Hot-Reload...")
                    # Debounce settling delay
                    time.sleep(0.5)

                    reloaded_count = self.sop_engine.reload_catalog(self.vault_dir)
                    self._last_snapshot = self._get_vault_snapshot()

                    if self.on_reload_callback:
                        try:
                            self.on_reload_callback(reloaded_count)
                        except Exception as cb_err:
                            logger.error("[OBSIDIAN DAEMON] Reload callback error: %s", cb_err)

            except Exception as e:
                logger.error("[OBSIDIAN DAEMON] Unexpected error in monitor loop: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    vault_path = "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/obsidian_vault"
    engine = SOPRegistryEngine(vault_dir=vault_path)

    daemon = ObsidianSyncDaemon(vault_dir=vault_path, sop_engine=engine, poll_interval_sec=1.0)
    daemon.start()

    print("Daemon running for 3 seconds test...")
    time.sleep(3.0)
    daemon.stop()
    print("Daemon test completed successfully.")
