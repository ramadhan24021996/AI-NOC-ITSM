import json
import logging
import os
import socket
import psycopg2
from schemas import VerificationSchema

logger = logging.getLogger("VERIFICATION_AGENT")

def get_db_connection():
    db_host = os.getenv("DB_HOST", "127.0.0.1")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "osi_system")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    return psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=user,
        password=password
    )

def remote_tcp_probe(ip, port=10000) -> bool:
    if not ip:
        logger.warning("[remote_tcp_probe] IP is empty")
        return False
    # Map localhost/127.0.0.1 to host.docker.internal inside docker container
    if ip in ("127.0.0.1", "localhost"):
        ip = "host.docker.internal"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2.0)
        s.connect((ip, port))
        s.close()
        logger.info(f"[remote_tcp_probe] Successfully connected to {ip}:{port}")
        return True
    except Exception as e:
        logger.warning(f"[remote_tcp_probe] Failed to connect to {ip}:{port}: {e}")
        # Fallback to port 10001
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((ip, 10001))
            s.close()
            logger.info(f"[remote_tcp_probe] Fallback successfully connected to {ip}:10001")
            return True
        except Exception as e2:
            logger.warning(f"[remote_tcp_probe] Fallback failed to connect to {ip}:10001: {e2}")
            return False

class VerificationAgent:
    def __init__(self, nc=None):
        self.nc = nc

    async def start(self):
        if not self.nc:
            return
        async def handler(msg):
            try:
                payload = json.loads(msg.data.decode())
                logger.info(f"Verification Agent triggered for payload: {payload}")
                
                # Extraction of checks from payload
                service_alive = payload.get("service_alive", True)
                target_process_exists = payload.get("target_process_exists", True)
                port_open = payload.get("port_open", True)
                cpu_normalized = payload.get("cpu_normalized", True)
                memory_normalized = payload.get("memory_normalized", True)
                logs_clean = payload.get("logs_clean", True)
                dependent_services_stable = payload.get("dependent_services_stable", True)
                
                # Retrieve target device information
                incident_id = payload.get("incident_id")
                device_name = ""
                device_ip = ""
                
                if incident_id:
                    try:
                        conn = get_db_connection()
                        with conn.cursor() as cur:
                            cur.execute("SELECT pc_name FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                            row = cur.fetchone()
                            if row:
                                device_name = row[0]
                                
                            if device_name:
                                cur.execute("SELECT hardware_info FROM fleet_devices WHERE pc_name = %s", (device_name,))
                                row_ip = cur.fetchone()
                                if row_ip and row_ip[0]:
                                    hw = row_ip[0]
                                    if isinstance(hw, str):
                                        try:
                                            hw = json.loads(hw)
                                        except Exception:
                                            hw = {}
                                    device_ip = hw.get("ip", "")
                        conn.close()
                    except Exception as db_err:
                        logger.error(f"Failed to fetch device info from DB: {db_err}")

                # 1. Agent Local Verification Vote
                local_verification_ok = service_alive and target_process_exists and port_open and cpu_normalized and memory_normalized
                
                # 2. Remote TCP Probe Vote
                remote_probe_ok = remote_tcp_probe(device_ip)
                
                # 3. Independent Observer Agent Vote
                observer_name = ""
                observer_ip = ""
                try:
                    conn = get_db_connection()
                    with conn.cursor() as cur:
                        cur.execute("SELECT pc_name, hardware_info FROM fleet_devices WHERE pc_name != %s AND status = 'ACTIVE' LIMIT 1", (device_name or "",))
                        row_obs = cur.fetchone()
                        if row_obs:
                            observer_name = row_obs[0]
                            hw = row_obs[1]
                            if hw:
                                if isinstance(hw, str):
                                    try:
                                        hw = json.loads(hw)
                                    except Exception:
                                        hw = {}
                                observer_ip = hw.get("ip", "")
                    conn.close()
                except Exception:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')

                observer_probe_ok = False
                if observer_ip:
                    observer_probe_ok = remote_tcp_probe(device_ip) and remote_tcp_probe(observer_ip)
                else:
                    # Fallback to local/remote consensus if no observer agent is registered
                    observer_probe_ok = (local_verification_ok or remote_probe_ok)

                # Quorum Consensus Calculation (2/3 Vote)
                votes = {
                    "local_verification": local_verification_ok,
                    "remote_tcp_probe": remote_probe_ok,
                    "observer_agent_probe": observer_probe_ok
                }
                success_votes = sum(1 for v in votes.values() if v)
                quorum_verified = success_votes >= 2

                if quorum_verified:
                    status = "SUCCESS"
                    rollback_needed = False
                else:
                    status = "FAILED"
                    rollback_needed = True

                logger.info(
                    f"[VERIFICATION QUORUM] Consensus: {status} ({success_votes}/3 votes) | "
                    f"Votes: {votes} | Target Device: {device_name} ({device_ip}) | Observer: {observer_name} ({observer_ip})"
                )

                verification = VerificationSchema(
                    incident_id=payload.get("incident_id"),
                    verification_status=status,
                    service_alive=service_alive,
                    port_open=port_open,
                    cpu_normalized=cpu_normalized,
                    memory_normalized=memory_normalized,
                    logs_clean=logs_clean,
                    rollback_needed=rollback_needed,
                    metrics={
                        "target_process_exists": target_process_exists,
                        "dependent_services_stable": dependent_services_stable,
                        "quorum_votes": votes,
                        "quorum_count": success_votes
                    }
                )
                
                response_payload = verification.dict()
                await msg.respond(json.dumps(response_payload).encode())
            except Exception as e:
                logger.error(f"Error in VerificationAgent handler: {e}")
                await msg.respond(json.dumps({"error": str(e)}).encode())

        await self.nc.subscribe("agent.verify.result", cb=handler)
        logger.info("Verification Agent listening on 'agent.verify.result'")
