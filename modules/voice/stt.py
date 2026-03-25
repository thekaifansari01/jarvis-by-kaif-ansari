import speech_recognition as sr
import pvporcupine
from groq import Groq
from pvrecorder import PvRecorder
from modules.logger import logger
import os
import winsound

# --- CONFIGURATION ---
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "oLxGUCx6LY/f8Ru4pUzZIattcQ9NLLmzYkDXKB7vao5dn2laj14DIg==")
GROQ_API_KEY = os.getenv("GROQ_API_KEY_2")

# Initialize Groq Client for Whisper STT
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# --- GLOBAL RECOGNIZER SETTINGS ---
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = True
# 🔥 OPTIMISED: Lower energy threshold to detect speech faster
recognizer.energy_threshold = 200
# 🔥 OPTIMISED: Shorter pause threshold – stops recording sooner after user stops speaking
recognizer.pause_threshold = 0.5
recognizer.non_speaking_duration = 0.4

# --- GLOBAL WAKE WORD ENGINE ---
porcupine = None
recorder = None

try:
    porcupine = pvporcupine.create(
        access_key=PICOVOICE_ACCESS_KEY,
        keywords=['jarvis']
    )
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
except Exception as e:
    logger.error(f"❌ Failed to initialize Porcupine Globally: {e}")

def play_wake_sound():
    try:
        winsound.Beep(2000, 200)
    except:
        pass

def wait_for_wake_word():
    if not porcupine or not recorder:
        return False
        
    try:
        recorder.start()
        logger.info("🦅 Waiting for wake word 'Jarvis'...")
        while True:
            pcm = recorder.read()
            keyword_index = porcupine.process(pcm)
            if keyword_index >= 0:
                logger.info("⚡ Wake word detected!")
                recorder.stop()
                play_wake_sound()
                return True
    except Exception as e:
        return False
    finally:
        if recorder and recorder.is_recording:
            try: recorder.stop()
            except: pass

# ==============================================================================
# 🎙️ LISTENING LOGIC (Dual-Language Optimized)
# ==============================================================================
def listen_command():
    if not groq_client: return ""

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.3)
        try:
            logger.info("🎧 Listening... (Speak naturally in Hindi/English mix)")
            # 🔥 OPTIMISED: Limit phrase length to 4 seconds to avoid long waiting
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
            logger.info("🔄 Processing via Groq Whisper...")
            
            wav_data = audio.get_wav_data()

            # 🚀 DUAL-LANGUAGE WHISPER CALL
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.wav", wav_data),
                model="whisper-large-v3-turbo",
                response_format="text",
                temperature=0.0,
                prompt="Jarvis, kaise ho? Notepad kholo. Kaif ko email bhejo. Today's weather kya hai? Search karo internet par. Kya command di hai batao."
            )
            
            raw_command = transcription.strip().lower()
            
            # Filter out filler words
            artifacts = ["thank you.", "thank you", "thanks.", "jarvis", "jarvis.", ""]
            if raw_command in artifacts or not raw_command:
                return ""

            logger.info(f"🗣️ You said: {raw_command}")
            return raw_command

        except (sr.WaitTimeoutError, TimeoutError):
            logger.info("😶 No speech detected. Going back to sleep.")
            return ""
        except Exception as e:
            logger.error(f"Listening Error: {repr(e)}")
            return ""

def listen():
    if wait_for_wake_word():
        return listen_command()
    return ""