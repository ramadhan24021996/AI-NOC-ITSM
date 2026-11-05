import sys
import json
import os

# Add the python_ai_core to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.workflow_orchestrator import WorkflowOrchestrator

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(json.dumps({"answer": "Error: Missing arguments (session_id, query)"}))
        sys.exit(1)
        
    session_id = sys.argv[1]
    query = sys.argv[2]
    
    try:
        orchestrator = WorkflowOrchestrator()
        result = orchestrator.process_query(session_id, query)
        print(json.dumps({
            "answer": result,
            "confidence": 0.95,
            "source": "Cognitive Workflow Orchestrator"
        }))
    except Exception as e:
        print(json.dumps({"answer": f"Error Orchestrator: {str(e)}"}))
