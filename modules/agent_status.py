import json
import os
from datetime import datetime

STATUS_FILE = "Data/agent_status.json"

def update_agent_status(step: int, total_steps: int, thought: str, action: str = "", observation: str = ""):
    """Call this inside agent loop to update UI"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "step": step,
        "total_steps": total_steps,
        "thought": thought,
        "action": action,
        "observation": observation[:200]  # truncate
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)