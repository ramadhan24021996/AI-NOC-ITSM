"""
SERVER.jarvis.diagnostics.deep_diagnostics_adapter — JARVIS Deep Diagnostics Adapter
======================================================================================
P19 Implementation: Adapter untuk GetAgentDeepDiagnostics endpoint dashboard.

Deep Diagnostics menyediakan 10 section per device:
  1. System Health Core Metrics (CPU, RAM, Disk, OS version)
  2. Network Monitoring & Wi-Fi (IP, DNS, gateway, SSID)
  3. Security & Compliance (antivirus, firewall, encryption)
  4. Application Performance (top processes, app list)
  5. User Session & Access Control (active users, locked accounts)
  6. Event Log Analysis (critical Windows events)
  7. Printer Status (print queue, spooler status)
  8. Browser Monitoring (active tabs, bandwidth)
  9. Hardware Inventory (CPU model, RAM slots, NIC)
  10. Predictive Failure Indicators (SMART disk, error trends)

Dipanggil oleh JARVIS ketika operator bertanya:
  "Jarvis, deep diagnostics PC-STORE-01"
  "Jarvis, diagnosa mendalam server-jakarta-01"
"""
import logging
from typing import Any, Dict, List, Optional

from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge

logger = logging.getLogger("jarvis.diagnostics.deep_diagnostics")


class JarvisDeepDiagnosticsAdapter:
    """
    P19 — JARVIS Deep Diagnostics Adapter.
    Calls /api/agent_deep_diagnostics/:device dan memformat hasilnya
    sebagai laporan komprehensif per-device untuk JARVIS output.
    """

    # Section icons
    SECTION_ICONS = {
        "system_health": "💻",
        "network": "🌐",
        "security": "🔒",
        "applications": "📱",
        "user_sessions": "👤",
        "event_logs": "📋",
        "printers": "🖨️",
        "browser": "🌍",
        "hardware": "⚙️",
        "predictive": "🔮",
    }

    def __init__(self, noc_bridge: Optional[JarvisNOCBridge] = None):
        self.bridge = noc_bridge or JarvisNOCBridge()

    def get_full_diagnostics(self, device: str) -> str:
        """
        Ambil dan format deep diagnostics lengkap (10 section).

        Args:
            device: Nama device (e.g. "PC-STORE-01", "server-jakarta-01")

        Returns:
            Formatted string laporan diagnostics untuk JARVIS display.
        """
        resp = self.bridge.get_deep_diagnostics(device)

        if not resp.success:
            return (
                f"❌ Deep diagnostics {device} gagal: {resp.error or 'Device tidak merespons'}\n"
                f"Pastikan agent terinstall dan device online."
            )

        data = resp.data
        agent_data = data.get("agent_data", data)  # Flatten jika nested

        sections = [
            f"🔍 Deep Diagnostics Report — `{device}`",
            f"Status: {data.get('status', 'UNKNOWN')} | IP: {data.get('ip', '?')}",
            "=" * 50,
        ]

        # Section 1: System Health
        sections.append(self._format_system_health(agent_data))

        # Section 2: Network
        sections.append(self._format_network(agent_data))

        # Section 3: Security
        sections.append(self._format_security(agent_data))

        # Section 4: Applications (summary)
        sections.append(self._format_applications(agent_data))

        # Section 5: User Sessions
        sections.append(self._format_user_sessions(agent_data))

        # Section 6: Printers
        sections.append(self._format_printers(agent_data))

        # Section 7: Browser
        sections.append(self._format_browser(agent_data))

        # Section 8: Predictive Failure
        sections.append(self._format_predictive(agent_data))

        return "\n\n".join(filter(None, sections))

    def get_quick_summary(self, device: str) -> str:
        """Ringkasan cepat (hanya health metrics utama)."""
        resp = self.bridge.get_deep_diagnostics(device)
        if not resp.success:
            return f"❌ {device}: {resp.error or 'Gagal'}"

        data = resp.data
        agent = data.get("agent_data", data)
        cpu = agent.get("cpu_usage", "?")
        ram = agent.get("ram_usage", "?")
        disk = agent.get("disk_usage", "?")
        os_ver = agent.get("os_version", "?")
        status = data.get("status", "UNKNOWN")

        def _icon(v, warn=80, crit=90):
            try:
                val = float(str(v).replace("%", ""))
                if val >= crit:
                    return "🔴"
                elif val >= warn:
                    return "🟠"
                return "✅"
            except Exception:
                return "❓"

        return (
            f"💻 `{device}` [{status}]:\n"
            f"CPU: {cpu} {_icon(cpu)} | RAM: {ram} {_icon(ram)} | Disk: {disk} {_icon(disk)}\n"
            f"OS: {os_ver}"
        )

    def get_section(self, device: str, section: str) -> str:
        """Ambil satu section tertentu saja."""
        resp = self.bridge.get_deep_diagnostics(device)
        if not resp.success:
            return f"❌ Gagal mengambil data {device}: {resp.error}"

        data = resp.data
        agent = data.get("agent_data", data)
        section_map = {
            "health": self._format_system_health,
            "network": self._format_network,
            "security": self._format_security,
            "app": self._format_applications,
            "user": self._format_user_sessions,
            "printer": self._format_printers,
            "browser": self._format_browser,
            "predictive": self._format_predictive,
        }
        formatter = section_map.get(section.lower())
        if not formatter:
            return f"Section '{section}' tidak dikenal. Pilihan: {', '.join(section_map.keys())}"
        return formatter(agent) or f"Section {section}: tidak ada data."

    # ── Section Formatters ─────────────────────────────────────────────────────

    def _format_system_health(self, agent: Dict) -> str:
        cpu = agent.get("cpu_usage", "?")
        ram = agent.get("ram_usage", "?")
        disk = agent.get("disk_usage", "?")
        os_ver = agent.get("os_version", "?")
        uptime = agent.get("uptime", "?")
        temp = agent.get("cpu_temp", "?")
        return (
            f"💻 System Health:\n"
            f"├── CPU Usage  : {cpu}\n"
            f"├── RAM Usage  : {ram}\n"
            f"├── Disk Usage : {disk}\n"
            f"├── CPU Temp   : {temp}\n"
            f"├── OS Version : {os_ver}\n"
            f"└── Uptime     : {uptime}"
        )

    def _format_network(self, agent: Dict) -> str:
        net = agent.get("network_advanced", agent.get("network", {}))
        if not net:
            return ""
        ip = net.get("local_ip", "?")
        gateway = net.get("gateway", "?")
        dns = net.get("dns_servers", [])
        wifi_ssid = net.get("wifi_ssid", "N/A (wired)")
        latency = net.get("gateway_latency_ms", "?")
        return (
            f"🌐 Network:\n"
            f"├── IP Address  : {ip}\n"
            f"├── Gateway     : {gateway} ({latency}ms)\n"
            f"├── DNS Servers : {', '.join(dns[:2]) if dns else '?'}\n"
            f"└── Wi-Fi SSID  : {wifi_ssid}"
        )

    def _format_security(self, agent: Dict) -> str:
        sec = agent.get("security", {})
        if not sec:
            return ""
        av = sec.get("antivirus_status", "?")
        fw = sec.get("firewall_status", "?")
        enc = sec.get("disk_encryption", "?")
        last_scan = sec.get("last_scan_date", "?")
        return (
            f"🔒 Security:\n"
            f"├── Antivirus  : {av}\n"
            f"├── Firewall   : {fw}\n"
            f"├── Encryption : {enc}\n"
            f"└── Last Scan  : {last_scan}"
        )

    def _format_applications(self, agent: Dict) -> str:
        top_procs = agent.get("top_processes", [])
        if not top_procs:
            return ""
        if isinstance(top_procs, dict):
            top_procs = [top_procs]
        elif not isinstance(top_procs, list):
            return ""
        lines = ["📱 Top Processes (CPU):"]
        for p in top_procs[:5]:
            if isinstance(p, dict):
                name = p.get("name", "?")
                cpu = p.get("cpu_pct", "?")
                ram = p.get("ram_mb", "?")
                lines.append(f"  • {name}: CPU {cpu}% | RAM {ram}MB")
        return "\n".join(lines)

    def _format_user_sessions(self, agent: Dict) -> str:
        sessions = agent.get("user_sessions", [])
        if not sessions:
            return ""
        if isinstance(sessions, dict):
            sessions = [sessions]
        elif not isinstance(sessions, list):
            return ""
        lines = ["👤 User Sessions:"]
        for s in sessions[:3]:
            if isinstance(s, dict):
                user = s.get("username", "?")
                status = s.get("status", "?")
                lines.append(f"  • {user}: {status}")
        return "\n".join(lines)

    def _format_printers(self, agent: Dict) -> str:
        printers = agent.get("printers", [])
        if not printers:
            return ""
        if isinstance(printers, dict):
            printers = [printers]
        elif not isinstance(printers, list):
            return ""
        lines = ["🖨️ Printers:"]
        for p in printers[:5]:
            if isinstance(p, dict):
                name = p.get("name", "?")
                status = p.get("status", "?")
                queue = p.get("queue_jobs", 0)
                icon = "✅" if status == "Ready" else "⚠️"
                lines.append(f"  {icon} {name}: {status} | Queue: {queue} jobs")
        return "\n".join(lines)

    def _format_browser(self, agent: Dict) -> str:
        browser = agent.get("browser_monitoring", agent.get("browser", {}))
        if not browser:
            return ""
        tabs = browser.get("active_tabs", [])
        if isinstance(tabs, dict):
            tabs = [tabs]
        elif not isinstance(tabs, list):
            tabs = []
        bandwidth = browser.get("bandwidth_mbps", "?") if isinstance(browser, dict) else "?"
        lines = [f"🌍 Browser ({len(tabs)} tab aktif | BW: {bandwidth} Mbps):"]
        for tab in tabs[:3]:
            if isinstance(tab, dict):
                title = tab.get("title", "?")[:40]
                lines.append(f"  • {title}")
        return "\n".join(lines)

    def _format_predictive(self, agent: Dict) -> str:
        pred = agent.get("predictive_failure", {})
        if not pred:
            return ""
        disk_health = pred.get("disk_health", "?")
        error_rate = pred.get("error_rate_7d", "?")
        risk_level = pred.get("failure_risk", "LOW")
        icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "✅"}.get(risk_level, "❓")
        return (
            f"🔮 Predictive Failure:\n"
            f"├── Disk Health    : {disk_health}\n"
            f"├── Error Rate 7d  : {error_rate}\n"
            f"└── Failure Risk   : {icon} {risk_level}"
        )


class JarvisBrowserMonitorBridge:
    """
    P18 — JARVIS Browser Monitor Bridge.
    Menghubungkan browser extension telemetry (via browser_ext_server.go)
    ke JARVIS Runtime.

    Browser extension mengirim data ke agent (port 10001)
    → agent relay ke server → /api/browser_monitoring/
    → JARVIS bisa query via NOCBridge

    Commands yang bisa dijawab:
      "Jarvis, lihat aktivitas browser PC-STORE-01"
      "Jarvis, browser analytics hari ini"
      "Jarvis, device mana yang banyak browsing non-produktif?"
    """

    # Daftar domain yang dianggap tidak produktif untuk di-flag
    UNPRODUCTIVE_DOMAINS = [
        "youtube.com", "tiktok.com", "instagram.com", "facebook.com",
        "twitter.com", "x.com", "reddit.com", "9gag.com",
        "shopee.co.id", "tokopedia.com", "lazada.co.id",
        "netflix.com", "vidio.com",
    ]

    def __init__(self, noc_bridge: Optional[JarvisNOCBridge] = None):
        self.bridge = noc_bridge or JarvisNOCBridge()

    def get_live_tabs(self, device: str = "") -> str:
        """Ambil tab browser aktif secara live."""
        resp = self.bridge.get_live_browser_tabs()
        if not resp.success:
            return f"❌ Gagal mengambil live browser data: {resp.error}"

        all_tabs = resp.data if isinstance(resp.data, list) else []

        # Filter per device jika disebutkan
        if device:
            all_tabs = [
                t for t in all_tabs
                if device.lower() in str(t.get("device", "")).lower()
            ]

        if not all_tabs:
            return f"Tidak ada tab browser aktif {'untuk ' + device if device else 'saat ini'}."

        # Group by device
        by_device: Dict[str, List] = {}
        for tab in all_tabs:
            dev = tab.get("device", "unknown")
            by_device.setdefault(dev, []).append(tab)

        lines = [f"🌍 Live Browser Activity ({len(all_tabs)} tab aktif):\n"]
        for dev_name, tabs in sorted(by_device.items()):
            unproductive = sum(
                1 for t in tabs
                if any(d in str(t.get("url", "")) for d in self.UNPRODUCTIVE_DOMAINS)
            )
            lines.append(
                f"📱 {dev_name} — {len(tabs)} tab "
                f"{'| ⚠️ ' + str(unproductive) + ' non-produktif' if unproductive else ''}"
            )
            for tab in tabs[:3]:
                title = str(tab.get("title", "?"))[:45]
                url = str(tab.get("url", "?"))[:50]
                is_np = any(d in url for d in self.UNPRODUCTIVE_DOMAINS)
                icon = "🔴" if is_np else "✅"
                lines.append(f"  {icon} {title}")

        return "\n".join(lines)

    def get_analytics_summary(self) -> str:
        """Browser analytics ringkasan hari ini."""
        resp = self.bridge.get_browser_analytics()
        if not resp.success:
            return f"❌ Gagal mengambil browser analytics: {resp.error}"

        data = resp.data
        total_sessions = data.get("total_sessions", 0)
        total_tabs = data.get("total_tabs", 0)
        avg_duration = data.get("avg_session_duration_min", 0)
        top_sites = data.get("top_sites", [])
        devices_monitored = data.get("devices_monitored", 0)

        lines = [
            f"📊 Browser Analytics Summary:\n",
            f"├── Device monitored  : {devices_monitored}",
            f"├── Total sessions    : {total_sessions}",
            f"├── Total tab dibuka  : {total_tabs}",
            f"└── Avg. session dur. : {avg_duration} menit",
        ]

        if top_sites:
            lines.append("\nTop Sites:")
            for site in top_sites[:5]:
                domain = site.get("domain", "?")
                visits = site.get("visits", 0)
                is_np = any(d in domain for d in self.UNPRODUCTIVE_DOMAINS)
                icon = "🔴" if is_np else "✅"
                lines.append(f"  {icon} {domain}: {visits} kunjungan")

        return "\n".join(lines)

    def get_unproductive_report(self) -> str:
        """Laporan device dengan aktivitas browser tidak produktif."""
        resp = self.bridge.get_live_browser_tabs()
        if not resp.success:
            return f"❌ Tidak bisa generate laporan: {resp.error}"

        all_tabs = resp.data if isinstance(resp.data, list) else []
        device_np: Dict[str, int] = {}

        for tab in all_tabs:
            url = str(tab.get("url", ""))
            if any(d in url for d in self.UNPRODUCTIVE_DOMAINS):
                dev = tab.get("device", "unknown")
                device_np[dev] = device_np.get(dev, 0) + 1

        if not device_np:
            return "✅ Tidak ada aktivitas browser tidak produktif terdeteksi saat ini."

        lines = [f"⚠️ Device dengan aktivitas tidak produktif ({len(device_np)} device):\n"]
        for dev, count in sorted(device_np.items(), key=lambda x: -x[1]):
            lines.append(f"  🔴 {dev}: {count} tab non-produktif")

        return "\n".join(lines)
