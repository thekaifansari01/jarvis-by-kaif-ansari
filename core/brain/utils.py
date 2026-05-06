import re
from typing import List, Optional
from core.brain.history import command_history

def clean_and_split_apps(raw: str) -> List[str]:
    """Clean and split raw command into app names."""
    raw = re.sub(r"\b(and|then|also|print|with|comma|aur|phir|aur bhi)\b", ",", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s+", " ", raw).strip()
    parts = re.split(r",|\s+", raw)
    return [p.strip().lower() for p in parts if p.strip()]

def resolve_pronouns(raw_command: str) -> str:
    """Resolve pronouns and 'last app' references in the command based on command history."""
    if not command_history:
        return raw_command
    last_entry = list(command_history)[-1]
    if not isinstance(last_entry, dict):
        return raw_command
    last_result = last_entry.get("result", {})
    last_apps_opened = last_result.get("apps_to_open", [])
    last_app = last_apps_opened[-1] if last_apps_opened else None
    if last_app:
        # Replace pronouns like 'it', 'that', 'usko', 'isse'
        raw_command = re.sub(r"\b(it|that|usko|isse)\b", last_app, raw_command, flags=re.IGNORECASE)
        # Replace 'last app' or similar phrases
        raw_command = re.sub(r"\b(last app|last application|last opened app|us app ko|previous app)\b", last_app, raw_command, flags=re.IGNORECASE)
    return raw_command