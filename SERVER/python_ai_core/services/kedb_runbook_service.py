"""
Enterprise KEDB & Runbook Management Service
Manages Known Error Database (KEDB), SOP Repository, Troubleshooting Runbooks, and Executable Script Store.
"""

import logging
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger("KEDB_RUNBOOK_SERVICE")

class KEDBRunbookService:
    """
    Enterprise KEDB & Runbook Service
    Indexes known error resolutions, SOP playbooks, and executable remediation scripts.
    """

    def __init__(self):
        self.kedb_records: Dict[str, Dict[str, Any]] = {
            "ERR-504": {
                "error_code": "ERR-504",
                "title": "Gateway Timeout on Client Access Switch",
                "symptoms": ["HTTP 504", "Ping Latency > 500ms", "VLAN Tagging Error", "Gateway Timeout"],
                "root_cause": "Duplex mismatch or port saturation on Switch_Access_01",
                "resolution": "Reset switch port duplex to Auto-Negotiate and clear ARP table",
                "script_ref": "reset_switch_port.sh",
                "success_rate": 0.98
            },

            "ERR-DNS-01": {
                "error_code": "ERR-DNS-01",
                "title": "DNS Resolution Timeout for Internal Portal",
                "symptoms": ["nslookup failure", "Name not resolved", "DNS port 53 timeout"],
                "root_cause": "Stale DNS cache or Primary DNS service restart needed",
                "resolution": "Flush client DNS cache via ipconfig /flushdns and verify DNS service",
                "script_ref": "flush_dns.ps1",
                "success_rate": 0.95
            }
        }

        self.sop_repository: Dict[str, Dict[str, Any]] = {
            "SOP-NET-01": {
                "sop_id": "SOP-NET-01",
                "title": "Standard Operating Procedure: Client Network Interface Troubleshooting",
                "category": "NETWORK_L1_L4",
                "steps": [
                    "1. Check physical link & Wi-Fi RSSI signal",
                    "2. Verify DHCP IP lease and subnet mask",
                    "3. Ping Default Gateway and evaluate packet loss",
                    "4. Validate DNS resolution for internal and external FQDNs"
                ]
            }
        }

    def search_kedb(self, symptom_text: str) -> List[Dict[str, Any]]:
        """Searches KEDB for matching error codes or symptoms."""
        results = []
        text_lower = symptom_text.lower()
        for err_code, data in self.kedb_records.items():
            if err_code.lower() in text_lower or any(s.lower() in text_lower for s in data["symptoms"]):
                results.append(data)
        return results

    def get_sop(self, sop_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves SOP playbook by ID."""
        return self.sop_repository.get(sop_id)
