# modules/voice/tts.py
import os
import re
import time
import asyncio
import threading
import subprocess
import sys
import logging
import queue
from pathlib import Path
from dotenv import load_dotenv

# Setup basic logging to catch previously "silent" errors
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

# Load config
from core.brain.config import (
    EDGE_TTS_VOICE,
    CARTESIA_VOICE_ID,
    CARTESIA_MODEL_ID,
    CARTESIA_SAMPLE_RATE,
    CARTESIA_API_KEY
)

# Optional imports with graceful fallback
try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False
    logging.warning("PyAudio not available.")

try:
    from cartesia import Cartesia
    CARTESIA_SDK_AVAILABLE = True
except ImportError:
    CARTESIA_SDK_AVAILABLE = False
    logging.warning("Cartesia SDK not available.")

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    logging.warning("Edge TTS not available.")

load_dotenv()

# ========== GLOBALS ==========
_stop_playback = False
is_speaking = False
_current_process = None
_audio_engine = None  # PyAudio instance, lazy init
_popup_process = None  # track popup subprocess for immediate termination

# Global Cartesia Client (Fixes latency without breaking websocket context)
_cartesia_client = None

# Forced TTS engine (None = automatic fallback, "edge_tts", "cartesia")
_forced_engine = None

# ========== ADVANCED EMOTION PROCESSING ==========
EMOTION_CONFIG = {
    "anger": {"priority": 11, "keywords": [r"\b(angry|gussa|mad|furious|irritate|hate|bakwas)\b"], "cartesia": "anger", "intensity": "high"},
    "cheerful": {"priority": 10, "keywords": [r"\b(send|done|complete|success|badhiya|shandar|thanks|happy)\b"], "cartesia": "cheerful", "intensity": "highest"},
    "excited": {"priority": 9, "keywords": [r"\b(wow|wah|maza|amazing|superb|zabardast|yay)\b"], "cartesia": "amusement", "intensity": "high"},
    "apologetic": {"priority": 8, "keywords": [r"\b(error|fail|sorry|problem|galti|maaf)\b"], "cartesia": "sadness", "intensity": "low"},
    "sad": {"priority": 7, "keywords": [r"\b(sad|dukh|afsoos|bura|cry)\b"], "cartesia": "sadness", "intensity": "high"},
    "thinking": {"priority": 6, "keywords": [r"\b(search|research|dhundo|wait|processing|loading|thinking|hmm)\b"], "cartesia": "curiosity", "intensity": "medium"},
    "warm": {"priority": 5, "keywords": [r"\b(namaste|hello|hi|welcome|swagat)\b"], "cartesia": "cheerful", "intensity": "low"},
    "fearful": {"priority": 4, "keywords": [r"\b(danger|warning|alert|khatarnaak|scared|darr)\b"], "cartesia": "fear", "intensity": "high"},
    "empathetic": {"priority": 3, "keywords": [r"\b(understood|sympathy|don't worry|koi baat nahi)\b"], "cartesia": "sadness", "intensity": "low"},
    "surprised": {"priority": 2, "keywords": [r"\b(really|shocking|kya|sach mein|omg)\b"], "cartesia": "surprise", "intensity": "high"},
    "calm": {"priority": 1, "keywords": [r"\b(calm|relax|peace|shanti)\b"], "cartesia": None, "intensity": "normal"},
    "confident": {"priority": 1, "keywords": [r"\b(confident|sure|definitely|absolutely)\b"], "cartesia": None, "intensity": "normal"}
}

EMOTION_PATTERNS = []
for emotion, cfg in EMOTION_CONFIG.items():
    for pattern in cfg["keywords"]:
        EMOTION_PATTERNS.append((emotion, re.compile(pattern, re.IGNORECASE), cfg["priority"]))

def detect_emotion(text: str) -> str:
    best_emotion = "calm"
    best_priority = -1
    for emotion, pattern, priority in EMOTION_PATTERNS:
        if pattern.search(text):
            if priority > best_priority:
                best_priority = priority
                best_emotion = emotion
    return best_emotion

def add_pauses(text: str, emotion: str) -> str:
    if emotion == "thinking":
        return f"Hmm... {text.replace(',', ',... ')}"
    elif emotion in ["sad", "apologetic", "empathetic"]:
        return re.sub(r'\b(Sir|sir),\b', r'\1,...', text)
    return text

def apply_dynamic_emotions(text: str, default_emotion: str = None) -> str:
    if default_emotion and default_emotion in EMOTION_CONFIG:
        cfg = EMOTION_CONFIG[default_emotion]
        cartesia_emo = cfg["cartesia"]
        intensity = cfg["intensity"]
        text = add_pauses(text, default_emotion)
        
        if cartesia_emo:
            return f"<emotion name='{cartesia_emo}' intensity='{intensity}'>{text}</emotion>"
        return text

    sentences = re.split(r'(?<=[.!?]) +', text)
    tagged_sentences = []

    for sentence in sentences:
        if not sentence.strip():
            continue
            
        emotion = detect_emotion(sentence)
        cfg = EMOTION_CONFIG.get(emotion, EMOTION_CONFIG["calm"])
        cartesia_emo = cfg["cartesia"]
        intensity = cfg["intensity"]
        
        sentence = add_pauses(sentence, emotion)
        
        if cartesia_emo:
            tagged_sentences.append(f"<emotion name='{cartesia_emo}' intensity='{intensity}'>{sentence}</emotion>")
        else:
            tagged_sentences.append(sentence)

    return " ".join(tagged_sentences)

def extract_and_clean_emotion(text: str):
    if not text:
        return "", None
    match = re.search(r'\[([a-zA-Z]+)\]', text)
    emotion = match.group(1).lower() if match else None
    if match:
        text = re.sub(r'\[[a-zA-Z]+\]', '', text).strip()
    return text, emotion

def clean_text_for_speech(text: str) -> str:
    if not text:
        return ""
    clean = re.sub(r'[\*\_\#\`\-\[\]\>\~]', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

# ========== FORCE ENGINE API ==========
def set_tts_engine(engine: str):
    """
    Force a specific TTS engine. Valid values: 'edge_tts', 'cartesia'
    After setting, speak() will use only that engine, no fallback.
    """
    global _forced_engine
    if engine in ["edge_tts", "cartesia"]:
        _forced_engine = engine
        logging.info(f"🔊 TTS engine forced to: {engine}")
    else:
        logging.warning(f"Invalid TTS engine: {engine}. Valid: 'edge_tts', 'cartesia'")

def get_forced_engine():
    return _forced_engine

# ========== STOP FUNCTION ==========
def stop_speaking():
    global _stop_playback, is_speaking, _current_process, _popup_process
    _stop_playback = True
    is_speaking = False
    
    if _current_process:
        try:
            _current_process.kill()
        except Exception as e:
            logging.error(f"Failed to kill TTS subprocess: {e}")
            
    if _popup_process and _popup_process.poll() is None:
        try:
            _popup_process.terminate()
            _popup_process = None
        except Exception as e:
            logging.error(f"Failed to terminate popup process: {e}")

# ========== CARTESIA STREAMING (WebSocket + Queue + PyAudio) ==========
def _get_cartesia_client():
    """Maintain a single Cartesia client instance to reduce latency."""
    global _cartesia_client
    if _cartesia_client is None:
        try:
            _cartesia_client = Cartesia(api_key=CARTESIA_API_KEY)
        except Exception as e:
            logging.error(f"Failed to initialize Cartesia client: {e}")
            return None
    return _cartesia_client

def _get_ffplay_path():
    possible_paths = [
        r"C:\ffmpeg\bin\ffplay.exe",
        r"C:\Program Files\ffmpeg\bin\ffplay.exe",
        "ffplay"
    ]
    for p in possible_paths:
        if Path(p).exists() or (p == "ffplay" and subprocess.run(["where", "ffplay"], capture_output=True).returncode == 0):
            return p
    return None

def _stream_cartesia(text_with_emotion: str) -> bool:
    global _stop_playback, _audio_engine

    if not PYAUDIO_AVAILABLE or not CARTESIA_SDK_AVAILABLE or not CARTESIA_API_KEY:
        return False

    if _audio_engine is None:
        try:
            _audio_engine = pyaudio.PyAudio()
        except Exception as e:
            logging.error(f"Failed to initialize PyAudio: {e}")
            return False

    sample_rate = CARTESIA_SAMPLE_RATE if CARTESIA_SAMPLE_RATE else 24000
    
    audio_queue = queue.Queue()
    
    def audio_player():
        stream = None
        try:
            while not _stop_playback:
                chunk = audio_queue.get()
                if chunk is None:  # End of stream
                    break
                
                if stream is None:
                    stream = _audio_engine.open(
                        format=pyaudio.paFloat32,
                        channels=1,
                        rate=sample_rate,
                        output=True,
                        frames_per_buffer=2048
                    )
                stream.write(chunk)
        except Exception as e:
            logging.error(f"Audio playback error: {e}")
        finally:
            if stream:
                stream.stop_stream()
                stream.close()

    # Start audio player in background
    player_thread = threading.Thread(target=audio_player, daemon=True)
    player_thread.start()
    
    try:
        client = _get_cartesia_client()
        if not client:
            return False

        with client.tts.websocket_connect() as connection:
            ctx = connection.context(
                model_id=CARTESIA_MODEL_ID or "sonic-3",
                voice={"mode": "id", "id": CARTESIA_VOICE_ID},
                output_format={
                    "container": "raw",
                    "encoding": "pcm_f32le",
                    "sample_rate": sample_rate
                },
                language="hi"
            )
            
            ctx.push(text_with_emotion)
            ctx.no_more_inputs()

            for response in ctx.receive():
                if _stop_playback:
                    break
                if response.type == "chunk" and response.audio:
                    audio_queue.put(response.audio)
            
            # Wait for the queue to empty before finishing
            while not audio_queue.empty() and not _stop_playback:
                time.sleep(0.05)

            return True
            
    except Exception as e:
        logging.error(f"Cartesia streaming failed: {e}")
        return False
        
    finally:
        audio_queue.put(None)
        player_thread.join(timeout=1.0)

# ========== EDGE TTS STREAMING ==========
async def _stream_edge_tts_async(text: str):
    global _current_process, _stop_playback

    ffplay_path = _get_ffplay_path()
    if not ffplay_path:
        logging.error("ffplay not found. Edge TTS fallback will fail.")
        return

    communicate = edge_tts.Communicate(text, EDGE_TTS_VOICE, rate='+25%')
    stealth_flag = 0x08000000 if os.name == 'nt' else 0
    process = None
    
    try:
        process = subprocess.Popen(
            [ffplay_path, "-autoexit", "-nodisp", "-hide_banner", "-loglevel", "error",
             "-probesize", "32", "-analyzeduration", "0", "-sync", "ext", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=stealth_flag
        )
        _current_process = process
        
        async for chunk in communicate.stream():
            if _stop_playback:
                break
            if chunk["type"] == "audio":
                try:
                    process.stdin.write(chunk["data"])
                    process.stdin.flush()
                except (BrokenPipeError, OSError) as pipe_err:
                    logging.error(f"Pipe error while writing to ffplay: {pipe_err}")
                    break
                    
    except Exception as e:
        logging.error(f"Edge TTS async stream failed: {e}")
        
    finally:
        if process and process.stdin:
            try:
                process.stdin.close()
            except Exception as e:
                logging.error(f"Failed to close ffplay stdin: {e}")
                
        if process:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                logging.warning("ffplay did not exit in time. Killing process.")
                process.kill()
            except Exception as e:
                logging.error(f"Error waiting for ffplay process: {e}")
                
        _current_process = None

def _run_edge_stream(text: str):
    asyncio.run(_stream_edge_tts_async(text))

# ========== MAIN SPEAK FUNCTION ==========
def speak(text: str):
    global _stop_playback, is_speaking, _popup_process

    if not text:
        return

    raw_markdown_text, llm_emotion = extract_and_clean_emotion(text)
    if not raw_markdown_text:
        return

    cleaned_for_speech = clean_text_for_speech(raw_markdown_text)

    if is_speaking:
        stop_speaking()
        time.sleep(0.1)

    _stop_playback = False
    is_speaking = True
    _popup_process = None
    
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent
        popup_path = project_root / "core" / "ui" / "popup.py"
        
        if popup_path.exists():
            _popup_process = subprocess.Popen([sys.executable, str(popup_path), raw_markdown_text])
        else:
            logging.error(f"Popup UI script not found at {popup_path}")
    except Exception as e:
        logging.error(f"Failed to launch popup UI: {e}")

    text_tagged = apply_dynamic_emotions(cleaned_for_speech, llm_emotion)

    success = False

    # ---- FORCED ENGINE LOGIC ----
    if _forced_engine == "edge_tts":
        if EDGE_TTS_AVAILABLE:
            logging.info("🔊 Using forced Edge TTS only")
            edge_thread = threading.Thread(target=_run_edge_stream, args=(cleaned_for_speech,))
            edge_thread.start()
            edge_thread.join()
            success = True
        else:
            logging.error("❌ Forced Edge TTS but Edge TTS is not available. No fallback.")
            success = False

    elif _forced_engine == "cartesia":
        if CARTESIA_API_KEY and PYAUDIO_AVAILABLE and CARTESIA_SDK_AVAILABLE:
            success = _stream_cartesia(text_tagged)
        else:
            logging.error("❌ Forced Cartesia but dependencies missing. No fallback.")
            success = False

    else:
        # Normal behaviour (Cartesia → Edge fallback)
        if CARTESIA_API_KEY and PYAUDIO_AVAILABLE and CARTESIA_SDK_AVAILABLE:
            success = _stream_cartesia(text_tagged)

        if not success and EDGE_TTS_AVAILABLE:
            logging.info("Falling back to Edge TTS")
            edge_thread = threading.Thread(target=_run_edge_stream, args=(cleaned_for_speech,))
            edge_thread.start()
            edge_thread.join()
            success = True

    if not success:
        logging.warning("No TTS engine could speak the message")

    is_speaking = False

def cleanup_temp():
    global _audio_engine
    
    if _audio_engine:
        try:
            _audio_engine.terminate()
        except Exception as e:
            logging.error(f"Failed to terminate PyAudio: {e}")
        _audio_engine = None