import os
import winsound
import speech_recognition as sr
import pvporcupine
from pvrecorder import PvRecorder
from core.logger.logger import logger
import threading
import time
from groq import Groq

# --- API KEYS ---
PICOVOICE_ACCESS_KEY = os.getenv("PICOVOICE_ACCESS_KEY", "oLxGUCx6LY/f8Ru4pUzZIattcQ9NLLmzYkDXKB7vao5dn2laj14DIg==")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = Groq(api_key=GROQ_API_KEY)

# --- STT Status Helper (to show popup) ---
from core.voice.stt_status import update_stt_status

# ==================================================================
# 🔥 SINGLE WAKE WORD MANAGER (Stops speaking + activates in one go)
# ==================================================================
class WakeWordManager:
    def __init__(self):
        self.porcupine = None
        self.recorder = None
        self.activation_event = threading.Event()
        self.running = True
        self._init_porcupine()
        
    def _init_porcupine(self):
        try:
            self.porcupine = pvporcupine.create(access_key=PICOVOICE_ACCESS_KEY, keywords=['jarvis'])
            self.recorder = PvRecorder(device_index=-1, frame_length=self.porcupine.frame_length)
        except Exception as e:
            logger.error(f"Porcupine init error: {e}")
            raise
    
    def start(self):
        self.recorder.start()
        self.thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.thread.start()
        logger.info("🎙️ Single wake word manager started.")
    
    def _listen_loop(self):
        from core.voice import tts
        while self.running:
            pcm = self.recorder.read()
            if self.porcupine.process(pcm) >= 0:
                # Always stop speaking (if any) and set activation
                tts.stop_speaking()
                self.activation_event.set()
                time.sleep(0.3)  # debounce
    
    def wait_for_activation(self, timeout=None):
        return self.activation_event.wait(timeout=timeout)
    
    def clear_activation(self):
        self.activation_event.clear()
    
    def stop(self):
        self.running = False
        if self.recorder:
            self.recorder.stop()
            self.recorder.delete()
        if self.porcupine:
            self.porcupine.delete()

# Global instance
_wake_manager = None

def get_wake_manager():
    global _wake_manager
    if _wake_manager is None:
        _wake_manager = WakeWordManager()
        _wake_manager.start()
    return _wake_manager

# ==================================================================
# LEGACY FUNCTIONS (for compatibility)
# ==================================================================
def wait_for_wake_word():
    return get_wake_manager().wait_for_activation()

def clear_wake_event():
    if _wake_manager:
        _wake_manager.clear_activation()

def start_background_wake_word_listener():
    get_wake_manager()
    logger.debug("Background listener already running.")

# ==================================================================
# 🎤 STT RECOGNITION with Status Updates
# ==================================================================
recognizer = sr.Recognizer()
recognizer.dynamic_energy_threshold = False
recognizer.energy_threshold = 400
recognizer.pause_threshold = 0.5

def play_wake_sound():
    try:
        winsound.Beep(2000, 150)
    except:
        pass

def transcribe_audio(audio_wav_bytes):
    try:
        transcription = groq_client.audio.transcriptions.create(
            file=("audio.wav", audio_wav_bytes),
            model="whisper-large-v3",
            prompt="Hinglish command.",
            language="hi",
        )
        return transcription.text.strip().lower()
    except Exception as e:
        logger.warning(f"Groq error: {e}. Trying Google...")
    try:
        return recognizer.recognize_google(sr.AudioData(audio_wav_bytes, 16000, 2)).strip().lower()
    except:
        return ""

def listen_command():
    # Show "listening" popup
    update_stt_status("listening")
    
    with sr.Microphone(sample_rate=16000) as source:
        logger.info("🎧 Listening... (Speak now)")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        
        # Show "understanding" while processing (will be updated after listen)
        try:
            audio = recognizer.listen(source, timeout=4, phrase_time_limit=10)
            update_stt_status("understanding")
        except sr.WaitTimeoutError:
            update_stt_status("idle")
            return ""
            
    logger.info("🔄 Transcribing via Groq Whisper...")
    command = transcribe_audio(audio.get_wav_data())
    
    ignore_words = ["", "okay", "okay.", "jarvis", "jarvis.", "thanks", "thank you"]
    if command and command not in ignore_words:
        logger.info(f"🗣️ You said: {command}")
        update_stt_status("transcribed", command)
        return command
    else:
        update_stt_status("idle")
        return ""

def listen():
    """Legacy entry point."""
    manager = get_wake_manager()
    if manager.wait_for_activation():
        manager.clear_activation()
        play_wake_sound()
        return listen_command()
    return ""