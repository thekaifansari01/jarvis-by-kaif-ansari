import sys
import time
import threading
import pygame
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- MODULE IMPORTS ---
from modules.logger import logger
from modules.history import load_command_history, save_command_history, command_history
# Note: process_with_cohere is now internally acting as a Hybrid router
from modules.processor import process_with_cohere 
from modules.executor import execute_actions
from modules.memory import ContextMemory
from modules.voice import stt, tts 
from modules.scout.scout import SmartScout # ⚡ Added Scout Import

import asyncio
import platform

# ⚡ BUG FIX 1: Windows specific event loop fix (Prevents RuntimeError: Event loop is closed)
if platform.system() == 'Windows':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
# --- GLOBAL FLAGS ---
_is_running = True

# --- COMMAND PROCESSING LOGIC ---
def main_command_processor(command: str, executor: ThreadPoolExecutor, memory: ContextMemory) -> None:
    """
    Orchestrates the AI pipeline: 
    Memory -> Processing -> Action Execution -> Result Summarization -> History/TTS.
    """
    raw = command.strip() if command else ""
    if not raw: return

    # 1. Fetch Context (RAG & Memory)
    try:
        context = memory.get_relevant_context(raw)
    except Exception as e:
        logger.warning(f"⚠️ Context Memory Error: {e}")
        context = ""

    # 2. First Pass: AI Processing (Determine Intent)
    logger.info(f"🧠 Processing Intent for: {raw}")
    # This will now route to Groq by default for speed
    result = process_with_cohere(raw, context) 
    
    # 3. Execute Actions (Apps, Search, Automation, Workspace Read)
    search_results = execute_actions(result, executor)
    
    # 4. Second Pass: Analyze Results & Execute Conditional Actions (Email/GUI)
    # ⚡ BUG FIX 2: Modified summary_command to enforce execution of conditional actions
    if search_results: 
        logger.info("🧠 Analyzing fetched data (Pass 2)...")
        
        # Enhanced summary command to force AI to remember the 'Email' or 'Type' part
        summary_command = (
            f"Original Request: {raw}. Data Found: {search_results[:2500]}. "
            f"Now provide the final response and MUST execute any pending actions (like sending email or typing) if conditions are met. "
            f"Do NOT search or read files again."
        )
        
        # Deep Brain (120B) is best for this conditional logic
        final_result = process_with_cohere(summary_command, context, search_results=search_results)
        
        if final_result:
            # 🔥 CRITICAL: Execute the actions (This will send the email AND speak)
            execute_actions(final_result, executor)
            result = final_result # Update history with the final outcome

    # 5. Fallback Response & History Saving
    if 'response' not in result:
        result['response'] = "Action executed."

    command_history.append({
        "command": raw,
        "result": result,
        "timestamp": datetime.now().isoformat()
    })
    save_command_history()
    
    # 6. Memory Update & Audio Prep
    try:
        memory.add_message("USER", raw)
        memory.add_message("CHATBOT", result.get("response", ""))
    except Exception as e:
        logger.warning(f"⚠️ Memory Update Failed: {e}")

    # Fix: Short delay to prevent audio driver conflicts if mic was just active
    if result.get("response"):
        time.sleep(1)

# --- MAIN APPLICATION LOOP ---
def main() -> None:
    global _is_running
    
    # Check for Developer Mode (Text Input)
    is_dev_mode = len(sys.argv) > 1 and sys.argv[1] == "test_jarvis"
    
    if not is_dev_mode:
        logger.info("⏳ Waiting 10s for system startup...")
        time.sleep(10) 

    load_command_history()
    
    # Initialize Memory
    try:
        memory = ContextMemory()
    except Exception as e:
        logger.error(f"❌ Critical Memory Init Failed: {e}")
        # Fallback dummy memory class to prevent crash
        class FakeMemory:
            def get_relevant_context(self, text): return ""
            def add_message(self, role, text): pass
            preferences = {"likes": []} # Fallback
        memory = FakeMemory()

    # 👇 ⚡ SCOUT BACKGROUND THREAD INITIALIZATION 👇
    try:
        scout = SmartScout(memory) # Share existing memory
        
        def scout_worker():
            logger.info("🕵️‍♂️ Scout Background Thread Started (15 min interval).")
            # Wait 30 seconds on boot so system stabilizes before first scan
            time.sleep(30) 
            
            while _is_running:
                try:
                    scout.run_scout_cycle()
                except Exception as e:
                    logger.error(f"Scout Error: {e}")
                
                # Smart 15 Minute (900 seconds) wait
                # Breaks immediately if Jarvis is turned off
                for _ in range(900): 
                    if not _is_running:
                        break
                    time.sleep(1)

        scout_thread = threading.Thread(target=scout_worker, daemon=True)
        scout_thread.start()
    except Exception as e:
        logger.error(f"❌ Scout Init Failed: {e}")
    # 👆 ⚡ SCOUT INITIALIZATION END 👆

    # User Interface Logs
    if is_dev_mode:
        mode = "TEXT"
        logger.info("⌨️  DEVELOPER MODE: Type your commands.")
    else:
        mode = "VOICE"
        logger.info("🎙️  JARVIS MODE: Listening via Microphone... (Say 'Jarvis')")
    
    logger.info("✅ Jarvis ready. (Hybrid Engine Online: Groq + Cohere)")

    # Thread Pool for background tasks
    with ThreadPoolExecutor(max_workers=5) as executor:
        while _is_running:
            try:
                command = ""

                # --- INPUT HANDLING ---
                if mode == "TEXT":
                    try:
                        command = input("🧠 You: ").strip()
                    except EOFError:
                        break
                else:
                    # Voice Mode: Wait for Wake Word -> Stop TTS -> Listen
                    if stt.wait_for_wake_word():
                        if tts.is_speaking:
                            tts.stop_speaking() 
                        
                        tts._stop_playback = False
                        command = stt.listen_command()
                        
                        if command:
                            logger.info(f"🗣️  Recognized: {command}")
                    else:
                        continue 

                # --- EXIT COMMANDS ---
                if command and command.lower() in ["exit", "quit", "stop", "bye"]:
                    logger.info("👋 Jarvis shutting down...")
                    _is_running = False # This will also stop the Scout thread cleanly
                    tts.stop_speaking()
                    break

                # --- EXECUTE ---
                if command:
                    main_command_processor(command, executor, memory)

            except KeyboardInterrupt:
                logger.info("🛑 Jarvis interrupted by user. Exiting.")
                _is_running = False
                break
            except Exception as e:
                logger.error(f"❌ Error in main loop: {e}")
                continue

    # Cleanup
    save_command_history()
    tts.cleanup_temp()
    pygame.quit()

if __name__ == "__main__":
    main()