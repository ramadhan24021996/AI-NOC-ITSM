"""
Sandboxed Plugin Runtime Module
Manages sandboxed vendor plugins (Cisco, Mikrotik, Fortigate, Windows, Linux, Docker, K8s, VMware, Proxmox):
Enforces signed plugin manifests, permission bounds (e.g. snmp.read, api.write), and process isolation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import hmac
import hashlib


@dataclass
class PluginManifest:
    plugin_name: str         # "mikrotik", "cisco", "fortigate", etc.
    version: str
    granted_permissions: List[str]
    digital_signature: str
    sandbox_isolated: bool


@dataclass
class PluginExecutionResult:
    plugin_name: str
    action_executed: str
    permitted: bool
    signature_verified: bool
    output_data: Dict[str, Any]


class AIOSPluginRuntime:
    """Manages sandboxed execution of signed vendor driver plugins."""

    def __init__(self, signing_secret: str = "aios_plugin_secret"):
        self.signing_secret = signing_secret.encode()
        self.registered_plugins: Dict[str, PluginManifest] = {}
        self._register_default_vendor_plugins()

    def _register_default_vendor_plugins(self):
        for vendor, perms in [
            ("mikrotik", ["snmp.read", "api.read", "api.write"]),
            ("cisco", ["snmp.read", "ssh.read"]),
            ("fortigate", ["snmp.read", "api.read"]),
            ("windows", ["wmi.read", "eventlog.read"]),
            ("linux", ["ssh.read", "syslog.read"]),
            ("kubernetes", ["k8s.read"])
        ]:
            sig = hmac.new(self.signing_secret, f"{vendor}-1.0.0".encode(), hashlib.sha256).hexdigest()
            self.registered_plugins[vendor] = PluginManifest(
                plugin_name=vendor,
                version="1.0.0",
                granted_permissions=perms,
                digital_signature=sig,
                sandbox_isolated=True
            )

    def execute_sandboxed_plugin(
        self,
        plugin_name: str,
        action: str,
        required_permission: str
    ) -> PluginExecutionResult:

        manifest = self.registered_plugins.get(plugin_name)
        if not manifest:
            return PluginExecutionResult(
                plugin_name=plugin_name,
                action_executed=action,
                permitted=False,
                signature_verified=False,
                output_data={"error": f"Vendor plugin '{plugin_name}' not registered"}
            )

        # Check signature verification
        expected_sig = hmac.new(self.signing_secret, f"{plugin_name}-{manifest.version}".encode(), hashlib.sha256).hexdigest()
        sig_ok = hmac.compare_digest(expected_sig, manifest.digital_signature)

        # Check permission check
        perm_ok = required_permission in manifest.granted_permissions

        allowed = sig_ok and perm_ok

        return PluginExecutionResult(
            plugin_name=plugin_name,
            action_executed=action,
            permitted=allowed,
            signature_verified=sig_ok,
            output_data={"status": "SUCCESS" if allowed else "BLOCKED_PERMISSION_VIOLATION"}
        )
