"""
Enterprise AI OS — Log Stream Compactor & Pattern Aggregator Module
Compresses high-volume raw syslog/telemetry stream bursts into structured pattern summaries
(e.g., 10,000 repeated error logs -> 1 aggregated pattern template with occurrence counts).

Protects LLM Router and RCA Hypothesis Engine from Token Exhaustion during Major Outages.
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger("LOG_STREAM_COMPACTOR")


class LogStreamCompactor:
    """
    Sub-millisecond Log Pattern Extractor & Aggregator.
    Replaces dynamic tokens (IPs, PIDs, Timestamps, Hex addresses) with wildcards <*>.
    """

    @staticmethod
    def extract_pattern(log_line: str) -> str:
        """Masks dynamic variables (IPs, Timestamps, PIDs, Hex) to extract log template pattern."""
        if not log_line:
            return ""
        
        pattern = log_line.strip()
        
        # 1. Mask Timestamps (ISO8601, Syslog dates)
        pattern = re.sub(r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?\b", "<TIMESTAMP>", pattern)
        pattern = re.sub(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+\s+\d{2}:\d{2}:\d{2}\b", "<TIMESTAMP>", pattern)
        
        # 2. Mask IP Addresses
        pattern = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?\b", "<IP_ADDR>", pattern)
        
        # 3. Mask PIDs & Process IDs
        pattern = re.sub(r"\[pid:\s*\d+\]|\[\d+\]", "[PID]", pattern)
        
        # 4. Mask Hex Addresses & Hashes
        pattern = re.sub(r"\b0x[0-9a-fA-F]+\b", "<HEX>", pattern)
        pattern = re.sub(r"\b[0-9a-fA-F]{16,64}\b", "<HASH>", pattern)
        
        # 5. Mask Numbers/Counts
        pattern = re.sub(r"\b\d+\b", "<NUM>", pattern)
        
        return pattern

    def compact_stream(self, log_lines: List[str], max_patterns: int = 10) -> Dict[str, Any]:
        """
        Aggregates thousands of log lines into top N compact patterns with frequency stats.
        Returns compressed summary dictionary for LLM context window.
        """
        if not log_lines:
            return {"total_lines": 0, "compressed_patterns": [], "compression_ratio": 0.0}

        total_input_lines = len(log_lines)
        pattern_counts: Dict[str, int] = defaultdict(int)
        sample_raw: Dict[str, str] = {}

        for line in log_lines:
            pat = self.extract_pattern(line)
            pattern_counts[pat] += 1
            if pat not in sample_raw:
                sample_raw[pat] = line.strip()

        # Sort patterns by frequency descending
        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        top_patterns = sorted_patterns[:max_patterns]

        compressed = []
        for pat, count in top_patterns:
            pct = round((count / float(total_input_lines)) * 100.0, 2)
            compressed.append({
                "pattern": pat,
                "count": count,
                "percentage": pct,
                "sample_log": sample_raw.get(pat, "")
            })

        comp_ratio = round((1.0 - (len(compressed) / float(total_input_lines))) * 100.0, 2) if total_input_lines > 0 else 0.0

        logger.info(f"[LOG COMPACTOR] Compacted {total_input_lines} logs into {len(compressed)} patterns ({comp_ratio}% compression ratio)")

        return {
            "total_lines": total_input_lines,
            "unique_patterns": len(sorted_patterns),
            "compression_ratio_pct": comp_ratio,
            "top_patterns": compressed
        }
