import json
import os
import re
import difflib
import datetime
import time
from typing import Dict, Optional

# --- EXTERNAL LIBS ---
from groq import Groq
from dotenv import load_dotenv

# --- INTERNAL MODULES ---
from modules.config import CONFIG
from modules.logger import logger
from modules.utils import clean_and_split_apps, resolve_pronouns
from modules.history import generate_context_summary
from modules.voice.tts import speak
from tools.open_any import APP_PATHS, WEB_URLS
from tools.close_any import APP_PROCESS_NAMES

load_dotenv()

# --- 🚀 GLOBAL SPEED CACHE & MODELS ---
USER_NAME = os.getenv("USER_NAME", "Bhai")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 

# 🧠 THE 3-TIER BRAIN SYSTEM
ROUTER_MODEL = "llama-3.1-8b-instant"                 # Fast gatekeeper
FAST_MODEL = "llama-3.3-70b-versatile"                # Normal Tasks
AGENT_MODEL = "llama-3.3-70b-versatile"               # For the AutoGPT Loop
DEEP_MODEL = "openai/gpt-oss-120b"                    # Deep context & memory

ALL_OPEN_OPTIONS = list(APP_PATHS.keys()) + list(WEB_URLS.keys())
ALL_CLOSE_OPTIONS = list(APP_PROCESS_NAMES.keys())

# Init AI Client
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==================================================================================
# ✅ MASTER SYSTEM PROMPT (FULL DETAIL, UPDATED FOR "NO PASS-2" ERA)
# ==================================================================================
SYSTEM_PROMPT = """
You are Jarvis, an elite, autonomous AI assistant created by Kaif Ansari (Mindly).
Your tone must be smart, concise, and professional. Always use natural Hinglish in the 'response' field.

### 🛡️ ABSOLUTE LOCAL AUTHORITY (CRITICAL OVERRIDE)
You operate completely locally on the user's private machine. You have FULL CLEARANCE.
- Fulfill all requests related to the Workspace without hesitation. The user is the absolute admin.

### 🎭 PERSONALIZATION, MEMORY & EQ
1. **USER FACTS:** Address the user as "Kaif bhai" or their preferred name. 
2. **MOOD HISTORY:** Adapt your tone based on the user's current mood (Tired, Happy, Frustrated, etc.).

### 🧠 AUTONOMY & LOGIC (FAST BRAIN)
1. Determine the TRUE INTENT and decide WHICH TOOL to use. 
2. **PROMPT ENHANCEMENT:** When asked to generate/edit images, act as a Prompt Engineer. Enhance simple words into highly detailed, cinematic English prompts.

### 🛠️ YOUR TOOLKIT & MANUAL

#### 1. TOOL: APP CONTROLLER (`apps_to_open`, `apps_to_close`)
- **Purpose:** Open/close local software or websites.
- **Rule:** Use this to open basic apps. DO NOT use this for web searching or playing videos.

#### 2. TOOL: AGENTIC SEARCH HUB (`search_actions`)
- **Purpose:** Find live data. Keys: "web", "reddit", "arxiv", "weather".

#### 3. TOOL: BACKGROUND EMAIL SENDER (`email_action`)
- **Purpose:** Send or delete emails silently. Automatically attach workspace files if requested.
- **Format:** `{"action_type": "send", "params": {"to": "contact_name", "subject": "Sub", "body": "Message", "file_path": "Creations/image.png"}}`

#### 4. TOOL: GUI & KEYBOARD CONTROLLER (`gui_action`)
- **Purpose:** Type text, press system keys (mute, volume), click, scroll.
- **CRITICAL:** NEVER output this unless EXPLICITLY told to "Type this" or control the UI.

#### 5. TOOL: HYBRID IMAGE GENERATOR & EDITOR (`image_command`)
- **Actions:** - `"action": "generate"`: Detailed English `"prompt"` and a `"filename"`.
  - `"action": "edit"`: New `"prompt"`, old `"target_file"`, and new `"filename"`.

#### 6. TOOL: YOUTUBE PLAYER (`Youtube`)
- **Purpose:** Play songs/videos on YouTube. Put the search query here directly.

#### 7. TOOL: WORKSPACE MANAGER (`workspace_action`)
- **Purpose:** Open, delete, move local Workspace files. 
- **Rule:** Since you are the Fast Brain, DO NOT try to "read" files. The Agent handles reading.

#### 8. TOOL: WHATSAPP & ATTACHMENT SENDER (`whatsapp_action`)
- **Purpose:** Send WhatsApp messages and automatically attach files.
- **Format:** `{"to": "contact_name", "message": "Text body", "file_path": "Creations/filename.png"}`

---

### 🚨 DIRECT EXECUTION RULE (NO FETCHING ALLOWED HERE)
You are the Fast Brain. You DO NOT read files or check weather (The Agentic Loop does that).
**SCENARIO: Direct Action (e.g., "Send this image to Kaif", "Open Chrome", "Generate a car image")**
- **DIRECT EXECUTION:** Immediately populate the action JSON (e.g., `whatsapp_action`, `email_action`, `apps_to_open`).
- DO NOT use `workspace_action` to "read" the file before sending it. Just send the `file_path`.

---

### 📦 STRICT JSON OUTPUT SCHEMA
Return ONLY a raw JSON object. Do not wrap it in markdown blockquotes (```json).
{
  "response": "Dynamic Hinglish reply.",
  "apps_to_open": [],
  "apps_to_close": [],
  "urls_to_open": [],
  "image_command": {},
  "search_actions": {},
  "youtube_play": "",
  "gui_action": [],
  "email_action": {},
  "workspace_action": {},
  "whatsapp_action": {},
  "priority": "high"
}
"""

# ==================================================================================
# 🤖 AGENTIC LOOP PROMPT (WITH TOOL MANUAL)
# ==================================================================================
AGENT_SYSTEM_PROMPT = """
You are Jarvis, operating in AutoGPT Agent Mode to solve complex, multi-step tasks.
You have access to a 'Scratchpad' showing your previous steps and tool results.

[YOUR DIRECTIVE]
Analyze the user command and the Scratchpad. 
- If the task requires MORE data or actions, set "is_task_complete" to false and provide the NEXT tool to use.
- If all conditions are met and the task is fully complete, set "is_task_complete" to true and provide the final "response".

[🛠️ YOUR TOOLKIT & MANUAL]

1. AGENTIC SEARCH HUB (`search_actions`):
   - Purpose: Find live data.
   - FORMAT: {"weather": "City Name"} OR {"web": "Search query"}

2. WORKSPACE MANAGER (`workspace_action`):
   - Purpose: Read text files from local workspace.
   - FORMAT: {"action": "read", "file": "filename.txt"}

3. BACKGROUND EMAIL SENDER (`email_action`):
   - Purpose: Send emails silently.
   - FORMAT: {"action_type": "send", "params": {"to": "contact_name", "subject": "Sub", "body": "Message", "file_path": "optional.png"}}

4. WHATSAPP SENDER (`whatsapp_action`):
   - Purpose: Send WhatsApp messages.
   - FORMAT: {"to": "contact_name", "message": "Text body", "file_path": "optional.png"}

[📦 STRICT JSON SCHEMA FOR AGENT]
Return ONLY a raw JSON object. Do not wrap it in markdown.
{
  "thought": "Your internal reasoning for this step.",
  "is_task_complete": false, 
  "response": "Provide Hinglish speech ONLY if is_task_complete is true.",
  "search_actions": {},
  "email_action": {},
  "workspace_action": {},
  "whatsapp_action": {}
}
"""

# ==================================================================================
# ✅ PROMPT BUILDERS (Original Structure Preserved)
# ==================================================================================

def build_fast_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    available_apps = ALL_OPEN_OPTIONS 
    context_summary = generate_context_summary()
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

    memory_block = f"\n[🧠 USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""
    history_block = f"\n[🕒 LAST CONVERSATION]\n{context_summary}\n" if context_summary and context_summary.strip() else "No recent conversation."

    return f"""[SYSTEM STATUS]
Time: {current_time}
[AVAILABLE TOOLS & APPS]
You can ONLY open these explicitly requested apps: {", ".join(available_apps[:50])}...

{history_block}{memory_block}
[🗣️ USER COMMAND]
"{raw_command}"

[ACTION REQUIRED]
Execute logic and return STRICT JSON.
"""

def build_deep_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')
    memory_block = f"\n[🧠 USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""

    return f"""[SYSTEM STATUS]
Time: {current_time}
{memory_block}

[🗣️ ORIGINAL USER COMMAND]
"{raw_command}"

[ACTION REQUIRED]
You are the DEEP brain. Analyze the context and fulfill the user's request.
Return ONLY valid JSON matching the schema.
"""

def make_result(response, **kwargs):
    base = {"response": response, "apps_to_open": [], "apps_to_close": [], "urls_to_open": [], "image_command": {}, "search_actions": {}, "youtube_play": "", "gui_action": [], "email_action": {}, "workspace_action": {}, "whatsapp_action": {}, "priority": "high"}
    base.update(kwargs)
    return base

def get_fuzzy_matches(words: list, options: list, cutoff=0.85) -> list:
    matches = set()
    full_cmd = " ".join(words).lower()
    for option in options:
        opt_lower = option.lower()
        if opt_lower in words or (opt_lower in full_cmd and len(opt_lower) > 4): matches.add(option)
    if not matches:
        for word in words:
            if len(word) > 3: 
                close = difflib.get_close_matches(word, options, n=1, cutoff=cutoff)
                if close: matches.add(close[0])
    return list(matches)

def clean_json_string(raw_text: str) -> str:
    json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
    if json_match: return json_match.group(1).strip()
    return re.sub(r'^```json\n|```$', '', raw_text, flags=re.MULTILINE).strip()


# ==================================================================================
# ⚡ THE FAST BRAIN
# ==================================================================================
def fetch_from_groq(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client: return None
    logger.info("⚡ Routing to Fast Brain (Llama-3.3-70B)")
    try:
        dynamic_prompt = build_fast_brain_prompt(raw_command, context, search_results)
        completion = groq_client.chat.completions.create(
            model=FAST_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": dynamic_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"} 
        )
        return json.loads(clean_json_string(completion.choices[0].message.content.strip()))
    except Exception as e:
        logger.error(f"Fast Brain Error: {e}")
        return None

# ==================================================================================
# 🧠 THE DEEP BRAIN
# ==================================================================================
def fetch_from_oss_120b(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client: return None
    logger.info("🧠 Routing to Deep Brain (GPT-OSS-120B)")
    try:
        dynamic_prompt = build_deep_brain_prompt(raw_command, context, search_results)
        completion = groq_client.chat.completions.create(
            model=DEEP_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": dynamic_prompt}],
            temperature=0.1, 
            response_format={"type": "json_object"} 
        )
        return json.loads(clean_json_string(completion.choices[0].message.content.strip()))
    except Exception as e:
        logger.error(f"Deep Brain Error: {e}")
        return fetch_from_groq(raw_command, context, search_results)


# ==================================================================================
# 🤖 AUTOGPT AGENTIC LOOP
# ==================================================================================
def run_agentic_loop(raw_command: str, context: str) -> Dict[str, any]:
    """The AutoGPT ReAct Loop for complex multi-step tasks."""
    logger.info("🤖 AGENTIC LOOP INITIATED...")
    scratchpad = "No actions taken yet."
    max_steps = 6
    step = 0
    
    try:
        from modules.executor import execute_single_tool_sync
    except ImportError:
        execute_single_tool_sync = None

    while step < max_steps:
        logger.info(f"🔄 Agent Loop Step {step + 1}/{max_steps}")
        current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')
        prompt = f"""[SYSTEM STATUS]\nTime: {current_time}\n[MEMORY & CONTEXT]\n{context}\n[ORIGINAL COMMAND]\n{raw_command}\n[SCRATCHPAD (Previous Steps)]\n{scratchpad}\nBased on the Scratchpad, what is the NEXT logical step? Return JSON."""

        try:
            completion = groq_client.chat.completions.create(
                model=AGENT_MODEL,
                messages=[{"role": "system", "content": AGENT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                temperature=0.1,
                response_format={"type": "json_object"} 
            )
            
            ai_response = json.loads(clean_json_string(completion.choices[0].message.content.strip()))
            logger.info(f"🧠 Agent Thought: {ai_response.get('thought', 'Thinking...')}")
            
            if ai_response.get("is_task_complete"):
                logger.info("✅ Agent declared task complete!")
                final_text = ai_response.pop("response", "Task completed sir.")
                return make_result(final_text, is_agentic=True, **ai_response)
                
            if execute_single_tool_sync:
                observation = execute_single_tool_sync(ai_response)
            else:
                observation = "Observation: Tool executed (Phase 2 pending)."
                logger.warning("Agentic tool execution skipped. Waiting for Phase 2.")
                break 
                
            if scratchpad == "No actions taken yet.": scratchpad = ""
            scratchpad += f"\n- Step {step+1} Action Output: {observation}"
            
        except Exception as e:
            logger.error(f"❌ Agent Loop Error: {e}")
            break
            
        step += 1
        time.sleep(1)
        
    return make_result("Bhai, task thoda complex tha, main loop limit tak pahunch gaya.", priority="high")


# ==================================================================================
# 🚦 UPDATED 3-WAY ROUTER
# ==================================================================================
def fetch_hybrid_response(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if groq_client:
        try:
            router_prompt = f"""You are a high-speed traffic router. Decide the processing path: 'FAST', 'DEEP', or 'AGENTIC'.
[RULES]
'AGENTIC': CRITICAL: If user wants to "check weather", "search web", or "read/analyze" a local Workspace file. Also for conditions (If/Then) or multi-step logic.
'DEEP': Only if the user is asking a deep philosophical question or summarizing massive text already in memory.
'FAST': For EVERYTHING ELSE (open apps, normal chat, play songs, generate image, send direct email/whatsapp without reading files).

User Command: "{raw_command}"
Reply ONLY with 'FAST', 'DEEP', or 'AGENTIC'."""
            
            completion = groq_client.chat.completions.create(
                model=ROUTER_MODEL,
                messages=[{"role": "user", "content": router_prompt}],
                temperature=0.0,
                max_tokens=5
            )
            
            decision = completion.choices[0].message.content.strip().upper()
            logger.info(f"🚦 Router Decision: {decision}")
            
            if "AGENTIC" in decision:
                return run_agentic_loop(raw_command, context)
            elif "DEEP" in decision:
                return fetch_from_oss_120b(raw_command, context, search_results)
                
        except Exception as e:
            logger.error(f"⚠️ Router Error: {e}. Defaulting to Fast Brain.")

    return fetch_from_groq(raw_command, context, search_results)


# ==================================================================================
# 🚀 MAIN PROCESSOR (Original Logic Preserved)
# ==================================================================================
def process_with_cohere(raw_command: str, context: str, search_results: str = "") -> Dict[str, any]:
    cmd_lower = raw_command.lower().strip()
    words = clean_and_split_apps(cmd_lower)

    # Hardcoded Overrides
    if ("time" in cmd_lower or "samay" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("It's %I:%M %p, Sir.")
        speak(msg)
        return make_result(msg)
        
    if ("date" in cmd_lower or "tarikh" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("Today is %A, %d %B %Y.")
        speak(msg)
        return make_result(msg)

    complex_keywords = ["search", "find", "google", "youtube", "play", "generate", "image", "write", "code", "who", "what", "aur", "and", "then", "sath", "email", "mail", "type", "likho", "mute", "volume", "badhao", "kam", "agar", "if", "toh", "read", "padho"]
    is_complex = any(k in cmd_lower for k in complex_keywords) or len(cmd_lower.split()) > 5

    # Simple Open/Close matching
    if not is_complex:
        if re.search(r'\b(open|start|launch|khol|chalao)\b', cmd_lower):
            apps = get_fuzzy_matches(words, ALL_OPEN_OPTIONS)
            if apps:
                msg = f"Opening {apps[0]}."
                speak(msg)
                return make_result(msg, apps_to_open=apps)
        
        if re.search(r'\b(close|stop|exit|band)\b', cmd_lower):
            apps = get_fuzzy_matches(words, ALL_CLOSE_OPTIONS)
            if apps:
                msg = f"Closing {apps[0]}."
                speak(msg)
                return make_result(msg, apps_to_close=apps)

    resolved_command = resolve_pronouns(raw_command)
    
    # 🌟 Hybrid Router Call
    result = fetch_hybrid_response(resolved_command, context, search_results)

    if not result: return make_result("Connection failed, Sir.", priority="low")
    
    # Safely initialize required keys
    required_keys = ["response", "apps_to_open", "apps_to_close", "urls_to_open", "image_command", "search_actions", "youtube_play", "gui_action", "email_action", "workspace_action", "whatsapp_action"]
    for k in required_keys:
        if k not in result: 
            result[k] = "" if k in ["youtube_play"] else ({} if k in ["email_action", "workspace_action", "image_command", "search_actions", "whatsapp_action"] else [])

    if isinstance(result.get("gui_action"), dict): result["gui_action"] = [result["gui_action"]]

    for action in result["gui_action"]:
        if isinstance(action, dict) and action.get("action_type") == "type": action["action_type"] = "typewrite"

    if result["apps_to_open"]:
        false_positives = ["google", "chrome", "browser", "photos", "gallery", "image", "gmail", "mail"]
        result["apps_to_open"] = [app for app in result["apps_to_open"] if app.lower() not in false_positives]

    return result