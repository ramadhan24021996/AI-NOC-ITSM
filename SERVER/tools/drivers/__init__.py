"""SERVER.tools.drivers — Package Init"""
from SERVER.tools.drivers.ssh_driver import SSHDriver
from SERVER.tools.drivers.docker_driver import DockerDriver
from SERVER.tools.drivers.mikrotik_driver import MikrotikDriver
from SERVER.tools.drivers.rest_driver import RESTDriver

DRIVER_REGISTRY = {
    "ssh":      SSHDriver,
    "docker":   DockerDriver,
    "mikrotik": MikrotikDriver,
    "rest":     RESTDriver,
}

__all__ = ["SSHDriver", "DockerDriver", "MikrotikDriver", "RESTDriver", "DRIVER_REGISTRY"]
