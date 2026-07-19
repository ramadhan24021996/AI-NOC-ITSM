import re

with open("SERVER/python_ai_core/ai_supervisor.py", "r") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "# 4. Consensus Engine Layer with max 2 rounds debate limit" in line:
        start_idx = i
    if "# 5. Isolated Agent Calls & Schema Validation" in line and start_idx != -1:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    fast_track_code = """
                # System 1: Fast Track Bypass
                fast_track_bypassed = False
                fast_track_action = None
                fast_track_confidence = 0.0
                fast_track_reason = ""
                
                if severity_score < 70 and historical_context:
                    best_match = None
                    for h in historical_context:
                        try:
                            sim = float(h.get("similarity", 0.0))
                            if sim > 0.85 and h.get("remediation_effectiveness") == "SUCCESS":
                                best_match = h
                                break
                        except:
                            _ = None
                    
                    if best_match:
                        fast_track_bypassed = True
                        fast_track_action = best_match.get("recommended_action", "UNKNOWN")
                        fast_track_confidence = float(best_match.get("similarity", 0.9)) * 100
                        fast_track_reason = f"System 1 Fast Track: High similarity historical match ({fast_track_confidence:.1f}%)"
                        logger.info(f"[SYSTEM 1 FAST TRACK] Bypassing Consensus. Action: {fast_track_action}")

                if fast_track_bypassed:
                    consensus_verdict = {
                        "recommended_action": fast_track_action,
                        "confidence": fast_track_confidence / 100.0,
                        "risk_level": "LOW",
                        "reasoning": fast_track_reason
                    }
                    first_hypothesis = fast_track_action
                    final_decision = fast_track_action
                    confidence_score = min(99.0, max(10.0, fast_track_confidence))
                    risk_level_str = "LOW"
                    second_hypothesis = fast_track_reason
                    
                    _erg.set_hypothesis(first_hypothesis, confidence_score / 100.0)
                    _erg.set_knowledge(historical_context)
                    
                    llm_response = {
                        "status": "SUCCESS",
                        "model": "system-1-fast-track",
                        "response": json.dumps(consensus_verdict)
                    }
                    
                    log_event_sourced(rag.conn, "incident_events", incident_id or 0, "ANALYZED", {
                        "verdict": consensus_verdict,
                        "confidence": confidence_score,
                        "severity": severity_str,
                        "path": "FAST_TRACK_SYSTEM_1"
                    })
                else:
"""
    # Indent the original consensus block
    original_block = lines[start_idx:end_idx]
    indented_block = ["    " + line if line.strip() else line for line in original_block]
    
    new_lines = lines[:start_idx] + [fast_track_code] + indented_block + lines[end_idx:]
    
    with open("SERVER/python_ai_core/ai_supervisor.py", "w") as fw:
        fw.writelines(new_lines)
    print("REFACTOR SUCCESS")
else:
    print("FAILED TO FIND BLOCK")
