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
    
    # Agentic Loop Configuration
    "AGENT_MAX_STEPS": 10,
    "AGENT_TIMEOUT": 120,
    "AGENT_RETRY_LIMIT": 2,
    "AGENT_SCRATCHPAD_MAX_CHARS": 8000,
}

# Google Gemini API key (used for embeddings and LLM)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")