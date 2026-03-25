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
}

# API keys
COHERE_API_KEY = os.getenv("COHERE_API_KEY")