import os
import winsound
import speech_recognition as sr
import pvporcupine
from pvrecorder import PvRecorder
from modules.logger import logger
from deepgram import DeepgramClient, PrerecordedOptions

# --- API KEYS ---
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "oLxGUCx6LY/f8Ru4pUzZIattcQ9NLLmzYkDXKB7vao5dn2laj14DIg==")
DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "7923d32ca51e5092838822428adc1cdf33f42b23")

# --- CLIENTS INIT ---
dg_client = DeepgramClient(api_key=DEEPGRAM_API_KEY)
try:
    porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keywords=['jarvis'])
    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
except Exception as e:
    logger.error(f"❌ Porcupine Error: {e}")

# ==============================================================================
# 🔥 ULTRA-SIMPLE & FAST MIC SETUP
# ==============================================================================
recognizer = sr.Recognizer()

# ⚡ DYNAMIC THRESHOLD OFF: Yehi lag ka sabse bada reason tha!
recognizer.dynamic_energy_threshold = False  
recognizer.energy_threshold = 400  # Normal aawaz ke liye perfect (Agar mic kam catch kare to ise 300 kar dena)
recognizer.pause_threshold = 0.5   # Chup hote hi 0.5s mein cut!

def play_wake_sound():
    try: winsound.Beep(2000, 150)
    except: pass

def wait_for_wake_word():
    if not recorder.is_recording: recorder.start()
    logger.info("🦅 Waiting for 'Jarvis'...")
    while True:
        if porcupine.process(recorder.read()) >= 0:
            logger.info("⚡ Wake word detected!")
            recorder.stop()
            return True

def transcribe_audio(audio_data):
    """Simple STT logic: Deepgram first, Google as backup."""
    # 1. Try Deepgram
    try:
        options = PrerecordedOptions(
            model="nova-3", smart_format=True, language="hi", encoding="linear16", sample_rate=16000, channels=1
        )
        response = dg_client.listen.prerecorded.v("1").transcribe_file({"buffer": audio_data}, options)
        return response.results.channels[0].alternatives[0].transcript.strip().lower()
    except Exception as e:
        logger.warning(f"⚠️ Deepgram Issue: {e}. Trying Google...")

    # 2. Try Google Fallback
    try:
        return recognizer.recognize_google(sr.AudioData(audio_data, 16000, 2)).strip().lower()
    except:
        return ""

# ==============================================================================
# 🚀 CORE LISTENER
# ==============================================================================
def listen_command():
    with sr.Microphone(sample_rate=16000) as source:
        logger.info("🎧 Listening... (Speak now)")
        
        # Thoda sa noise adjust karega shuru mein
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        try:
            # Simple timeout limits
            audio = recognizer.listen(source, timeout=4, phrase_time_limit=10)
        except sr.WaitTimeoutError:
            return ""
            
    logger.info("🔄 Transcribing...")
    command = transcribe_audio(audio.get_raw_data())
    
    # Faltu words filter karna
    ignore_words = ["", "okay", "okay.", "jarvis", "jarvis.", "thanks", "thank you"]
    if command and command not in ignore_words:
        logger.info(f"🗣️ You said: {command}")
        return command
        
    return ""

def listen():
    if wait_for_wake_word():
        play_wake_sound()
        return listen_command()
    return ""