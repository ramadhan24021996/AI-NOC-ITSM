import os
import psycopg2
import logging
from datetime import datetime
import uuid
import json

logger = logging.getLogger("DISCOVERY_ENGINE")

class DiscoveryEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def run_discovery(self):
        """Scans fleet_devices and network_scans to populate the new World Model Enterprise Asset Graph."""
        logger.info("[DISCOVERY] Starting Enterprise Asset Discovery...")
        if not self.db:
            return

        try:
            with self.db.cursor() as cur:
                # 1. Discover Sites (from fleet_devices location if any, or default)
                cur.execute("SELECT DISTINCT site_id FROM fleet_devices WHERE site_id IS NOT NULL AND site_id != ''")
                locations = cur.fetchall()
                site_map = {}
                for loc in locations:
                    site_name = loc[0]
                    cur.execute("INSERT INTO sites (name, description) VALUES (%s, 'Auto-discovered site') ON CONFLICT (name) DO NOTHING RETURNING id", (site_name,))
                    row = cur.fetchone()
                    if row:
                        site_map[site_name] = row[0]
                    else:
                        cur.execute("SELECT id FROM sites WHERE name = %s", (site_name,))
                        site_map[site_name] = cur.fetchone()[0]

                # If no sites, create a default HQ
                if "HQ" not in site_map:
                    cur.execute("INSERT INTO sites (name, description) VALUES ('HQ', 'Default HQ Site') ON CONFLICT (name) DO NOTHING RETURNING id")
                    row = cur.fetchone()
                    if row:
                        site_map["HQ"] = row[0]
                    else:
                        cur.execute("SELECT id FROM sites WHERE name = 'HQ'")
                        site_map["HQ"] = cur.fetchone()[0]

                # 2. Migrate fleet_devices to assets table
                cur.execute("SELECT pc_name, ip, status, last_seen, hardware_info, os_version, telemetry_version, site_id FROM fleet_devices")
                devices = cur.fetchall()
                
                for dev in devices:
                    pc_name, ip, status, last_seen, hardware_info, os_version, agent_version, location = dev
                    site_id_val = site_map.get(location, site_map["HQ"])
                    
                    hw = {}
                    if hardware_info:
                        if isinstance(hardware_info, str):
                            try:
                                hw = json.loads(hardware_info)
                            except:
                                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                        elif isinstance(hardware_info, dict):
                            hw = hardware_info
                    
                    mac = hw.get("mac", "")
                    # Decide Device Type
                    device_type = "Windows PC"
                    if "linux" in str(os_version).lower():
                        device_type = "Linux"
                    elif "server" in str(os_version).lower() or "server" in str(pc_name).lower():
                        device_type = "Server"
                    
                    # Check if asset exists
                    cur.execute("SELECT asset_id FROM assets WHERE hostname = %s", (pc_name,))
                    existing = cur.fetchone()
                    
                    if existing:
                        asset_id = existing[0]
                        # Change Detection
                        cur.execute("SELECT ip_address, mac_address, os_version, agent_version, status, site_id FROM assets WHERE asset_id = %s", (asset_id,))
                        old_data = cur.fetchone()
                        
                        updates = []
                        params = []
                        if ip and ip != old_data[0]:
                            self._log_change(cur, asset_id, "UPDATED", "ip_address", old_data[0], ip)
                            updates.append("ip_address = %s")
                            params.append(ip)
                        if mac and mac != old_data[1]:
                            self._log_change(cur, asset_id, "UPDATED", "mac_address", old_data[1], mac)
                            updates.append("mac_address = %s")
                            params.append(mac)
                        if os_version and os_version != old_data[2]:
                            self._log_change(cur, asset_id, "UPDATED", "os_version", old_data[2], os_version)
                            updates.append("os_version = %s")
                            params.append(os_version)
                        if agent_version and agent_version != old_data[3]:
                            self._log_change(cur, asset_id, "UPDATED", "agent_version", old_data[3], agent_version)
                            updates.append("agent_version = %s")
                            params.append(agent_version)
                        if status and status != old_data[4]:
                            self._log_change(cur, asset_id, "STATUS_CHANGE", "status", old_data[4], status)
                            updates.append("status = %s")
                            params.append(status)
                        
                        if updates:
                            updates.append("updated_at = NOW()")
                            updates.append("last_seen = %s")
                            params.append(last_seen)
                            params.extend([asset_id])
                            query = f"UPDATE assets SET {', '.join(updates)} WHERE asset_id = %s"
                            cur.execute(query, params)
                    else:
                        # Create new
                        asset_id = "AST-" + str(uuid.uuid4())[:8].upper()
                        cur.execute("""
                            INSERT INTO assets (
                                asset_id, hostname, ip_address, mac_address, os_version, 
                                agent_version, device_type, site_id, status, last_seen,
                                created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                        """, (
                            asset_id, pc_name, ip, mac, os_version, agent_version, device_type, site_id_val, status, last_seen
                        ))
                        self._log_change(cur, asset_id, "CREATED", "asset", None, pc_name)

            self.db.commit()
            logger.info("[DISCOVERY] Discovery completed successfully.")
        except Exception as e:
            logger.error(f"[DISCOVERY] Discovery failed: {e}")
            self.db.rollback()

    def _log_change(self, cur, asset_id, change_type, field, old_val, new_val):
        cur.execute("""
            INSERT INTO asset_audit_trail (asset_id, change_type, field_changed, old_value, new_value)
            VALUES (%s, %s, %s, %s, %s)
        """, (asset_id, change_type, field, str(old_val), str(new_val)))
