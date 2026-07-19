"""
Enterprise AI OS — Asset Context Engine
Sprint: Gap Closure 1A

Tujuan:
Mengambil konteks aset (SLA, criticality, role, environment, business_owner,
maintenance_window) dari tabel `assets` SEBELUM pipeline reasoning dimulai.

AI harus tahu bahwa restart server database produksi berbeda risikonya
dengan restart workstation client.

ZERO-MOCK: Semua data berasal dari tabel `assets` produksi (36 kolom).
"""

import logging
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("ASSET_CONTEXT_ENGINE")


class AssetContextEngine:
    """
    Mengambil dan menggabungkan konteks aset penuh dari database sebelum
    reasoning pipeline dimulai. Output berupa dict yang langsung disuntikkan
    ke dalam prompt LLM dan parameter PolicyEngine.
    """

    def __init__(self, db_conn=None):
        self.conn = db_conn

    def _get_conn(self):
        if self.conn and not self.conn.closed:
            return self.conn
        import psycopg2
        return psycopg2.connect(
            host=os.getenv("DB_HOST", "postgres"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "osi_system"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "")
        )

    def fetch(self, hostname: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Query tabel `assets` berdasarkan hostname atau IP.
        Mengembalikan konteks lengkap aset untuk dipakai oleh:
        - PolicyEngine (criticality, blast_radius override)
        - Prompt LLM (role, environment, SLA)
        - HypothesisEngine (bobot risk berdasarkan aset kritis)
        """
        default = {
            "found": False,
            "hostname": hostname,
            "device_type": "UNKNOWN",
            "role": "UNKNOWN",
            "operating_system": "UNKNOWN",
            "criticality": "MEDIUM",
            "environment": "PRODUCTION",
            "business_owner": "NOC",
            "sla": 99.0,
            "maintenance_window": None,
            "department": "IT",
            "site_id": None,
            "trust_score": 100.0,
            "health_score": 100.0,
            "last_seen": None,
            "context_summary": f"Asset '{hostname}' — konteks tidak ditemukan di database, menggunakan default MEDIUM criticality."
        }

        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                # Query utama berdasarkan hostname (case-insensitive)
                query = """
                    SELECT
                        asset_id, hostname, ip_address, device_type,
                        operating_system, department, business_owner,
                        technical_owner, criticality, sla, maintenance_window,
                        status, last_seen, trust_score, health_score,
                        site_id, model, vendor
                    FROM assets
                    WHERE LOWER(hostname) = LOWER(%s)
                """
                params = [hostname]

                if ip_address:
                    query += " OR ip_address = %s"
                    params.append(ip_address)

                query += " LIMIT 1"
                cur.execute(query, params)
                row = cur.fetchone()

                if not row:
                    logger.warning(f"[ASSET_CTX] Hostname '{hostname}' tidak ditemukan di tabel assets.")
                    return default

                (
                    asset_id, db_hostname, db_ip, device_type,
                    os_name, department, business_owner,
                    tech_owner, criticality, sla, maint_window,
                    status, last_seen, trust_score, health_score,
                    site_id, model, vendor
                ) = row

                # Tentukan "role" berdasarkan device_type
                role_map = {
                    "server": "SERVER",
                    "workstation": "CLIENT",
                    "pc": "CLIENT",
                    "switch": "NETWORK_DEVICE",
                    "router": "NETWORK_DEVICE",
                    "firewall": "SECURITY_DEVICE",
                    "database": "DATABASE_SERVER",
                    "printer": "PERIPHERAL",
                    "laptop": "CLIENT",
                }
                role = role_map.get((device_type or "").lower(), "SERVER")

                # Risk multiplier berdasarkan criticality
                risk_multiplier = {
                    "CRITICAL": 3.0,
                    "HIGH": 2.0,
                    "MEDIUM": 1.0,
                    "LOW": 0.5,
                }.get((criticality or "MEDIUM").upper(), 1.0)

                ctx = {
                    "found": True,
                    "asset_id": asset_id,
                    "hostname": db_hostname,
                    "ip_address": db_ip,
                    "device_type": device_type or "UNKNOWN",
                    "role": role,
                    "operating_system": os_name or "UNKNOWN",
                    "model": model or "UNKNOWN",
                    "vendor": vendor or "UNKNOWN",
                    "criticality": (criticality or "MEDIUM").upper(),
                    "environment": "PRODUCTION",  # default, bisa dikembangkan dari tags
                    "business_owner": business_owner or "NOC",
                    "technical_owner": tech_owner or "NOC",
                    "department": department or "IT",
                    "sla": float(sla) if sla is not None else 99.0,
                    "maintenance_window": str(maint_window) if maint_window else None,
                    "status": status or "UNKNOWN",
                    "last_seen": str(last_seen) if last_seen else None,
                    "trust_score": float(trust_score) if trust_score is not None else 100.0,
                    "health_score": float(health_score) if health_score is not None else 100.0,
                    "site_id": site_id,
                    "risk_multiplier": risk_multiplier,
                    "context_summary": (
                        f"Aset: {db_hostname} | Role: {role} | Tipe: {device_type} | "
                        f"OS: {os_name} | Criticality: {criticality} | SLA: {sla}% | "
                        f"Owner: {business_owner} | Dept: {department} | "
                        f"Maintenance: {maint_window or 'Tidak dijadwalkan'} | "
                        f"Trust Score: {trust_score}"
                    )
                }

                logger.info(
                    f"[ASSET_CTX] Konteks aset '{hostname}' ditemukan: "
                    f"criticality={criticality}, role={role}, SLA={sla}%"
                )
                return ctx

        except Exception as e:
            logger.error(f"[ASSET_CTX] Gagal query asset context untuk '{hostname}': {e}")
            return default

    def build_risk_context_prompt(self, asset_ctx: Dict[str, Any]) -> str:
        """
        Menghasilkan teks konteks yang disuntikkan ke dalam system prompt LLM
        agar AI memahami risiko aset SEBELUM memberikan rekomendasi.
        """
        if not asset_ctx.get("found"):
            return (
                "PERINGATAN: Konteks aset tidak ditemukan. "
                "Asumsikan aset adalah SERVER PRODUKSI KRITIS dan gunakan pendekatan KONSERVATIF."
            )

        crit = asset_ctx.get("criticality", "MEDIUM")
        sla = asset_ctx.get("sla", 99.0)
        role = asset_ctx.get("role", "SERVER")
        maint = asset_ctx.get("maintenance_window")

        risk_note = ""
        if crit == "CRITICAL":
            risk_note = (
                "PERINGATAN KRITIS: Aset ini adalah komponen KRITIAL dengan SLA "
                f"{sla}%. Setiap tindakan yang menyebabkan downtime HARUS melalui "
                "persetujuan HITL dan rollback plan. JANGAN eksekusi restart tanpa approval."
            )
        elif crit == "HIGH":
            risk_note = (
                f"PERINGATAN TINGGI: Aset HIGH criticality (SLA {sla}%). "
                "Tindakan berisiko memerlukan approval operator."
            )
        elif maint:
            risk_note = f"Catatan: Aset dalam maintenance window: {maint}. Tindakan mungkin aman."
        else:
            risk_note = f"Aset dengan criticality {crit}. Pertimbangkan dampak sebelum eksekusi."

        return (
            f"KONTEKS ASET:\n"
            f"- Hostname: {asset_ctx.get('hostname')}\n"
            f"- Role: {role} | Device Type: {asset_ctx.get('device_type')}\n"
            f"- OS: {asset_ctx.get('operating_system')}\n"
            f"- Criticality: {crit} | SLA: {sla}%\n"
            f"- Business Owner: {asset_ctx.get('business_owner')}\n"
            f"- Department: {asset_ctx.get('department')}\n"
            f"- Trust Score: {asset_ctx.get('trust_score')}/100\n"
            f"- Health Score: {asset_ctx.get('health_score')}/100\n"
            f"\n{risk_note}"
        )


_instance: Optional[AssetContextEngine] = None


def get_asset_context_engine(db_conn=None) -> AssetContextEngine:
    global _instance
    if _instance is None:
        _instance = AssetContextEngine(db_conn=db_conn)
    elif db_conn and _instance.conn != db_conn:
        _instance.conn = db_conn
    return _instance
