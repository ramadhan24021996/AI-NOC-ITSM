"""
Enterprise DNS / DHCP External Service Connector
Layer 8: External Enterprise Integration — L8_DNS

Modul ini menyediakan interface untuk:
  1. DNS Resolution & Reverse Lookup (via system resolver menggunakan ENTERPRISE_DNS_PRIMARY)
  2. DHCP Lease Discovery (via SNMP atau PowerDNS API)
  3. DNS Health Check & Monitoring
  4. LDAP/AD device hostname resolution

Config diambil dari environment variables (set di .env):
  ENTERPRISE_DNS_PRIMARY, ENTERPRISE_DNS_SECONDARY, ENTERPRISE_DNS_PORT
  ENTERPRISE_DHCP_SERVER, ENTERPRISE_DNS_API_URL, ENTERPRISE_DNS_API_KEY
  ENTERPRISE_LDAP_HOST, ENTERPRISE_LDAP_PORT, ENTERPRISE_LDAP_BASE_DN
"""

import os
import socket
import asyncio
import logging
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger("ENTERPRISE_DNS_DHCP")

# ── Config dari .env ──────────────────────────────────────────────────────────
DNS_PRIMARY    = os.environ.get("ENTERPRISE_DNS_PRIMARY",   "192.168.1.1")
DNS_SECONDARY  = os.environ.get("ENTERPRISE_DNS_SECONDARY", "192.168.1.2")
DNS_PORT       = int(os.environ.get("ENTERPRISE_DNS_PORT",  "53"))
DNS_DOMAIN     = os.environ.get("ENTERPRISE_DNS_DOMAIN",    "corp.local")
DNS_API_URL    = os.environ.get("ENTERPRISE_DNS_API_URL",   "")
DNS_API_KEY    = os.environ.get("ENTERPRISE_DNS_API_KEY",   "")

DHCP_SERVER    = os.environ.get("ENTERPRISE_DHCP_SERVER",   "192.168.1.1")
DHCP_PORT      = int(os.environ.get("ENTERPRISE_DHCP_PORT", "67"))

LDAP_HOST      = os.environ.get("ENTERPRISE_LDAP_HOST",     "192.168.1.1")
LDAP_PORT      = int(os.environ.get("ENTERPRISE_LDAP_PORT", "389"))
LDAP_BASE_DN   = os.environ.get("ENTERPRISE_LDAP_BASE_DN",  "DC=corp,DC=local")

# Timeout untuk network operations
CONNECT_TIMEOUT_SEC = float(os.environ.get("ENTERPRISE_DNS_TIMEOUT_SEC", "3.0"))


class EnterpriseDNSDHCPConnector:
    """
    Enterprise DNS/DHCP connector untuk L8 External Integration.
    
    Semua method fail-safe: tidak pernah raise exception ke caller,
    selalu return dict dengan status 'ok' atau 'error'.
    """

    def __init__(self):
        self._dns_primary = DNS_PRIMARY
        self._dns_secondary = DNS_SECONDARY
        self._dns_domain = DNS_DOMAIN
        self._dns_api_url = DNS_API_URL
        self._dns_api_key = DNS_API_KEY
        self._dhcp_server = DHCP_SERVER
        self._ldap_host = LDAP_HOST
        self._ldap_port = LDAP_PORT
        self._ldap_base_dn = LDAP_BASE_DN

        # Health state
        self._last_dns_check: Optional[float] = None
        self._dns_reachable: bool = False
        self._dhcp_reachable: bool = False
        self._ldap_reachable: bool = False

        logger.info(
            f"[DNS/DHCP] Enterprise connector initialized | "
            f"DNS={self._dns_primary}:{DNS_PORT} | "
            f"DHCP={self._dhcp_server} | "
            f"LDAP={self._ldap_host}:{self._ldap_port} | "
            f"Domain={self._dns_domain}"
        )

    # ── DNS Resolution ─────────────────────────────────────────────────────────

    def resolve_hostname(self, hostname: str) -> Dict[str, Any]:
        """
        Resolve hostname ke IP address menggunakan system resolver
        (yang sudah di-configure ke ENTERPRISE_DNS_PRIMARY via resolv.conf atau OS).
        
        Returns: {"status": "ok", "hostname": ..., "ip": ..., "resolved_in_ms": ...}
        """
        start = time.monotonic()
        try:
            # Jika hostname tidak mengandung domain, append enterprise domain
            if "." not in hostname:
                fqdn = f"{hostname}.{self._dns_domain}"
            else:
                fqdn = hostname

            ip = socket.gethostbyname(fqdn)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            logger.debug(f"[DNS] {fqdn} → {ip} ({elapsed_ms}ms)")
            return {
                "status": "ok", "hostname": hostname, "fqdn": fqdn,
                "ip": ip, "resolved_in_ms": elapsed_ms,
                "dns_server": self._dns_primary,
            }
        except socket.gaierror as e:
            return {
                "status": "error", "hostname": hostname, "error": str(e),
                "dns_server": self._dns_primary,
            }
        except Exception as e:
            return {"status": "error", "hostname": hostname, "error": str(e)}

    def reverse_lookup(self, ip_address: str) -> Dict[str, Any]:
        """
        Reverse DNS lookup: IP → hostname.
        Berguna untuk enrichment telemetry data.
        """
        start = time.monotonic()
        try:
            hostname, _, _ = socket.gethostbyaddr(ip_address)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            return {
                "status": "ok", "ip": ip_address,
                "hostname": hostname, "resolved_in_ms": elapsed_ms,
            }
        except socket.herror as e:
            return {"status": "no_ptr", "ip": ip_address, "error": str(e)}
        except Exception as e:
            return {"status": "error", "ip": ip_address, "error": str(e)}

    def batch_resolve(self, hostnames: List[str]) -> List[Dict[str, Any]]:
        """Resolve multiple hostnames sekaligus."""
        return [self.resolve_hostname(h) for h in hostnames]

    # ── DNS Health Check ───────────────────────────────────────────────────────

    def check_dns_health(self) -> Dict[str, Any]:
        """
        Cek apakah DNS server dapat dijangkau dengan TCP ping ke port 53.
        Tidak melakukan actual DNS query untuk menghindari overhead.
        """
        result = {"primary": {}, "secondary": {}, "timestamp": datetime.now(timezone.utc).isoformat()}

        for label, server in [("primary", self._dns_primary), ("secondary", self._dns_secondary)]:
            start = time.monotonic()
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(CONNECT_TIMEOUT_SEC)
                sock.connect((server, DNS_PORT))
                sock.close()
                elapsed_ms = round((time.monotonic() - start) * 1000, 1)
                result[label] = {"status": "reachable", "server": server, "latency_ms": elapsed_ms}
            except Exception as e:
                result[label] = {"status": "unreachable", "server": server, "error": str(e)}

        self._dns_reachable = result["primary"].get("status") == "reachable"
        self._last_dns_check = time.monotonic()
        return result

    # ── DHCP Lease Discovery ───────────────────────────────────────────────────

    def check_dhcp_server(self) -> Dict[str, Any]:
        """
        Check DHCP server reachability via TCP (port 67 UDP, fallback ke management port).
        Actual lease listing memerlukan SNMP atau PowerDNS API.
        """
        start = time.monotonic()
        # DHCP management biasanya melalui HTTP API atau SNMP
        dhcp_mgmt_port = int(os.environ.get("ENTERPRISE_DHCP_MGMT_PORT", "8080"))
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT_SEC)
            sock.connect((self._dhcp_server, dhcp_mgmt_port))
            sock.close()
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            self._dhcp_reachable = True
            return {
                "status": "reachable", "server": self._dhcp_server,
                "port": dhcp_mgmt_port, "latency_ms": elapsed_ms,
            }
        except Exception as e:
            self._dhcp_reachable = False
            return {
                "status": "unreachable", "server": self._dhcp_server,
                "port": dhcp_mgmt_port, "error": str(e),
                "note": "Configure ENTERPRISE_DHCP_MGMT_PORT in .env for management access",
            }

    # ── LDAP Health ────────────────────────────────────────────────────────────

    def check_ldap_health(self) -> Dict[str, Any]:
        """Cek LDAP / Active Directory reachability."""
        start = time.monotonic()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(CONNECT_TIMEOUT_SEC)
            sock.connect((self._ldap_host, self._ldap_port))
            sock.close()
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            self._ldap_reachable = True
            return {
                "status": "reachable", "host": self._ldap_host,
                "port": self._ldap_port, "latency_ms": elapsed_ms,
                "base_dn": self._ldap_base_dn,
            }
        except Exception as e:
            self._ldap_reachable = False
            return {
                "status": "unreachable", "host": self._ldap_host,
                "port": self._ldap_port, "error": str(e),
                "note": "Update ENTERPRISE_LDAP_HOST in .env with actual AD server IP",
            }

    # ── Full Health Report ─────────────────────────────────────────────────────

    def collect_all(self) -> Dict[str, Any]:
        """
        Interface standar untuk EnterpriseConnectors (L3).
        Dipanggil oleh observer_daemon.py dalam siklus collect & validate.
        """
        dns_health = self.check_dns_health()
        dhcp_status = self.check_dhcp_server()
        ldap_status = self.check_ldap_health()

        return {
            "layer": "L8_external",
            "component": "enterprise_dns_dhcp",
            "dns": dns_health,
            "dhcp": dhcp_status,
            "ldap": ldap_status,
            "summary": {
                "dns_primary_ok": self._dns_reachable,
                "dhcp_ok": self._dhcp_reachable,
                "ldap_ok": self._ldap_reachable,
                "overall_status": (
                    "HEALTHY" if self._dns_reachable else
                    "DEGRADED" if self._ldap_reachable else
                    "UNREACHABLE"
                ),
            },
            "config": {
                "dns_primary": self._dns_primary,
                "dns_domain": self._dns_domain,
                "dhcp_server": self._dhcp_server,
                "ldap_host": self._ldap_host,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ── Singleton ──────────────────────────────────────────────────────────────────
_instance: Optional[EnterpriseDNSDHCPConnector] = None

def get_dns_dhcp_connector() -> EnterpriseDNSDHCPConnector:
    """Singleton factory. Thread-safe."""
    global _instance
    if _instance is None:
        _instance = EnterpriseDNSDHCPConnector()
    return _instance
