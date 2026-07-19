import logging
import socket

logger = logging.getLogger("SERVICE_VALIDATOR")

class ServiceValidator:
    def __init__(self):
        import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def validate_service(self, service_name: str, active_processes: list, host: str = None, port: int = None) -> dict:
        service_lower = service_name.lower()
        is_running = False

        for proc in active_processes:
            proc_name = str(proc.get("name", "")).lower()
            if service_lower in proc_name:
                is_running = True
                break
                
        port_open = False
        if host and port:
            try:
                with socket.create_connection((host, port), timeout=2.0):
                    port_open = True
            except OSError:
                port_open = False
        else:
            # If no host/port provided, assume port check is not applicable
            port_open = True

        return {
            "service_alive": is_running,
            "port_open": port_open
        }
