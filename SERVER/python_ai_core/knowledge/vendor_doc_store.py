"""
Enterprise Vendor Documentation & Incident History Store
Indexes vendor KB documentation (Microsoft, Cisco, MikroTik, Linux) and past incident ticket resolutions.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("VENDOR_DOC_STORE")

class VendorDocStore:
    """
    Enterprise Vendor Documentation Repository
    Provides searchable vendor KB articles and historical ticket resolution summaries.
    """

    def __init__(self):
        self.vendor_kbs: List[Dict[str, Any]] = [
            {
                "vendor": "Cisco",
                "doc_id": "CISCO-KB-88210",
                "title": "Troubleshooting 802.1X Port Authentication Failures",
                "content": "Verify RADIUS server IP connectivity, shared secret key, and port VLAN assignments."
            },
            {
                "vendor": "Microsoft",
                "doc_id": "MS-KB-310400",
                "title": "Windows TCP/IP Stack Reset and Winsock Repair",
                "content": "Execute netsh int ip reset and netsh winsock reset to resolve corrupted TCP/IP stack."
            }
        ]

    def search_vendor_docs(self, query: str) -> List[Dict[str, Any]]:
        """Searches vendor documentation articles."""
        q = query.lower()
        return [doc for doc in self.vendor_kbs if q in doc["title"].lower() or q in doc["content"].lower()]
