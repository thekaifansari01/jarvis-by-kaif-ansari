import sys
import time
import threading
import subprocess
import os
import pygame
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- MODULE IMPORTS ---
from modules.logger import logger
from modules.history import load_command_history, save_command_history, command_history
from modules.processor import process_with_cohere 
from modules.executor import execute_actions
from modules.memory import ContextMemory
from modules.voice import stt, tts 
from modules.scout.scout import SmartScout 
import logging
import asyncio
import asyncio
import platform

# Suppress annoying asyncio/aiohttp unclosed session warnings in Windows
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
_is_running = True
_panel_process = None  # To track agent panel subprocess

def start_agent_panel():
    """Start agent_panel.py as a background subprocess (without extra console window)"""
    global _panel_process
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        panel_script = os.path.join(base_dir, "modules", "agent_panel.py")
        
        if os.path.exists(panel_script):
            # Use CREATE_NO_WINDOW flag on Windows to avoid extra console
            creation_flags = 0
            if platform.system() == 'Windows':
                creation_flags = subprocess.CREATE_NO_WINDOW
                
            _panel_process = subprocess.Popen(
                [sys.executable, panel_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags
            )
            logger.info("✅ Agent Panel started automatically (background)")
        else:
            logger.warning(f"⚠️ Agent panel not found at {panel_script}")
    except Exception as e:
        logger.warning(f"⚠️ Could not start agent panel: {e}")

def stop_agent_panel():
    """Terminate agent panel subprocess"""
    global _panel_process
    if _panel_process:
        try:
            _panel_process.terminate()
            _panel_process.wait(timeout=2)
        except:
            _panel_process.kill()
        _panel_process = None
        logger.info("🛑 Agent Panel stopped")

def main_command_processor(command: str, executor: ThreadPoolExecutor, memory: ContextMemory) -> None:
    """
    Orchestrates the AI pipeline: 
    Memory -> Processing -> Action Execution -> History/TTS.
    """
    raw = command.strip() if command else ""
    if not raw: return

    # 1. Fetch Context (RAG & Memory)
    try:
        context = memory.get_relevant_context(raw)
    except Exception as e:
        logger.warning(f"⚠️ Context Memory Error: {e}")
        context = ""

    # 2. AI Processing (Determine Intent via Router/Agent)
    logger.info(f"🧠 Processing Intent for: {raw}")
    result = process_with_cohere(raw, context, memory_instance=memory) 
    
    # 3. Execute Actions (Apps, Search, Automation, Workspace, Email, WhatsApp)
    execute_actions(result, executor)
    
    # 4. Fallback Response & History Saving
    if 'response' not in result:
        result['response'] = "Action executed."

    command_history.append({
        "command": raw,
        "result": result,
        "timestamp": datetime.now().isoformat()
    })
    save_command_history()
    
    # 5. Memory Update
    try:
        memory.add_message("USER", raw)
        memory.add_message("CHATBOT", result.get("response", ""))
    except Exception as e:
        logger.warning(f"⚠️ Memory Update Failed: {e}")

    if result.get("response"):
        time.sleep(1)

# --- MAIN APPLICATION LOOP ---
def main() -> None:
    global _is_running
    
    is_dev_mode = len(sys.argv) > 1 and sys.argv[1] == "test_jarvis"
    
    # 🆕 Start agent panel before anything else
    start_agent_panel()
    
    if not is_dev_mode:
        logger.info("⏳ Waiting 10s for system startup...")
        time.sleep(10) 

    load_command_history()
    
    try:
        memory = ContextMemory()
    except Exception as e:
        logger.error(f"❌ Critical Memory Init Failed: {e}")
        class FakeMemory:
            def get_relevant_context(self, text): return ""
            def add_message(self, role, text): pass
            preferences = {"likes": []}
            ephemeral = {}
        memory = FakeMemory()

    try:
        scout = SmartScout(memory) 
        def scout_worker():
            logger.info("🕵️‍♂️ Scout Background Thread Started (15 min interval).")
            time.sleep(30) 
            while _is_running:
                try:
                    scout.run_scout_cycle()
                except Exception as e:
                    logger.error(f"Scout Error: {e}")
                for _ in range(900): 
                    if not _is_running: break
                    time.sleep(1)

        scout_thread = threading.Thread(target=scout_worker, daemon=True)
        scout_thread.start()
    except Exception as e:
        logger.error(f"❌ Scout Init Failed: {e}")

    if is_dev_mode:
        mode = "TEXT"
        logger.info("⌨️  DEVELOPER MODE: Type your commands.")
    else:
        mode = "VOICE"
        logger.info("🎙️  JARVIS MODE: Listening via Microphone... (Say 'Jarvis')")
    
    logger.info("✅ Jarvis ready. (Hybrid Engine Online: Groq + Cohere)")

    with ThreadPoolExecutor(max_workers=5) as executor:
        while _is_running:
            try:
                command = ""
                if mode == "TEXT":
                    try:
                        command = input("🧠 You: ").strip()
                    except EOFError:
                        break
                else:
                    if stt.wait_for_wake_word():
                        if tts.is_speaking: tts.stop_speaking() 
                        tts._stop_playback = False
                        command = stt.listen_command()
                        if command: logger.info(f"🗣️  Recognized: {command}")
                    else: continue 

                if command and command.lower() in ["exit", "quit", "stop", "bye"]:
                    logger.info("👋 Jarvis shutting down...")
                    _is_running = False 
                    tts.stop_speaking()
                    break

                if command:
                    main_command_processor(command, executor, memory)

            except KeyboardInterrupt:
                logger.info("🛑 Jarvis interrupted by user. Exiting.")
                _is_running = False
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                continue

    save_command_history()
    tts.cleanup_temp()
    pygame.quit()
    
    # 🆕 Stop agent panel on exit
    stop_agent_panel()

if __name__ == "__main__":
    main()