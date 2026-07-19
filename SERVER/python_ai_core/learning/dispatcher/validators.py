from typing import Dict, Any

def validate_schema(payload: Dict[str, Any]) -> bool:
    if "header" not in payload or "payload" not in payload:
        return False
    return True\n