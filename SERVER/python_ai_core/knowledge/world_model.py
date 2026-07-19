"""
Enterprise Autonomous AI OS — Phase 6: Step 6.2
World Model

Memberikan AI peta mental produksi: topology, dependensi layanan,
dan dampak bisnis dari kegagalan perangkat.

Schema verified against production DB:
  - fleet_devices (PK: pc_name, columns: pc_name, site_id, ip, hostname, online, os_version, hardware_info)
  - fleet_topology (columns: site_id_from, site_id_to, link_type, bandwidth_mbps, is_critical)
  - device_dependencies (columns: pc_name, depends_on, dep_type, criticality)
  - network_paths (as-is)
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("WORLD_MODEL")


class WorldModel:
    """
    AI's mental model of the production infrastructure.
    Answers questions like:
      - "What depends on this device?"
      - "What is the blast radius if this switch goes down?"
      - "What is the critical path for this site?"
    """

    def __init__(self, db_conn=None):
        self._conn = db_conn

    def get_device_context(self, device_name: str) -> Dict[str, Any]:
        """
        Return full context for a device: info, dependencies, topology.
        Uses verified column names: pc_name (PK), depends_on, dep_type.
        """
        ctx: Dict[str, Any] = {}
        if not self._conn:
            return ctx
        try:
            with self._conn.cursor() as cur:
                # 1. Device info — PK is pc_name, not device_id
                cur.execute("""
                    SELECT pc_name, ip, hostname, online, os_version, site_id, hardware_info
                    FROM fleet_devices
                    WHERE hostname ILIKE %s OR ip = %s OR pc_name ILIKE %s
                    LIMIT 1
                """, (f"%{device_name}%", device_name, f"%{device_name}%"))
                row = cur.fetchone()
                if row:
                    ctx["device"] = {
                        "id": row[0],       # pc_name is the PK
                        "pc_name": row[0],
                        "ip": row[1],
                        "hostname": row[2],
                        "online": row[3],
                        "os": row[4],
                        "site_id": row[5],
                        "hardware": row[6] if isinstance(row[6], dict) else {}
                    }

                pc_name = ctx.get("device", {}).get("pc_name")

                # 2. Dependencies (what this device depends on) — uses pc_name + depends_on
                if pc_name:
                    cur.execute("""
                        SELECT depends_on, dep_type, criticality
                        FROM device_dependencies
                        WHERE pc_name = %s
                        LIMIT 10
                    """, (pc_name,))
                    ctx["depends_on"] = [
                        {"device": r[0], "type": r[1], "criticality": r[2]}
                        for r in cur.fetchall()
                    ]

                    # 3. Reverse dependencies (who depends on this device)
                    cur.execute("""
                        SELECT pc_name, dep_type, criticality
                        FROM device_dependencies
                        WHERE depends_on = %s
                        LIMIT 20
                    """, (pc_name,))
                    ctx["depended_by"] = [
                        {"device": r[0], "type": r[1], "criticality": r[2]}
                        for r in cur.fetchall()
                    ]
                else:
                    ctx["depends_on"] = []
                    ctx["depended_by"] = []

        except Exception as e:
            logger.error("[WORLD_MODEL] get_device_context error: %s", e)
        return ctx

    def get_blast_radius(self, device_name: str) -> Dict[str, Any]:
        """
        Calculate failure propagation impact for a device.
        Reuses BlastRadiusEngine if available, falls back to dependency count.
        """
        try:
            from blast_radius_engine import BlastRadiusEngine
            engine = BlastRadiusEngine()
            return engine.calculate(device_name, self._conn) if self._conn else {}
        except Exception as e:
            logger.warning("[WORLD_MODEL] BlastRadiusEngine fallback: %s", e)
            ctx = self.get_device_context(device_name)
            return {
                "device": device_name,
                "affected_count": len(ctx.get("depended_by", [])),
                "dependencies": ctx.get("depended_by", []),
            }

    def get_site_topology(self, site_id: str) -> Dict[str, Any]:
        """
        Return full topology links for a site.
        fleet_topology has site_id_from and site_id_to — no single site_id column.
        """
        if not self._conn:
            return dict()
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT site_id_from, site_id_to, link_type, bandwidth_mbps, latency_ms, is_critical
                    FROM fleet_topology
                    WHERE site_id_from = %s OR site_id_to = %s
                    LIMIT 20
                """, (site_id, site_id))
                rows = cur.fetchall()
                return {
                    "site_id": site_id,
                    "topology_links": [
                        {
                            "from": r[0], "to": r[1], "link_type": r[2],
                            "bandwidth_mbps": r[3], "latency_ms": r[4], "is_critical": r[5]
                        }
                        for r in rows
                    ]
                }
        except Exception as e:
            logger.error("[WORLD_MODEL] get_site_topology error: %s", e)
            return dict()

    def get_critical_path(self, site_id: Optional[str] = None) -> List[Dict]:
        """
        Identify devices that are single points of failure (most depended upon).
        Uses verified column names: depends_on (not depends_on_device).
        """
        if not self._conn:
            return list()
        try:
            with self._conn.cursor() as cur:
                if site_id:
                    cur.execute("""
                        SELECT dd.depends_on, COUNT(*) as dependent_count,
                               fd.online, fd.hostname
                        FROM device_dependencies dd
                        LEFT JOIN fleet_devices fd ON fd.pc_name = dd.depends_on
                        WHERE fd.site_id = %s
                        GROUP BY dd.depends_on, fd.online, fd.hostname
                        ORDER BY dependent_count DESC
                        LIMIT 10
                    """, (site_id,))
                else:
                    cur.execute("""
                        SELECT dd.depends_on, COUNT(*) as dependent_count,
                               fd.online, fd.hostname
                        FROM device_dependencies dd
                        LEFT JOIN fleet_devices fd ON fd.pc_name = dd.depends_on
                        GROUP BY dd.depends_on, fd.online, fd.hostname
                        ORDER BY dependent_count DESC
                        LIMIT 10
                    """)
                rows = cur.fetchall()
                return [
                    {"device_id": r[0], "dependent_count": r[1],
                     "online": r[2], "hostname": r[3]}
                    for r in rows
                ]
        except Exception as e:
            logger.error("[WORLD_MODEL] get_critical_path error: %s", e)
            return list()

    def get_infrastructure_summary(self) -> Dict[str, Any]:
        """
        Return high-level summary of the managed infrastructure.
        """
        if not self._conn:
            return dict()
        try:
            with self._conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM fleet_devices WHERE online = TRUE")
                online = cur.fetchone()[0]

                cur.execute("SELECT COUNT(*) FROM fleet_devices WHERE online = FALSE")
                offline = cur.fetchone()[0]

                cur.execute("SELECT COUNT(DISTINCT site_id) FROM fleet_sites")
                sites = cur.fetchone()[0]

                cur.execute("""
                    SELECT COUNT(*) FROM incidents
                    WHERE timestamp > NOW() - INTERVAL '24 hours'
                """)
                incidents_24h = cur.fetchone()[0]

            return {
                "online_devices":  online,
                "offline_devices": offline,
                "total_sites":     sites,
                "incidents_24h":   incidents_24h,
                "availability_pct": round(online / max(online + offline, 1) * 100, 2),
            }
        except Exception as e:
            logger.error("[WORLD_MODEL] infrastructure summary error: %s", e)
            return dict()
