import os
import asyncio
import edge_tts
import re
import threading
import subprocess
import sys
import time

# --- CONFIGURATION ---
VOICE = "hi-IN-MadhurNeural"

_stop_playback = False
is_speaking = False  
_current_process = None 

def stop_speaking():
    global _stop_playback, is_speaking, _current_process
    _stop_playback = True
    is_speaking = False 
    if _current_process:
        try:
            _current_process.kill()
        except:
            pass

def clean_text(text):
    if not text: return ""
    clean = re.sub(r'[\*\_\#\`\-\[\]]', '', text) 
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

# --- TRUE NATIVE STREAMING (BULLET-PROOF) ---
async def stream_audio_realtime(text):
    global _current_process, _stop_playback
    
    communicate = edge_tts.Communicate(text, VOICE, rate='+25%')
    stealth_flag = 0x08000000 if os.name == 'nt' else 0

    try:
        # Added -hide_banner and -loglevel error to keep it silent
        _current_process = subprocess.Popen(
            [r"C:\ffmpeg\bin\ffplay.exe", "-autoexit", "-nodisp", "-hide_banner", "-loglevel", "error", "-probesize", "32", "-analyzeduration", "0", "-sync", "ext", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=stealth_flag
        )
    except FileNotFoundError:
        print("❌ Error: FFmpeg install nahi hai! Path check karo: C:\\ffmpeg\\bin\\ffplay.exe")
        return

    try:
        async for chunk in communicate.stream():
            if _stop_playback:
                break
            if chunk["type"] == "audio":
                try:
                    _current_process.stdin.write(chunk["data"])
                    _current_process.stdin.flush()
                except (BrokenPipeError, OSError):
                    # Agar ffplay close ho jaye toh loop break kar do bina crash hue
                    break
                    
    except Exception as e:
        # Edge-TTS ya network ka koi error aaye toh ignore karo
        pass
        
    finally:
        try:
            if _current_process and _current_process.stdin:
                _current_process.stdin.close()
            if _current_process:
                _current_process.wait(timeout=2) # 2 sec wait karo, warna aage badho
        except:
            pass

def run_async_stream(text):
    # Modern approach to handle event loops cleanly
    try:
        asyncio.run(stream_audio_realtime(text))
    except Exception:
        pass

# --- MAIN SPEAK FUNCTION ---
def speak(text):
    global _stop_playback, is_speaking
    
    if not text: return
    cleaned_text = clean_text(text)
    if not cleaned_text: return
    
    if is_speaking:
        stop_speaking()
        time.sleep(0.1)

    _stop_playback = False
    is_speaking = True 

    # --- POPUP LAUNCH ---
    popup_process = None
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        popup_path = os.path.join(current_dir, "popup.py")
        if os.path.exists(popup_path):
            popup_process = subprocess.Popen([sys.executable, popup_path, cleaned_text])
    except Exception:
        pass

    stream_thread = threading.Thread(target=run_async_stream, args=(cleaned_text,))
    stream_thread.start()
    stream_thread.join() 
    
    if popup_process and popup_process.poll() is None:
        popup_process.terminate()
        
    is_speaking = False 

def cleanup_temp():
    pass