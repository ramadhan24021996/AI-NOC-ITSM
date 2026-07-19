from typing import Dict, Any
from .agent_registry import AgentRegistry

class TaskRouter:
    def __init__(self):
        self.registry = AgentRegistry()

    def route_task(self, incident: Dict[str, Any]) -> str:
        # Determine the most competent agent based on incident
        layer = str(incident.get("osi_layer", "")).lower()
        title = str(incident.get("title", "")).lower()
        
        service_type = "general"
        if "printer" in title or "spooler" in title:
            service_type = "printer"
        elif "network" in title or "layer 3" in layer:
            service_type = "network"
        elif "database" in title or "sql" in title:
            service_type = "database"
            
        return self.registry.discover_service(service_type)
