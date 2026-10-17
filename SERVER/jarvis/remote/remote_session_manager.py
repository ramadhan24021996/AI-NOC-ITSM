"""
SERVER.jarvis.remote.remote_session_manager — JARVIS Remote Session Manager
============================================================================
P6 Implementation: Manajemen sesi remote access (VNC/RDP/SSH) via JARVIS.

Fungsi utama:
  - open_session()   : Buka sesi remote baru via NOCBridge → LauncherService
  - close_session()  : Tutup sesi aktif
  - list_sessions()  : Lihat semua sesi remote aktif
  - format_status()  : Format status untuk output JARVIS

Terintegrasi dengan:
  - JarvisNOCBridge → POST /api/remote/launch/:type
  - JarvisCommandIntentRouter → Intent = REMOTE
"""
import logging
import time
import uuid
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.remote.session_manager")

# Supported remote tools
SUPPORTED_TOOLS = {"vnc", "rdp", "ssh", "anydesk", "teamviewer", "rustdesk"}

# Default ports per tool
DEFAULT_PORTS = {
    "vnc": 5900,
    "rdp": 3389,
    "ssh": 22,
    "anydesk": 7070,
    "teamviewer": 5938,
    "rustdesk": 21116,
}


@dataclass
class RemoteSession:
    """Representasi satu sesi remote aktif."""
    session_id: str
    operator_id: str
    tool: str              # vnc | rdp | ssh | anydesk | teamviewer
    host: str
    port: int
    target_device: str
    opened_at: float = field(default_factory=time.time)
    status: str = "ACTIVE"   # ACTIVE | CLOSED | FAILED
    session_token: str = ""
    closed_at: Optional[float] = None
    close_reason: str = ""


class JarvisRemoteSessionManager:
    """
    P6 — JARVIS Remote Session Manager.
    Manages lifecycle of all remote access sessions opened via JARVIS.

    Contoh:
        mgr = JarvisRemoteSessionManager(noc_bridge=bridge)
        result = mgr.open_session(
            operator_id="noc-operator-01",
            tool="vnc",
            host="192.168.10.5",
            target_device="server-Jakarta-01",
        )
        # result["message"] → "Sesi VNC berhasil dibuka ke 192.168.10.5 (server-Jakarta-01)"

        mgr.close_session("server-Jakarta-01")
        mgr.list_sessions()  → daftar semua sesi aktif
    """

    def __init__(self, noc_bridge=None):
        # Import di sini untuk hindari circular imports
        if noc_bridge is None:
            from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge
            noc_bridge = JarvisNOCBridge()
        self._bridge = noc_bridge
        self._sessions: Dict[str, RemoteSession] = {}        # session_id → session
        self._device_map: Dict[str, str] = {}                # target_device → session_id
        logger.info("[RemoteSessionManager] Initialized.")

    def open_session(
        self,
        operator_id: str,
        tool: str,
        host: str,
        target_device: str = "",
        port: int = 0,
        token: str = "",
    ) -> Dict:
        """
        Buka sesi remote baru.

        Args:
            operator_id: ID operator yang membuka sesi.
            tool: Jenis tool remote (vnc/rdp/ssh/anydesk/teamviewer).
            host: IP address atau hostname target.
            target_device: Nama device (untuk tracking).
            port: Port override (opsional, default sesuai tool).
            token: Auth token opsional.

        Returns:
            Dict dengan success, session_id, message, dan session details.
        """
        tool = tool.lower().strip()
        if tool not in SUPPORTED_TOOLS:
            return {
                "success": False,
                "message": (
                    f"❌ Tool '{tool}' tidak didukung. "
                    f"Pilihan: {', '.join(sorted(SUPPORTED_TOOLS))}"
                ),
            }

        # Cek jika device sudah ada sesi aktif
        if target_device and target_device in self._device_map:
            existing_sid = self._device_map[target_device]
            existing = self._sessions.get(existing_sid)
            if existing and existing.status == "ACTIVE":
                return {
                    "success": False,
                    "message": (
                        f"⚠️ Device {target_device} sudah memiliki sesi "
                        f"{existing.tool.upper()} aktif (ID: {existing_sid}). "
                        f"Tutup dahulu dengan: 'Jarvis, tutup remote {target_device}'"
                    ),
                }

        # Cek launcher service
        launcher_resp = self._bridge.get_launcher_status()
        if not launcher_resp.success or not launcher_resp.data.get("running", False):
            logger.warning("[RemoteSessionManager] Launcher offline, attempting start...")
            self._bridge.start_launcher()
            time.sleep(1)

        # Launch via NOCBridge
        actual_port = port or DEFAULT_PORTS.get(tool, 0)
        launch_resp = self._bridge.launch_remote(tool, host, token, actual_port)

        session_id = f"RS-{uuid.uuid4().hex[:8].upper()}"
        session_token = launch_resp.data.get("session_token", token or session_id)

        session = RemoteSession(
            session_id=session_id,
            operator_id=operator_id,
            tool=tool,
            host=host,
            port=actual_port,
            target_device=target_device or host,
            status="ACTIVE" if launch_resp.success else "FAILED",
            session_token=session_token,
        )
        self._sessions[session_id] = session
        if target_device:
            self._device_map[target_device] = session_id

        if launch_resp.success:
            logger.info(
                f"[RemoteSessionManager] ✅ Session opened: {session_id} "
                f"| {tool.upper()}@{host} | Operator={operator_id}"
            )
            return {
                "success": True,
                "session_id": session_id,
                "tool": tool.upper(),
                "host": host,
                "port": actual_port,
                "session_token": session_token,
                "message": (
                    f"✅ Sesi {tool.upper()} berhasil dibuka ke {host} "
                    f"({target_device or host}).\n"
                    f"🔐 Session ID: {session_id} | Token: {session_token}"
                ),
            }
        else:
            logger.error(
                f"[RemoteSessionManager] ❌ Failed to open: {session_id} "
                f"| Error: {launch_resp.error}"
            )
            return {
                "success": False,
                "session_id": session_id,
                "message": (
                    f"❌ Gagal membuka sesi {tool.upper()} ke {host}.\n"
                    f"Error: {launch_resp.error or 'Launcher tidak merespons.'}"
                ),
            }

    def close_session(
        self,
        target_device: str = "",
        session_id: str = "",
        reason: str = "Closed by operator",
    ) -> Dict:
        """Tutup sesi remote berdasarkan device name atau session ID."""
        # Resolve session
        sid = session_id
        if not sid and target_device:
            sid = self._device_map.get(target_device)

        if not sid or sid not in self._sessions:
            return {
                "success": False,
                "message": (
                    f"❌ Tidak ada sesi aktif untuk "
                    f"{'device ' + target_device if target_device else 'session ' + session_id}. "
                    f"Sesi aktif: {self.active_count()}"
                ),
            }

        session = self._sessions[sid]
        session.status = "CLOSED"
        session.closed_at = time.time()
        session.close_reason = reason

        # Cleanup device map
        if session.target_device in self._device_map:
            del self._device_map[session.target_device]

        logger.info(
            f"[RemoteSessionManager] Session closed: {sid} "
            f"| {session.tool.upper()}@{session.host}"
        )
        return {
            "success": True,
            "message": (
                f"✅ Sesi {session.tool.upper()} ke {session.host} "
                f"({session.target_device}) berhasil ditutup.\n"
                f"Durasi: {self._format_duration(session.opened_at, session.closed_at)}"
            ),
        }

    def list_sessions(self) -> str:
        """Format daftar semua sesi aktif untuk output JARVIS."""
        active = [s for s in self._sessions.values() if s.status == "ACTIVE"]
        if not active:
            return "✅ Tidak ada sesi remote yang aktif saat ini."
        lines = [f"🖥️  {len(active)} sesi remote aktif:\n"]
        for s in active:
            duration = self._format_duration(s.opened_at, time.time())
            lines.append(
                f"  • [{s.tool.upper()}] {s.target_device} → {s.host}:{s.port} "
                f"| Operator: {s.operator_id} | Durasi: {duration}"
            )
        return "\n".join(lines)

    def active_count(self) -> int:
        return sum(1 for s in self._sessions.values() if s.status == "ACTIVE")

    def detect_available_tools(self) -> str:
        """Deteksi tool remote yang tersedia dan format untuk JARVIS."""
        resp = self._bridge.detect_remote_tools()
        if not resp.success:
            return "Tidak dapat mendeteksi tool remote."
        return resp.summary or "Tool remote terdeteksi."

    @staticmethod
    def _format_duration(start: float, end: float) -> str:
        """Format durasi dalam format human-readable."""
        secs = int(end - start)
        if secs < 60:
            return f"{secs} detik"
        elif secs < 3600:
            return f"{secs // 60} menit {secs % 60} detik"
        else:
            h = secs // 3600
            m = (secs % 3600) // 60
            return f"{h} jam {m} menit"
