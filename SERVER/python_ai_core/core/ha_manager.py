import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("HA_MANAGER")

def get_nats_ha_servers(default_url: str) -> List[str]:
    """
    Tahap 7: NATS Cluster HA Support.
    Returns a list of NATS server URLs for clustering and failover.
    """
    cluster_urls = os.environ.get("NATS_CLUSTER_URLS")
    if cluster_urls:
        servers = [s.strip() for s in cluster_urls.split(",") if s.strip()]
        logger.info(f"[HA_MANAGER] Using NATS Cluster: {servers}")
        return servers
    
    # Fallback to default or comma separated default
    return [s.strip() for s in default_url.split(",") if s.strip()]

def get_postgres_ha_params(db_name: str, db_user: str, db_pass: str, db_host: str, db_port: str) -> Dict[str, Any]:
    """
    Tahap 7: PostgreSQL Patroni HA Support.
    Parses comma-separated hosts for Patroni cluster failover.
    Returns a kwargs dictionary safe to unpack into psycopg2.connect()
    """
    patroni_hosts = os.environ.get("PATRONI_HOSTS", db_host)
    
    # If there are multiple hosts, it's an HA cluster setup
    is_ha = "," in patroni_hosts
    
    params = {
        "dbname": db_name,
        "user": db_user,
        "password": db_pass,
        "host": patroni_hosts,
        "port": db_port
    }
    
    if is_ha:
        logger.info(f"[HA_MANAGER] Using PostgreSQL Patroni HA cluster: {patroni_hosts}")
        # Requires psycopg2 to route write queries to the Primary Patroni node
        params["target_session_attrs"] = "read-write"
    
    return params
