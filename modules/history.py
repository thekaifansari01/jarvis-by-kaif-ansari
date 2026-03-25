from collections import deque
try:
    from modules.config import CONFIG
except ImportError:
    CONFIG = {"COMMAND_HISTORY_LIMIT": 10}  # Fallback agar config fail ho jaye
from modules.logger import logger

# In-memory command history (Fastest way to store short-term memory)
history_limit = CONFIG.get("COMMAND_HISTORY_LIMIT", 10) if isinstance(CONFIG, dict) else 10
command_history = deque(maxlen=history_limit)

def load_command_history() -> None:
    """No-op: History is now in-memory only to keep it blazing fast."""
    logger.info("Command history initialized in-memory")

def save_command_history() -> None:
    """No-op: History is not saved to disk anymore to prevent IO bottleneck."""
    pass

def generate_context_summary() -> str:
    """Generate a clean, text-based summary of recent conversation + actions."""
    if not command_history:
        return "No previous conversation."
    
    summary = []
    # Get last 3 interactions to maintain immediate context without overloading the LLM
    for entry in list(command_history)[-3:]:
        cmd = entry.get("command", "").strip()
        result = entry.get("result", {})
        
        if not cmd:
            continue
            
        # 1. Capture what Jarvis said
        response_text = result.get("response", "").strip()
        
        # 2. Capture what Jarvis actually DID (Actions)
        actions = []
        if result.get("apps_to_open"):
            actions.append(f"opened {', '.join(result['apps_to_open'])}")
        if result.get("apps_to_close"):
            actions.append(f"closed {', '.join(result['apps_to_close'])}")
        if result.get("youtube_play"):
            actions.append(f"played on youtube: {result['youtube_play']}")
        if result.get("search_query"):
            actions.append(f"searched for: {result['search_query']}")
            
        action_str = f" [System Action: {', '.join(actions)}]" if actions else ""
        
        # 3. Format the interaction perfectly for Llama 70B
        interaction = f"User: {cmd}"
        if response_text:
            interaction += f"\nJarvis: {response_text}{action_str}"
            
        summary.append(interaction)
        
    return "\n\n".join(summary)