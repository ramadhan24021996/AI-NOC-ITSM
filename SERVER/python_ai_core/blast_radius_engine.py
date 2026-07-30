"""
P8: Blast Radius Engine
OSI Incident Ops Hardening v3.0

Features:
  - Traverses fleet_topology (site links) and device_dependencies (device dependency graph)
  - Computes affected nodes, dependency depth, critical paths, and blast score
  - Enforces severity auto-increase rule if routers/core switches/gateways/servers are impacted
  - Saves computation to blast_radius_registry
  - Listens on NATS subject `incident.blast.calculate` and publishes to `incident.blast.result`
"""
import asyncio
import json
import logging
import os
import psycopg2
from audit_logger import write_audit_log, get_db

logger = logging.getLogger("BLAST_RADIUS_ENGINE")

class BlastRadiusEngine:
    def __init__(self, nc=None):
        self.nc = nc

    async def start(self):
        logger.info("[BLAST RADIUS ENGINE] Starting Blast Radius Engine...")
        if self.nc:
            await self.nc.subscribe("incident.site.*.blast.calculate", queue="blast-radius-group", cb=self.handle_calculation_request)
            logger.info("[BLAST RADIUS ENGINE] Subscribed to NATS 'incident.site.*.blast.calculate'")

    async def handle_calculation_request(self, msg):
        """
        NATS payload:
        {
          "incident_id": 123,
          "device_id": "Jakarta-Router-01"  // matches pc_name
        }
        """
        try:
            data = json.loads(msg.data.decode())
            incident_id = int(data.get("incident_id", 0))
            device_id = data.get("device_id")

            if not incident_id or not device_id:
                logger.warning("[BLAST RADIUS ENGINE] Missing incident_id or device_id in request")
                return

            result = self.calculate_blast_radius(incident_id, device_id)

            if self.nc:
                site_id_str = "global"
                try:
                    db_conn = get_db()
                    with db_conn.cursor() as cur:
                        cur.execute("SELECT site_id FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                        row = cur.fetchone()
                        if row and row[0]:
                            s = str(row[0]).lower().strip()
                            s = s.replace(" ", "_").replace(".", "_")
                            site_id_str = s
                    db_conn.close()
                except Exception as dberr:
                    logger.warning(f"Failed to query site ID for blast radius notify: {dberr}")

                await self.nc.publish(f"incident.site.{site_id_str}.blast.result", json.dumps(result).encode())
                # Also publish to the live chat thread if requested using sharded subject
                await self.nc.publish(f"chat.site.{site_id_str}.thread.{incident_id}", json.dumps({
                    "type": "SYSTEM_INCIDENT",
                    "sender_type": "SYSTEM",
                    "incident_id": incident_id,
                    "message": f"📊 Blast Radius Computed: {len(result['affected_nodes'])} nodes affected. Blast Score: {result['blast_score']:.2f}. Severity: {result['severity']}",
                    "data": result
                }).encode())

        except Exception as e:
            logger.error("[BLAST RADIUS ENGINE] Calculation request failed: %s", e)

    def calculate_blast_radius(self, incident_id: int, root_device: str) -> dict:
        conn = get_db()
        try:
            affected_nodes = set()
            critical_paths = []
            max_depth = 0
            has_infrastructure_node = False
            infrastructure_types = ["router", "switch", "gateway", "server", "core"]

            # 1. Traverse device_dependencies (DFS/BFS)
            # Find all nodes that depend directly or indirectly on this root_device
            queue = [(root_device, 0, [root_device])]
            visited = set()

            while queue:
                current_node, depth, path = queue.pop(0)
                if current_node in visited:
                    continue
                visited.add(current_node)
                max_depth = max(max_depth, depth)

                # Check if current node is infrastructure
                node_lower = (current_node or "").lower()
                if any(inf in node_lower for inf in infrastructure_types):
                    has_infrastructure_node = True

                # Find dependent nodes: nodes where depends_on = current_node
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT pc_name, dep_type, criticality 
                        FROM device_dependencies 
                        WHERE depends_on = %s
                    """, (current_node,))
                    rows = cur.fetchall()
                    for dep_pc, dep_type, criticality in rows:
                        if dep_pc not in visited:
                            affected_nodes.add(dep_pc)
                            queue.append((dep_pc, depth + 1, path + [dep_pc]))
                            if criticality == "HIGH" or any(inf in (dep_pc or "").lower() for inf in infrastructure_types):
                                critical_paths.append({
                                    "path": path + [dep_pc],
                                    "type": dep_type,
                                    "criticality": criticality
                                })

            # 2. Traverse fleet_topology to calculate affected sites
            # Find site of root_device
            affected_sites = set()
            with conn.cursor() as cur:
                cur.execute("SELECT site_id FROM fleet_devices WHERE pc_name = %s", (root_device,))
                row = cur.fetchone()
                root_site = row[0] if row else "global"
                if root_site:
                    affected_sites.add(root_site)

                # Check site topology links from root site
                if root_site and root_site != "global":
                    cur.execute("""
                        SELECT site_id_to FROM fleet_topology 
                        WHERE site_id_from = %s AND is_critical = TRUE
                    """, (root_site,))
                    rows = cur.fetchall()
                    for r in rows:
                        affected_sites.add(r[0])

            # 3. Determine severity based on affected nodes count
            affected_count = len(affected_nodes)
            if affected_count <= 2:
                severity = "LOW"
            elif affected_count <= 5:
                severity = "MEDIUM"
            elif affected_count <= 10:
                severity = "HIGH"
            else:
                severity = "CRITICAL"

            # Auto-increase severity if infrastructure node is in critical path
            if has_infrastructure_node:
                if severity == "LOW":
                    severity = "MEDIUM"
                elif severity == "MEDIUM":
                    severity = "HIGH"
                elif severity == "HIGH":
                    severity = "CRITICAL"

            # Calculate blast score
            blast_score = float(affected_count * 10.0 + max_depth * 5.0)
            if has_infrastructure_node:
                blast_score *= 1.5

            result_payload = {
                "incident_id": incident_id,
                "root_device": root_device,
                "affected_nodes": list(affected_nodes),
                "affected_sites": list(affected_sites),
                "dependency_depth": max_depth,
                "critical_paths": critical_paths,
                "blast_score": blast_score,
                "severity": severity,
                "severity_multiplier": 1.5 if has_infrastructure_node else 1.0
            }

            # 4. Save to blast_radius_registry
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO blast_radius_registry 
                        (incident_id, affected_assets, affected_sites, scope, computed_at, computed_by,
                         root_device, severity_multiplier, dependency_depth, critical_paths, blast_score)
                    VALUES (%s, %s, %s, %s, NOW(), 'blast_radius_engine', %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                """, (
                    incident_id,
                    json.dumps(list(affected_nodes)),
                    list(affected_sites),
                    "SITE" if len(affected_sites) == 1 else "MULTI_SITE" if len(affected_sites) > 1 else "LOCAL",
                    root_device,
                    1.5 if has_infrastructure_node else 1.0,
                    max_depth,
                    json.dumps(critical_paths),
                    blast_score
                ))

                # Update fleet_incidents severity if calculated severity is higher
                cur.execute("SELECT severity FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                cur_severity_row = cur.fetchone()
                if cur_severity_row:
                    cur_sev = cur_severity_row[0]
                    # Simple severity hierarchy mapping
                    sev_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
                    if sev_rank.get(severity, 0) > sev_rank.get(cur_sev, 0):
                        cur.execute("UPDATE fleet_incidents SET severity = %s WHERE incident_id = %s", (severity, incident_id))

                # Audit logging
                write_audit_log(
                    action_type="BLAST_RADIUS_COMPUTED",
                    actor="blast_radius_engine",
                    target=f"incident_{incident_id}",
                    payload=result_payload,
                    conn=conn
                )

            conn.commit()
            logger.info("[BLAST RADIUS ENGINE] Incident #%d blast score: %.2f (severity: %s)", incident_id, blast_score, severity)
            return result_payload

        except Exception as e:
            logger.error("[BLAST RADIUS ENGINE] Failed to compute blast radius: %s", e)
            conn.rollback()
            raise
        finally:
            conn.close()
