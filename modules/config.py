import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CONFIG = {
    "COHERE_MODEL": "command-r-plus-08-2024",
    "MAX_TOKENS": 4096,
    "TEMPERATURE": 0.2,
    "COMMAND_HISTORY_LIMIT": 20,
    "LOG_FILE": "Data/jarvis.log",
    "HISTORY_FILE": "Data/command_history.pkl",
    
    # 🆕 Agentic Loop Configuration
    "AGENT_MAX_STEPS": 6,          # Max steps before loop exits
    "AGENT_TIMEOUT": 60,           # Timeout in seconds
    "AGENT_RETRY_LIMIT": 2,        # Retry attempts on tool failure
    "AGENT_SCRATCHPAD_MAX_CHARS": 8000,  # Max chars before summarization
}

# API keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY")