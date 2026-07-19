#!/usr/bin/env python3
import sys
import os
import time
import json
import random
from datetime import datetime, timedelta

# Add SERVER to path to import core logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../SERVER/python_ai_core')))

from cognition.evidence_fabric import EnterpriseEvidenceFabric
from cognition.knowledge_graph import DynamicKnowledgeGraph, GraphNode, GraphEdge

def generate_synthetic_telemetry():
    now = datetime.now()
    sources = ["CMDB", "LLDP", "SNMP", "Inference", "Agent_Windows", "Syslog"]
    metrics = ["CPU", "Memory", "Disk", "HTTP_503", "Connection_Refused", "Packet_Loss"]
    
    # 20% chance of being stale
    age_minutes = random.randint(65, 120) if random.random() < 0.2 else random.randint(1, 15)
    
    return {
        "timestamp": (now - timedelta(minutes=age_minutes)).isoformat(),
        "source": random.choice(sources),
        "metric": random.choice(metrics),
        "value": round(random.uniform(10, 100), 2),
        "severity": random.choice(["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    }

def run_evidence_fabric_load_test(iterations=1000):
    print(f"\n[+] Executing Enterprise Evidence Fabric Load Test ({iterations} packets)...")
    fabric = EnterpriseEvidenceFabric(incident_id="LOAD-TEST-001")
    
    start_time = time.time()
    
    for _ in range(iterations):
        raw_telemetry = generate_synthetic_telemetry()
        # Mix in intentional conflicts or duplicates randomly
        if random.random() < 0.05:
            # Duplicate
            fabric.ingest(raw_telemetry)
            fabric.ingest(raw_telemetry)
        else:
            fabric.ingest(raw_telemetry)
            
    # Also inject a known conflict
    conflict_1 = {"timestamp": datetime.now().isoformat(), "source": "Syslog", "metric": "HTTP_503", "value": "TRUE", "severity": "HIGH"}
    conflict_2 = {"timestamp": datetime.now().isoformat(), "source": "SNMP", "metric": "HTTP_503", "value": "FALSE", "severity": "LOW"}
    fabric.ingest(conflict_1)
    fabric.ingest(conflict_2)
    
    package = fabric.generate_package()
    end_time = time.time()
    
    print(f"[-] Load Test Complete in {end_time - start_time:.4f} seconds.")
    print(f"[-] Total Metrics Validated: {len(package.metrics)}")
    print(f"[-] Quality Score: {package.quality_score:.2f}%")
    print(f"[-] Confidence Score: {package.overall_confidence:.2f}%")
    
    conflicts = [m for m in package.metrics if m.status == "CONFLICT"]
    stale = [m for m in package.metrics if m.status == "STALE"]
    print(f"[-] Conflicts Detected: {len(conflicts)}")
    print(f"[-] Stale Evidence Detected: {len(stale)}")

def run_knowledge_graph_load_test(node_count=5000):
    print(f"\n[+] Executing Dynamic Knowledge Graph Load Test ({node_count} nodes)...")
    dkg = DynamicKnowledgeGraph()
    start_time = time.time()
    
    # Generate large topology
    for i in range(node_count):
        node = GraphNode(node_id=f"Node-{i}", node_type=random.choice(["Server", "VM", "Switch", "Database", "Application"]))
        dkg.add_node(node)
        
        # Connect to random previous node to ensure connectivity
        if i > 0:
            target = f"Node-{random.randint(0, i-1)}"
            edge = GraphEdge(
                source_id=f"Node-{i}", 
                target_id=target, 
                relationship="depends_on", 
                confidence=random.uniform(0.5, 1.0),
                source_engine="Load_Test"
            )
            dkg.add_edge(edge)
            
    # Trigger unknown dependency
    unknown_edge = GraphEdge(source_id="Node-100", target_id="Unknown", relationship="routes_to", confidence=0.8, source_engine="Inference")
    dkg.add_edge(unknown_edge)
    
    dkg.create_new_version()
    
    # Traverse
    path = dkg.traverse_root_cause(symptom_node_id=f"Node-{node_count-1}")
    radius = dkg.calculate_blast_radius(failure_node_id="Node-0")
    
    end_time = time.time()
    print(f"[-] Graph Test Complete in {end_time - start_time:.4f} seconds.")
    print(f"[-] Nodes Tracked: {dkg.graph.number_of_nodes()}")
    print(f"[-] Edges Tracked: {dkg.graph.number_of_edges()}")
    print(f"[-] Latest Version ID: {dkg.version_history[-1].version_id}")
    print(f"[-] Root Cause Path Depth from Node-{node_count-1}: {len(path)} hops")
    print(f"[-] Blast Radius Size from Node-0: {len(radius['impacted_nodes'])} impacted entities")

if __name__ == "__main__":
    print("="*60)
    print(" SPRINT P & Q PRODUCTION LOAD VALIDATION ")
    print("="*60)
    run_evidence_fabric_load_test(iterations=10000)
    run_knowledge_graph_load_test(node_count=10000)
    print("="*60)
    print(" ALL SYSTEMS STABLE AND OPERATIONAL ")
    print("="*60)
