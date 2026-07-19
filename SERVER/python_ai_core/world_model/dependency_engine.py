import psycopg2
import logging

logger = logging.getLogger("DEPENDENCY_ENGINE")

class DependencyEngine:
    def __init__(self, db_conn):
        self.db = db_conn

    def build_service_map(self):
        """Discovers and builds the dependency graph between assets based on traces and rules."""
        if not self.db:
            return
            
        try:
            with self.db.cursor() as cur:
                # 1. PC to Default Gateway (Router)
                # 2. Server to Database
                # For this sprint audit, we'll build basic dependencies if they don't exist
                
                cur.execute("SELECT asset_id, device_type, site_id FROM assets")
                assets = cur.fetchall()
                
                # Group by site
                sites = {}
                for a in assets:
                    asset_id, dtype, site_id = a
                    if site_id not in sites:
                        sites[site_id] = {'routers': [], 'switches': [], 'pcs': [], 'servers': [], 'printers': [], 'databases': []}
                    
                    if dtype == 'Router':
                        sites[site_id]['routers'].append(asset_id)
                    elif dtype == 'Switch':
                        sites[site_id]['switches'].append(asset_id)
                    elif dtype == 'Windows PC' or dtype == 'Linux':
                        sites[site_id]['pcs'].append(asset_id)
                    elif dtype == 'Server':
                        sites[site_id]['servers'].append(asset_id)
                    elif dtype == 'Printer':
                        sites[site_id]['printers'].append(asset_id)
                    elif dtype == 'Database':
                        sites[site_id]['databases'].append(asset_id)

                for site_id, grp in sites.items():
                    # Link Switch -> Router (UPSTREAM)
                    for sw in grp['switches']:
                        for rt in grp['routers']:
                            self._add_dep(cur, sw, rt, 'UPSTREAM', True)
                            self._add_dep(cur, rt, sw, 'DOWNSTREAM', False)
                            
                    # Link PC -> Switch
                    for pc in grp['pcs']:
                        # If no switch, link directly to router
                        targets = grp['switches'] if grp['switches'] else grp['routers']
                        if targets:
                            # Just link to the first one for the graph
                            self._add_dep(cur, pc, targets[0], 'UPSTREAM', False)
                            self._add_dep(cur, targets[0], pc, 'DOWNSTREAM', False)
                            
                    # Link Printer -> Switch
                    for prn in grp['printers']:
                        targets = grp['switches'] if grp['switches'] else grp['routers']
                        if targets:
                            self._add_dep(cur, prn, targets[0], 'UPSTREAM', False)
                            
                    # Link Server -> Switch
                    for srv in grp['servers']:
                        targets = grp['switches'] if grp['switches'] else grp['routers']
                        if targets:
                            self._add_dep(cur, srv, targets[0], 'UPSTREAM', True)
                            
                        # Link Server -> Database
                        if grp['databases']:
                            self._add_dep(cur, srv, grp['databases'][0], 'DATABASE', True)

            self.db.commit()
            logger.info("[DEPENDENCY] Topology & Service Map Engine built successfully.")
        except Exception as e:
            logger.error(f"[DEPENDENCY] Failed to build map: {e}")
            self.db.rollback()

    def _add_dep(self, cur, src, tgt, dep_type, critical):
        cur.execute("""
            INSERT INTO asset_dependencies (source_asset_id, target_asset_id, dependency_type, critical_path)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (src, tgt, dep_type, critical))
