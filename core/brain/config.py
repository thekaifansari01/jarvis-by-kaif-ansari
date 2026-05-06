import os
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 1. GROQ MODELS (API key: GROQ_API_KEY)
# ==========================================
GROQ_ROUTER_MODEL = "llama-3.1-8b-instant"
GROQ_FAST_MODEL = "llama-3.3-70b-versatile"
GROQ_SUMMARY_MODEL = "openai/gpt-oss-120b"      # for memory summarization & insights
GROQ_WHISPER_MODEL = "whisper-large-v3"
GROQ_EMAIL_SUMMARY_MODEL = "llama-3.1-8b-instant"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==========================================
# 2. GEMINI MODELS (API key: GEMINI_API_KEY)
# ==========================================
GEMINI_AGENT_MODEL = "gemma-4-31b-it"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-2"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ==========================================
# 3. TOGETHER AI (FLUX) – API key: TOGETHER_AI
# ==========================================
FLUX_IMAGE_MODEL = "black-forest-labs/FLUX.1-schnell"
TOGETHER_API_KEY = os.getenv("TOGETHER_AI")

# ==========================================
# 4. AI HORDE (no API key, just model name)
# ==========================================
AI_HORDE_IMAGE_MODEL = "AlbedoBase XL (SDXL)"

# ==========================================
# 5. TTS MODELS (Edge TTS – no key; Cartesia needs key)
# ==========================================
EDGE_TTS_VOICE = "hi-IN-MadhurNeural"
CARTESIA_VOICE_ID = "4877b818-c7fe-4c89-b1cf-eadf8e23da72"
CARTESIA_MODEL_ID = "sonic-3"
CARTESIA_SAMPLE_RATE = 44100
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

# ==========================================
# 6. OTHER PARAMETERS
# ==========================================
EMBEDDING_DIM = 768
WHISPER_ENERGY_THRESHOLD = 400
WHISPER_PAUSE_THRESHOLD = 0.5
WHISPER_LISTEN_TIMEOUT = 4
WHISPER_PHRASE_TIME_LIMIT = 10
DEEP_RESEARCH_TIMEOUT = 420
EMAIL_SUMMARY_MAX_TOKENS = 40

# ==========================================
# 7. OTHER API KEYS (no models)
# ==========================================
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
PICOVOICE_API_KEY = os.getenv("PICOVOICE_API_KEY")
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")

# For backward compatibility, also keep CONFIG dict if used elsewhere
CONFIG = {
    "AGENT_MAX_STEPS": 10,
    "AGENT_TIMEOUT": 900,
    "AGENT_RETRY_LIMIT": 2,
    "AGENT_SCRATCHPAD_MAX_CHARS": 15000,
}