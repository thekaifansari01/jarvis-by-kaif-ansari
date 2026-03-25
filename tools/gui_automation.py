import pyautogui
import time
from typing import Dict, Optional
from modules.logger import logger

# Configure PyAutoGUI
pyautogui.FAILSAFE = True  # Top-left corner triggers FailSafeException
pyautogui.PAUSE = 0.5

def perform_gui_action(action: Dict[str, any]) -> Optional[str]:
    """
    Executes PyAutoGUI actions safely with parameter mapping for AI generated commands.
    """
    try:
        action_type = action.get("action_type", "").lower()
        params = action.get("params", {})

        if not action_type:
            return "Bhai, action type missing hai!"

        # --- 1. WAIT ACTION ---
        if action_type == "wait":
            seconds = float(params.get("seconds", 1))
            time.sleep(seconds)
            return f"Waited {seconds}s"

        # --- 2. KEYBOARD ACTIONS ---
        if action_type == "typewrite" or action_type == "write":
            # AI might send 'text', 'message', or 'value'
            text = params.get("value") or params.get("text") or params.get("message")
            interval = float(params.get("interval", 0.05))
            if not text: 
                return "Bhai, type karne ke liye text nahi mila."
            pyautogui.typewrite(text, interval=interval)
            return f"Typed: {text}"

        elif action_type == "press":
            key = params.get("key_to_press") or params.get("key")
            if not key: return "Key missing for press action."
            # Handle multiple presses if needed
            presses = int(params.get("presses", 1))
            interval = float(params.get("interval", 0.1))
            pyautogui.press(key, presses=presses, interval=interval)
            return f"Pressed: {key}"

        elif action_type == "hotkey":
            keys = params.get("keys", [])
            if not keys: return "Keys missing for hotkey."
            pyautogui.hotkey(*keys)
            return f"Performed hotkey: {keys}"

        # --- 3. MOUSE ACTIONS ---
        elif action_type == "click":
            # Safe unpacking with defaults
            x = params.get("x")
            y = params.get("y")
            clicks = int(params.get("clicks", 1))
            interval = float(params.get("interval", 0.1))
            button = params.get("button", "left")
            
            # PyAutoGUI handles None x,y by clicking current position
            pyautogui.click(x=x, y=y, clicks=clicks, interval=interval, button=button)
            return f"Clicked {button} at {x},{y}"

        elif action_type in ["moveto", "move"]:
            x = params.get("x")
            y = params.get("y")
            duration = float(params.get("duration", 0.5))
            if x is None or y is None: return "Coordinates missing for move."
            pyautogui.moveTo(x, y, duration=duration)
            return f"Moved to {x},{y}"

        elif action_type == "scroll":
            # AI mapping: 'amount', 'value', 'steps' -> 'clicks'
            amount = params.get("clicks") or params.get("amount") or params.get("value")
            if not amount: return "Scroll amount missing."
            pyautogui.scroll(int(amount))
            return f"Scrolled {amount}"

        elif action_type in ["dragto", "drag"]:
            x = params.get("x")
            y = params.get("y")
            duration = float(params.get("duration", 0.5))
            button = params.get("button", "left")
            if x is None or y is None: return "Coordinates missing for drag."
            pyautogui.dragTo(x, y, duration=duration, button=button)
            return f"Dragged to {x},{y}"

        # --- 4. SYSTEM ACTIONS ---
        elif action_type == "screenshot":
            filename = params.get("filename", f"screenshot_{int(time.time())}.png")
            pyautogui.screenshot(filename)
            logger.info(f"Screenshot saved: {filename}")
            return f"Screenshot saved as {filename}"

        # --- 5. FALLBACK (With Safety Check) ---
        else:
            if hasattr(pyautogui, action_type):
                func = getattr(pyautogui, action_type)
                # Risky call, wrapping in specific try-catch
                try:
                    func(**params)
                    return f"Executed generic action: {action_type}"
                except TypeError as e:
                    logger.error(f"Param mismatch for {action_type}: {e}")
                    return f"Bhai, {action_type} ke parameters galat the."
            else:
                return f"Unknown action: {action_type}"

    except pyautogui.FailSafeException:
        logger.warning("FailSafe triggered from mouse corner.")
        return "🛑 Action stopped by User (FailSafe)."
    
    except Exception as e:
        logger.error(f"GUI Action Failed: {e}")
        return f"Error: {str(e)}"