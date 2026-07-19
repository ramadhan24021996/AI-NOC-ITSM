import re
import networkx as nx

class APMKnowledgeGraph:
    """
    P3 - DEEP COGNITION FOR APM (Application Knowledge Graph)
    Menyandikan pemahaman AI terhadap pola log aplikasi (Thread Starvation, Memory Leaks, Cascading HTTP Errors).
    """
    def __init__(self):
        self.graph = nx.DiGraph()
        self._initialize_apm_syndromes()

    def _initialize_apm_syndromes(self):
        # Memory Leak Pattern
        self.graph.add_node("MEMORY_LEAK", type="syndrome", severity="CRITICAL")
        self.graph.add_edge("High RAM Usage", "MEMORY_LEAK", weight=0.8)
        self.graph.add_edge("OOM Killer", "MEMORY_LEAK", weight=1.0)
        self.graph.add_edge("Garbage Collection Pause", "MEMORY_LEAK", weight=0.7)

        # Thread Starvation Pattern
        self.graph.add_node("THREAD_STARVATION", type="syndrome", severity="CRITICAL")
        self.graph.add_edge("CPU 100%", "THREAD_STARVATION", weight=0.6)
        self.graph.add_edge("Deadlock Exception", "THREAD_STARVATION", weight=0.9)
        self.graph.add_edge("Connection Pool Exhausted", "THREAD_STARVATION", weight=0.85)
        self.graph.add_edge("Blocked Threads", "THREAD_STARVATION", weight=0.95)

        # Cascading HTTP Errors
        self.graph.add_node("CASCADING_HTTP_ERRORS", type="syndrome", severity="HIGH")
        self.graph.add_edge("HTTP 502 Bad Gateway", "CASCADING_HTTP_ERRORS", weight=0.7)
        self.graph.add_edge("HTTP 503 Service Unavailable", "CASCADING_HTTP_ERRORS", weight=0.8)
        self.graph.add_edge("HTTP 504 Gateway Timeout", "CASCADING_HTTP_ERRORS", weight=0.8)
        self.graph.add_edge("Upstream Connection Refused", "CASCADING_HTTP_ERRORS", weight=0.9)

    def analyze_telemetry(self, log_text: str, metadata: dict) -> list:
        """
        Analyze raw logs and metadata to detect APM syndromes based on the Application Knowledge Graph.
        """
        detected_syndromes = set()
        text_lower = log_text.lower()
        
        # Heuristics mapping to graph edges
        symptoms = []
        if metadata.get("ram_usage", 0) > 90 or "oom" in text_lower or "out of memory" in text_lower:
            symptoms.append("OOM Killer")
        if "gc overhead" in text_lower or "garbage collection" in text_lower:
            symptoms.append("Garbage Collection Pause")
            
        if metadata.get("cpu_usage", 0) > 95:
            symptoms.append("CPU 100%")
        if "deadlock" in text_lower:
            symptoms.append("Deadlock Exception")
        if "pool exhausted" in text_lower or "timeout waiting for connection" in text_lower:
            symptoms.append("Connection Pool Exhausted")
        if "blocked" in text_lower and "thread" in text_lower:
            symptoms.append("Blocked Threads")
            
        if "502" in text_lower or "bad gateway" in text_lower:
            symptoms.append("HTTP 502 Bad Gateway")
        if "503" in text_lower or "service unavailable" in text_lower:
            symptoms.append("HTTP 503 Service Unavailable")
        if "504" in text_lower or "gateway timeout" in text_lower:
            symptoms.append("HTTP 504 Gateway Timeout")
        if "connection refused" in text_lower and "upstream" in text_lower:
            symptoms.append("Upstream Connection Refused")

        # Traverse Graph to find active syndromes
        for symptom in symptoms:
            if self.graph.has_node(symptom):
                for successor in self.graph.successors(symptom):
                    node_data = self.graph.nodes[successor]
                    if node_data.get("type") == "syndrome":
                        detected_syndromes.add(successor)
                        
        return list(detected_syndromes)

_engine = APMKnowledgeGraph()

def extract_apm_syndromes(log_text: str, metadata: dict) -> list:
    return _engine.analyze_telemetry(log_text, metadata)
