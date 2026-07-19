import logging
from world_model.discovery_engine import DiscoveryEngine
from world_model.business_impact_engine import BusinessImpactEngine
from world_model.fleet_health_engine import FleetHealthEngine
from world_model.dependency_engine import DependencyEngine

logger = logging.getLogger("WORLD_MODEL")

class WorldModelUpdater:
    def __init__(self, db_conn):
        self.db = db_conn

    def run_all_engines(self):
        """Runs the entire suite of Enterprise Asset Engines to update the World Model."""
        logger.info("[WORLD MODEL] Starting global World Model update cycle...")
        
        # 1. Discovery & Asset Change Detection
        discovery = DiscoveryEngine(self.db)
        discovery.run_discovery()
        
        # 2. Dependency Graph & Service Map
        dependency = DependencyEngine(self.db)
        dependency.build_service_map()
        
        # 3. Business Impact & Criticality
        impact = BusinessImpactEngine(self.db)
        impact.calculate_criticality()
        
        # 4. Fleet Health Engine
        health = FleetHealthEngine(self.db)
        health.update_health_scores()
        
        logger.info("[WORLD MODEL] Update cycle complete.")
