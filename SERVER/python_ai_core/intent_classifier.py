import logging
import math
from typing import Dict, List, Tuple, Any

logger = logging.getLogger("INTENT_CLASSIFIER")

# ── 1. ENTERPRISE TRAINING DATA (COVERAGE INTENT) ─────────────────────────
TRAINING_DATA = {
    # Infrastructure & Compute
    "CPU_EXHAUSTION": "cpu high 95% utilization processor wmiprvse msmpeng task manager slow lag spike thread pool",
    "MEMORY_LEAK": "ram memory leak swap 95% usage out of memory oom kill exhausted consumption",
    "DISK_FULL": "disk full space 500mb storage c: cleanup temp block io bottleneck",
    "GPU_OVERHEAT": "gpu utilization nvidia amd overheat 90% cuda graphics thermal throttling",
    "LINUX_KERNEL_PANIC": "linux kernel panic oops crash segmentation fault dmesg trace",
    
    # Network & Connectivity
    "NETWORK_OFFLINE": "network offline ping failed connection dropped tracert timeout unreachable router switch",
    "DNS_RESOLUTION_FAILURE": "dns resolution failed name server timeout unresolvable cache expired 53",
    "DHCP_EXHAUSTION": "dhcp pool exhausted no ip address lease failed apipa 169.254",
    "VPN_DISCONNECT": "vpn disconnect forticlient cisco anyconnect rasdial tunnel dropped ipsec",
    "WIFI_DEGRADATION": "wifi signal weak dropped access point interference packet loss wlan",
    "FIREWALL_BLOCK": "firewall blocked drop deny port closed policy security group iptables ufw",
    
    # Web & Application Servers
    "IIS_CRASH": "iis application pool crash w3wp stopped worker process 503 unavailable web",
    "APACHE_TIMEOUT": "apache httpd worker timeout connection reset maxclients queued web",
    "NGINX_GATEWAY_ERROR": "nginx 502 bad gateway 504 timeout upstream failed web proxy",
    
    # Databases & Queues
    "POSTGRESQL_LOCK": "postgresql pgsql lock deadlock connection pool max_connections slow query",
    "MYSQL_CRASH": "mysql mariadb innodb crash out of memory max_allowed_packet db error",
    "SQL_SERVER_TIMEOUT": "sql server mssql deadlocked timeout query execution tempdb full",
    "ORACLE_TABLESPACE_FULL": "oracle ora- tablespace full temp extent maximum database",
    "REDIS_OOM": "redis oom command not allowed memory maxmemory eviction",
    "KAFKA_LAG": "kafka consumer lag broker offline partition rebalance zookeeper timeout",
    "RABBITMQ_QUEUE_FULL": "rabbitmq queue full unacked messages connection blocked memory alarm",
    
    # Virtualization & Containers
    "DOCKER_CONTAINER_EXIT": "docker container exit crashed restart loop oomkilled dockerd",
    "KUBERNETES_POD_CRASH": "kubernetes k8s pod crashloopbackoff evict pending node offline kubelet",
    "VMWARE_DATASTORE_LATENCY": "vmware esxi vsphere datastore latency snapshot consolidate vcenter",
    "HYPERV_VM_STUCK": "hyper-v vm stuck saved state stopping checkpoint virtual machine",
    
    # Storage & Backup
    "SAN_PATH_DOWN": "san storage area network multipath dead fiber channel iscsi lun dropped",
    "NAS_UNREACHABLE": "nas nfs smb cifs mount failed stale file handle unreachable",
    "BACKUP_FAILED": "backup failed snapshot vss writer error veeam shadow copy timeout",
    
    # Security & Identity
    "SECURITY_THREAT_LOGIN": "failed login event 4625 ssh failed password brute force security auth",
    "ACTIVE_DIRECTORY_REPLICATION": "active directory ad replication failed tombstone dcdiag domain controller",
    "CERTIFICATE_EXPIRED": "certificate expired ssl tls cert invalid sslv3 handshake failed x509",
    "WINDOWS_UPDATE_FAILED": "windows update failed wsus patch error rollback pending reboot",
    
    # Peripherals
    "PRINTER_STALLED": "printer spooler offline stalled queue printjob print spooling jam"
}

# ── 2. INTENT -> OSI LAYER MAPPING (KANDIDAT DOMAIN) ─────────────────────
OSI_MAPPING = {
    "CPU_EXHAUSTION": {"osi_layer": 7, "domain": "Compute/Application", "evidence_required": ["Process List", "CPU Metrics", "Service States"]},
    "MEMORY_LEAK": {"osi_layer": 7, "domain": "Compute/Application", "evidence_required": ["RAM Metrics", "OOM Logs", "Process Heap"]},
    "DISK_FULL": {"osi_layer": 1, "domain": "Storage", "evidence_required": ["Disk Usage", "Temp Files", "IOPS"]},
    "GPU_OVERHEAT": {"osi_layer": 1, "domain": "Compute", "evidence_required": ["Thermal Sensors", "GPU Load"]},
    "LINUX_KERNEL_PANIC": {"osi_layer": 1, "domain": "OS/Kernel", "evidence_required": ["dmesg", "syslog", "Kernel Trace"]},
    
    "NETWORK_OFFLINE": {"osi_layer": 3, "domain": "Network", "evidence_required": ["ICMP Ping", "Gateway ARP", "Routing Table"]},
    "DNS_RESOLUTION_FAILURE": {"osi_layer": 7, "domain": "Network Services", "evidence_required": ["nslookup", "resolv.conf", "DNS Cache"]},
    "DHCP_EXHAUSTION": {"osi_layer": 3, "domain": "Network Services", "evidence_required": ["DHCP Leases", "IPConfig", "Scope Stats"]},
    "VPN_DISCONNECT": {"osi_layer": 4, "domain": "Network Security", "evidence_required": ["VPN Logs", "Tunnel Status", "Routing"]},
    "WIFI_DEGRADATION": {"osi_layer": 1, "domain": "Wireless", "evidence_required": ["Signal Strength", "WLAN AutoConfig", "BSSID"]},
    "FIREWALL_BLOCK": {"osi_layer": 4, "domain": "Security", "evidence_required": ["Firewall Rules", "Dropped Packets", "Port Scan"]},
    
    "IIS_CRASH": {"osi_layer": 7, "domain": "Web Server", "evidence_required": ["IIS Logs", "Event Viewer", "AppPool Status"]},
    "APACHE_TIMEOUT": {"osi_layer": 7, "domain": "Web Server", "evidence_required": ["Apache Error Log", "Connection Count", "Resource Limits"]},
    "NGINX_GATEWAY_ERROR": {"osi_layer": 7, "domain": "Web Server", "evidence_required": ["Nginx Access Log", "Upstream Status", "TCP Sockets"]},
    
    "POSTGRESQL_LOCK": {"osi_layer": 7, "domain": "Database", "evidence_required": ["pg_stat_activity", "Lock Wait Info", "Slow Queries"]},
    "MYSQL_CRASH": {"osi_layer": 7, "domain": "Database", "evidence_required": ["MySQL Error Log", "InnoDB Status", "System RAM"]},
    "SQL_SERVER_TIMEOUT": {"osi_layer": 7, "domain": "Database", "evidence_required": ["SQL Error Log", "Active Sessions", "Blocking Locks"]},
    "ORACLE_TABLESPACE_FULL": {"osi_layer": 7, "domain": "Database", "evidence_required": ["DBA_TABLESPACES", "Alert Log", "Datafile Sizes"]},
    "REDIS_OOM": {"osi_layer": 7, "domain": "In-Memory DB", "evidence_required": ["INFO memory", "Eviction Stats", "Keyspace"]},
    "KAFKA_LAG": {"osi_layer": 7, "domain": "Message Queue", "evidence_required": ["Consumer Group Lag", "Broker Logs", "Partition State"]},
    "RABBITMQ_QUEUE_FULL": {"osi_layer": 7, "domain": "Message Queue", "evidence_required": ["Queue Depth", "Unacked Msgs", "Memory Alarms"]},
    
    "DOCKER_CONTAINER_EXIT": {"osi_layer": 7, "domain": "Container", "evidence_required": ["Docker Inspect", "Container Logs", "OOM Stats"]},
    "KUBERNETES_POD_CRASH": {"osi_layer": 7, "domain": "Orchestration", "evidence_required": ["kubectl describe", "Pod Logs", "Node Events"]},
    "VMWARE_DATASTORE_LATENCY": {"osi_layer": 2, "domain": "Virtualization", "evidence_required": ["esxtop", "Datastore IOPS", "VMware Events"]},
    "HYPERV_VM_STUCK": {"osi_layer": 2, "domain": "Virtualization", "evidence_required": ["Hyper-V Logs", "VM State", "Host Resources"]},
    
    "SAN_PATH_DOWN": {"osi_layer": 2, "domain": "Storage Network", "evidence_required": ["Multipath status", "iSCSI sessions", "FC Zoning"]},
    "NAS_UNREACHABLE": {"osi_layer": 3, "domain": "Storage Network", "evidence_required": ["NFS/SMB Mounts", "Network Ping", "NAS Uptime"]},
    "BACKUP_FAILED": {"osi_layer": 7, "domain": "Data Protection", "evidence_required": ["Backup Logs", "VSS Writers", "Snapshot Storage"]},
    
    "SECURITY_THREAT_LOGIN": {"osi_layer": 7, "domain": "Security", "evidence_required": ["Event ID 4625", "auth.log", "Source IP"]},
    "ACTIVE_DIRECTORY_REPLICATION": {"osi_layer": 7, "domain": "Identity", "evidence_required": ["repadmin", "dcdiag", "Event Viewer Directory"]},
    "CERTIFICATE_EXPIRED": {"osi_layer": 6, "domain": "Security", "evidence_required": ["Cert Expiry Date", "Keystore", "SSL Labs"]},
    "WINDOWS_UPDATE_FAILED": {"osi_layer": 7, "domain": "OS", "evidence_required": ["WindowsUpdate.log", "CBS.log", "Pending Reboots"]},
    
    "PRINTER_STALLED": {"osi_layer": 7, "domain": "Peripheral", "evidence_required": ["Spooler State", "Printer Queue", "Device Ping"]}
}

class FastIntentClassifier:
    def __init__(self):
        self.documents = []
        self.classes = []
        self.vocab = set()
        self.idf = {}
        self.tf_idf_matrix = []
        
        self._train()

    def _tokenize(self, text: str):
        import re
        text = re.sub(r'[^a-zA-Z0-9\s]', ' ', text)
        return text.lower().split()

    def _train(self):
        doc_freq = {}
        for intent, text in TRAINING_DATA.items():
            self.classes.append(intent)
            tokens = self._tokenize(text)
            self.documents.append(tokens)
            
            unique_tokens = set(tokens)
            self.vocab.update(unique_tokens)
            for token in unique_tokens:
                doc_freq[token] = doc_freq.get(token, 0) + 1
                
        N = len(self.documents)
        for token, freq in doc_freq.items():
            self.idf[token] = math.log(N / (1 + freq)) + 1
            
        for tokens in self.documents:
            vec = self._vectorize(tokens)
            self.tf_idf_matrix.append(vec)

    def _vectorize(self, tokens: list) -> Dict[str, float]:
        tf = {}
        total_tokens = len(tokens)
        if total_tokens == 0: return dict()
        
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
            
        vec = {}
        norm = 0.0
        for token, count in tf.items():
            if token in self.vocab:
                val = (count / total_tokens) * self.idf[token]
                vec[token] = val
                norm += val * val
                
        norm = math.sqrt(norm)
        if norm > 0:
            for k in vec:
                vec[k] /= norm
                
        return vec

    def extract_symptoms(self, data: dict) -> str:
        """
        Extracts hardware symptoms from raw telemetry to avoid supervisor reasoning.
        """
        hw_info = data.get("data", {}).get("hardware_info", {})
        base_data = data.get("data", {})
        
        cpu_val = hw_info.get("cpu_percent", hw_info.get("cpu_usage", base_data.get("cpu_percent", 0)))
        ram_val = hw_info.get("mem_percent", hw_info.get("ram_usage", base_data.get("memory_percent", 0)))
        disk_val = hw_info.get("disk_percent", hw_info.get("disk_usage", base_data.get("disk_percent", 0)))
        
        net_adv = hw_info.get("network", base_data.get("network_advanced", {}))
        if isinstance(net_adv, str): net_adv = {}
        
        loss_val = net_adv.get("packet_loss_pct", 0)
        
        hw_symptoms = []
        if isinstance(cpu_val, (int, float)) and cpu_val >= 90: hw_symptoms.append(f"cpu high {cpu_val}% utilization processor")
        if isinstance(ram_val, (int, float)) and ram_val >= 90: hw_symptoms.append(f"ram memory leak {ram_val}% usage")
        if isinstance(disk_val, (int, float)) and disk_val >= 90: hw_symptoms.append(f"disk full {disk_val}% space")
        if isinstance(loss_val, (int, float)) and loss_val >= 50: hw_symptoms.append(f"network offline ping failed connection dropped {loss_val}% loss")
        
        return " ".join(hw_symptoms).strip()

    def _cosine_similarity(self, vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        intersection = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[token] * vec2[token] for token in intersection)
        return dot_product

    def predict_multi(self, text: str) -> List[Dict[str, Any]]:
        """
        Predicts multiple intents and returns them sorted by confidence.
        Includes OSI mapping data directly.
        """
        tokens = self._tokenize(text)
        vec = self._vectorize(tokens)
        
        results = []
        
        for idx, intent in enumerate(self.classes):
            train_vec = self.tf_idf_matrix[idx]
            score = self._cosine_similarity(vec, train_vec)
            conf_pct = round(score * 100, 2)
            
            if conf_pct > 0:
                mapping = OSI_MAPPING.get(intent, {})
                results.append({
                    "intent": intent,
                    "confidence": conf_pct,
                    "osi_layer": mapping.get("osi_layer", 0),
                    "domain": mapping.get("domain", "Unknown"),
                    "evidence_required": mapping.get("evidence_required", [])
                })
                
        results = sorted(results, key=lambda x: x["confidence"], reverse=True)
        
        # Determine routing strategy based on thresholds
        # Confidence >95% : Direct route
        # 80-95% : Evidence Validation
        # 60-80% : LLM + Consensus
        # <60% : UNKNOWN
        
        final_results = []
        for r in results:
            if r["confidence"] > 95:
                r["routing"] = "DIRECT_ROUTE"
                final_results.append(r)
            elif r["confidence"] >= 80:
                r["routing"] = "EVIDENCE_VALIDATION"
                final_results.append(r)
            elif r["confidence"] >= 60:
                r["routing"] = "LLM_CONSENSUS"
                final_results.append(r)
            else: _ = None # Ignore intents below 60%
                
        if not final_results:
            return [{
                "intent": "UNKNOWN",
                "confidence": 0.0,
                "routing": "LLM_CONSENSUS", # Fallback completely to LLM
                "osi_layer": 0,
                "domain": "Unknown",
                "evidence_required": ["Full System Diagnostics"]
            }]
            
        return final_results

    def predict(self, text: str) -> Tuple[str, float]:
        """Backward compatibility"""
        res = self.predict_multi(text)
        if res:
            return res[0]["intent"], res[0]["confidence"]
        return "UNKNOWN", 0.0

_classifier_instance = None

def get_intent_classifier():
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = FastIntentClassifier()
    return _classifier_instance
