import json
import os
import tempfile

STATUS_FILE = "Data/stt_status.json"

def update_stt_status(status: str, text: str = ""):
    """
    Valid statuses: 'idle', 'listening', 'understanding', 'transcribed', 'exit'
    """
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    
    data = {
        "status": status,
        "text": text
    }
    
    try:
        # ATOMIC WRITE: Pehle temp file me likho, fir fast rename karo. 
        # Isse PyQt kabhi bhi aadhi-adhuri file read nahi karega (Race Condition Fixed).
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(STATUS_FILE), text=True)
        with os.fdopen(fd, 'w', encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(temp_path, STATUS_FILE)
    except Exception as e:
        pass

def hide_stt_popup():
    """Call this when AI starts responding to hide the popup"""
    update_stt_status("idle", "")

def exit_stt_popup():
    """Call this to gracefully close the zombie background process"""
    update_stt_status("exit", "")