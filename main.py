import os
import sys
import warnings
import subprocess
import threading
import time
import ctypes
import logging
import asyncio
import platform
import pygame
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# 1. Suppress all SDK banners and warnings
os.environ['TOGETHER_NO_BANNER'] = '1'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

# 2. Clear terminal before anything else
os.system('cls' if os.name == 'nt' else 'clear')

# 3. Import premium terminal manager (must be in same folder)
from core.terminal.jarvis_terminal import init_terminal, Colors
init_terminal()  # This sets up clean logging and prints premium banner

# --- Your existing imports (after terminal setup) ---
from core.brain.history import load_command_history, save_command_history, command_history
from core.brain.processor import process_with_cohere
from core.brain.executor import execute_actions
from core.brain.memory import ContextMemory
from core.voice import stt, tts
from tools.OpenCloseApps.open_any import start_background_cache_builder
from core.terminal.tray_manager import start_tray_icon

# 🚀 Import STT Status Helper to hide popup
from core.voice.stt_status import hide_stt_popup, exit_stt_popup

# 🚀 Import interrupt flag module (optional, for future use)
from core.voice import interrupt

_is_running = True
_panel_process = None
_stt_popup_process = None

def start_agent_panel():
    global _panel_process
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        panel_script = os.path.join(base_dir, "core", "ui", "agent_panel.py")
        if os.path.exists(panel_script):
            creation_flags = 0
            if platform.system() == 'Windows':
                creation_flags = subprocess.CREATE_NO_WINDOW
            _panel_process = subprocess.Popen(
                [sys.executable, panel_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
            logging.info("✅ Agent Panel started")
        else:
            logging.warning(f"Agent panel not found")
    except Exception as e:
        logging.warning(f"Could not start agent panel: {e}")

def stop_agent_panel():
    global _panel_process
    if _panel_process:
        try:
            _panel_process.terminate()
            _panel_process.wait(timeout=2)
        except:
            _panel_process.kill()
        _panel_process = None
        logging.info("🛑 Agent Panel stopped")

def start_stt_popup():
    global _stt_popup_process
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        popup_script = os.path.join(base_dir, "core", "ui", "stt_popup.py")
        
        if os.path.exists(popup_script):
            creation_flags = 0
            if platform.system() == 'Windows':
                creation_flags = subprocess.CREATE_NO_WINDOW
            _stt_popup_process = subprocess.Popen(
                [sys.executable, popup_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
            logging.info(f"🎙️ STT Popup UI started from {popup_script}")
        else:
            logging.warning(f"STT popup script not found at {popup_script}")
    except Exception as e:
        logging.warning(f"Could not start STT popup: {e}")

def stop_stt_popup():
    global _stt_popup_process
    logging.info("🛑 Sending exit signal to STT Popup...")
    try:
        exit_stt_popup()
    except:
        pass
    
    if _stt_popup_process:
        try:
            _stt_popup_process.wait(timeout=2)
        except:
            _stt_popup_process.kill()
        _stt_popup_process = None
        logging.info("🛑 STT Popup UI stopped")

def main_command_processor(command: str, executor: ThreadPoolExecutor, memory: ContextMemory) -> None:
    raw = command.strip() if command else ""
    if not raw:
        return
    
    # Check if interrupted by background wake word (optional, for future cancellation)
    if interrupt.is_interrupted():
        logging.info("⏸️ Command interrupted by user (wake word during processing).")
        interrupt.clear_interrupt()
        return
    
    try:
        context = memory.get_relevant_context(raw)
    except Exception as e:
        logging.warning(f"Context Memory Error: {e}")
        context = ""
    result = process_with_cohere(raw, context, memory_instance=memory)
    execute_actions(result, executor)
    if 'response' not in result:
        result['response'] = "Action executed."
    command_history.append({
        "command": raw,
        "result": result,
        "timestamp": datetime.now().isoformat()
    })
    save_command_history()
    
    try:
        full_conversation = f"User: {raw}\nJarvis: {result.get('response', '')}"
        memory.add_message("CONVERSATION", full_conversation)
    except Exception as e:
        logging.warning(f"Memory Update Failed: {e}")
        
    if result.get("response"):
        time.sleep(0.1)

def main() -> None:
    global _is_running

    args = [arg.lower() for arg in sys.argv[1:]]
    
    is_dev_mode = "test_jarvis" in args
    use_tray = "system_tray=no" not in args

    # 🆕 Parse forced TTS engine from command line (voice=edge_tts or voice=cartesia)
    forced_tts = None
    for arg in args:
        if arg.startswith("voice="):
            forced_tts = arg.split("=", 1)[1].strip()
            if forced_tts in ["edge_tts", "cartesia"]:
                # Use the already imported global 'tts'
                tts.set_tts_engine(forced_tts)
                logging.info(f"🔊 TTS engine forced to {forced_tts} via command line")
            else:
                logging.warning(f"Unknown voice engine: {forced_tts}. Ignoring. Valid: edge_tts, cartesia")
            break

    # 1. Hide console window ONLY if we are using the Tray
    if use_tray:
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
        except:
            pass

    # 2. 🔥 Resolve custom tray icon path
    icon_path = None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    possible_icon_paths = [
        os.path.join(base_dir, "Data", "icons", "jarvis_icon.png"),
        os.path.join(base_dir, "jarvis_icon.png"),
        os.path.join(base_dir, "assets", "jarvis_icon.png")
    ]
    for p in possible_icon_paths:
        if os.path.exists(p):
            icon_path = p
            if use_tray:
                logging.info(f"✅ Found tray icon: {p}")
            break
    if not icon_path and use_tray:
        logging.warning("⚠️ Custom icon not found, using default blue circle")

    # 3. Start tray icon ONLY if system_tray=no is NOT provided
    if use_tray:
        try:
            tray_thread = threading.Thread(target=start_tray_icon, args=(icon_path,), daemon=True)
            tray_thread.start()
            logging.info("🖥️ Tray icon ready")
        except Exception as e:
            logging.warning(f"Tray icon error: {e}")
    else:
        logging.info("🖥️ Tray disabled. Running in standard console mode.")

    start_agent_panel()
    start_stt_popup()
    start_background_cache_builder()

    # Add boot delay ONLY for voice mode
    if not is_dev_mode:
        logging.info("Booting system...")
        time.sleep(1)

    load_command_history()

    try:
        memory = ContextMemory()
    except Exception as e:
        logging.error(f"Memory init failed: {e}")
        class FakeMemory:
            def get_relevant_context(self, text): return ""
            def add_message(self, role, text): pass
            preferences = {"likes": []}
            ephemeral = {}
        memory = FakeMemory()

    mode = "TEXT" if is_dev_mode else "VOICE"
    if mode == "VOICE":
        logging.info("🎙️ Listening... wake word: 'Jarvis'")
    logging.info("✅ Ready. (Groq + Gemini Embeddings)")

    # 🔥 SINGLE WAKE WORD MANAGER – handles both stopping speech and activation
    if mode == "VOICE":
        stt.get_wake_manager()   # initializes and starts background thread

    with ThreadPoolExecutor(max_workers=5) as executor:
        while _is_running:
            try:
                command = ""
                if mode == "TEXT":
                    try:
                        command = input(f"{Colors.CYAN}{Colors.BOLD}🧠 You:{Colors.RESET} ").strip()
                    except EOFError:
                        break
                else:
                    # Wait for activation event (wake word when idle)
                    if stt.get_wake_manager().wait_for_activation():
                        stt.get_wake_manager().clear_activation()
                        # No need to stop speaking here – background already did if needed
                        tts._stop_playback = False
                        command = stt.listen_command()
                    else:
                        continue

                if command and command.lower() in ["exit", "quit", "stop", "bye"]:
                    logging.info("Shutting down...")
                    _is_running = False
                    tts.stop_speaking()
                    break

                if command:
                    try:
                        hide_stt_popup()
                    except Exception as e:
                        logging.debug(f"Hide popup error: {e}")
                    
                    main_command_processor(command, executor, memory)
                    # Clear interrupt flag after command finishes (in case it was set)
                    interrupt.clear_interrupt()

            except KeyboardInterrupt:
                logging.info("Interrupted by user. Exiting.")
                _is_running = False
                break
            except Exception as e:
                # 🚀 FIX: Ab yahan error ka full traceback print hoga
                logging.exception(f"Loop error: {e}")
                continue

    save_command_history()
    try:
        tts.cleanup_temp()
        pygame.quit()
    except:
        pass
    stop_agent_panel()
    stop_stt_popup()

if __name__ == "__main__":
    main()