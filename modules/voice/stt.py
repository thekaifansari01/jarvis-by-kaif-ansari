import os
import winsound
import speech_recognition as sr
import pvporcupine
from pvrecorder import PvRecorder
from modules.logger import logger
from deepgram import DeepgramClient

# --- CONFIGURATION ---
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "oLxGUCx6LY/f8Ru4pUzZIattcQ9NLLmzYkDXKB7vao5dn2laj14DIg==")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "7923d32ca51e5092838822428adc1cdf33f42b23")

# Initialize Deepgram
dg_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)

# --- GLOBAL SETUP (Wake Word) ---
try:
    porcupine = pvporcupine.create(
        access_key=PICOVOICE_ACCESS_KEY,
        keywords=['jarvis']
    )
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
except Exception as e:
    logger.error(f"❌ Initialization Error: {e}")

# ==============================================================================
# 🔥 TERA TRUSTED MIC SETUP 
# ==============================================================================
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 2000  # Tere kamre ke noise ke hisaab se perfect
recognizer.pause_threshold = 0.5    # 0.5 sec shanti = mic cut
recognizer.non_speaking_duration = 0.3

def play_wake_sound():
    try: winsound.Beep(2000, 150)
    except: pass

def wait_for_wake_word():
    """Porcupine se Jarvis naam sunna"""
    if not recorder.is_recording:
        recorder.start()
    logger.info("🦅 Waiting for 'Jarvis'...")
    try:
        while True:
            pcm = recorder.read()
            if porcupine.process(pcm) >= 0:
                logger.info("⚡ Wake word detected!")
                # 🛑 Mic ko yahan free karna zaroori hai
                recorder.stop() 
                return True
    except Exception as e:
        logger.error(f"Error in wake word detection: {e}")
    return False

# ==============================================================================
# 🚀 BLAZING FAST API COMMAND (RAM to RAM)
# ==============================================================================
def listen_command():
    # Tera purana reliable Speech Recognition
    with sr.Microphone(sample_rate=16000) as source:
        logger.info("🎧 Listening... (Speak now)")
        try:
            # 5 sec se zyada chup raha, ya 4 sec se lamba bola toh cut
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=4)
        except sr.WaitTimeoutError:
            logger.info("😶 No speech detected.")
            return ""
        except Exception as e:
            logger.error(f"Mic Error: {e}")
            return ""

    logger.info("🔄 Transcribing via Deepgram...")

    try:
        # 🔥 OPTIMIZATION 1: Direct Memory Upload (No .wav files)
        payload = {"buffer": audio.get_raw_data()}
        
        options = {
            "model": "nova-2",
            "smart_format": True,
            "language": "en-US",
            "encoding": "linear16",
            "sample_rate": 16000,
            "channels": 1
        }

        # HTTP request fire karo (Nova-2 chhote audios ke liye stream jitna hi fast hai)
        response = dg_client.listen.prerecorded.v("1").transcribe_file(payload, options)
        
        # 🔥 OPTIMIZATION 2: Safe Object Parsing (Fastest way)
        transcript = response.results.channels[0].alternatives[0].transcript
        command = transcript.strip().lower()
        
        # Faltu words filter karo
        artifacts = ["thank you.", "thank you", "thanks.", "thanks", "jarvis.", "jarvis", "okay.", "okay", ""]
        if command and command not in artifacts:
            logger.info(f"🗣️ You said: {command}")
            return command
            
        return ""

    except Exception as e:
        logger.error(f"❌ Deepgram Error: {e}")
        return ""

def listen():
    if wait_for_wake_word():
        play_wake_sound()
        return listen_command()
    return ""