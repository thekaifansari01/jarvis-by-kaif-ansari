import json
import os
import re
import difflib
import datetime
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

# --- 🚀 GLOBAL SPEED CACHE ---
USER_NAME = os.getenv("USER_NAME", "Bhai")
GROQ_API_KEY = os.getenv("GROQ_API_KEY") 

ALL_OPEN_OPTIONS = list(APP_PATHS.keys()) + list(WEB_URLS.keys())
ALL_CLOSE_OPTIONS = list(APP_PROCESS_NAMES.keys())

# Init AI Client
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==================================================================================
# ✅ MASTER SYSTEM PROMPT (UPDATED WITH STRICT EMAIL/WA ATTACHMENT & HYBRID RULES)
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

### 🧠 AUTONOMY & CONDITIONAL LOGIC (YOUR BRAIN)
1. Determine the TRUE INTENT and decide WHICH TOOL to use. 
2. **PROMPT ENHANCEMENT:** When asked to generate/edit images, act as a Prompt Engineer. Enhance simple words into highly detailed, cinematic English prompts.
3. **CONDITIONAL TASKS (IF/THEN):** Pass 1 -> Fetch Data. Pass 2 -> Evaluate & Execute.

### 🛠️ YOUR TOOLKIT & MANUAL

#### 1. TOOL: APP CONTROLLER (`apps_to_open`, `apps_to_close`)
- **Purpose:** Open/close local software or websites.
- **Rule:** Use this to open basic apps. DO NOT use this for web searching or playing videos.

#### 2. TOOL: AGENTIC SEARCH HUB (`search_actions`)
- **Purpose:** Find live data. Keys: "web", "reddit", "arxiv", "weather".
- **Rule:** Do NOT guess live data. Leave empty if not needed.

#### 3. TOOL: BACKGROUND EMAIL SENDER (`email_action`)
- **Purpose:** Send or delete emails silently. Automatically attach workspace files if requested.
- **Format:** `{"action_type": "send", "params": {"to": "contact_name", "subject": "Sub", "body": "Message", "file_path": "Creations/image.png"}}`
- **Rule:** `file_path` is OPTIONAL. Use it only when the user explicitly asks to attach/send a file via email.

#### 4. TOOL: GUI & KEYBOARD CONTROLLER (`gui_action`)
- **Purpose:** Type text, press system keys (mute, volume), click, scroll.
- **CRITICAL:** NEVER output this unless EXPLICITLY told to "Type this" or control the UI.

#### 5. TOOL: HYBRID IMAGE GENERATOR & EDITOR (`image_command`)
- **Actions:** - `"action": "generate"`: Detailed English `"prompt"` and a `"filename"`.
  - `"action": "edit"`: New `"prompt"`, old `"target_file"`, and new `"filename"`.

#### 6. TOOL: YOUTUBE PLAYER (`Youtube`)
- **Purpose:** Play songs/videos on YouTube. Put the search query here directly.

#### 7. TOOL: WORKSPACE MANAGER (`workspace_action`)
- **Purpose:** Open, delete, move, or READ TEXT files inside the local Workspace.
- **Actions:** "open", "delete", "move", "read".
- **Rule:** NEVER try to "read" image files (.png, .jpg). ONLY read text/code files.

#### 8. TOOL: WHATSAPP & ATTACHMENT SENDER (`whatsapp_action`)
- **Purpose:** Send WhatsApp messages and automatically attach files.
- **Format:** `{"to": "contact_name", "message": "Text body", "file_path": "Creations/filename.png"}`

---

### 🚨 THE 2-PASS RULE & ATTACHMENT EXCEPTION (CRITICAL FOR AVOIDING LOOPS)

**SCENARIO A: The User wants to KNOW/READ something (Needs Fetching)**
If the user says: "Check weather and email Kaif" OR "Read report.txt and summarize":
- **PASS 1 (Fetching):** Output ONLY `search_actions` or `workspace_action` (read). Leave all other actions completely empty.
- **PASS 2 (Execution):** You receive the data. Now output the final `email_action` or `response`.

**SCENARIO B: The User wants to SEND/ATTACH a file (DIRECT ACTION - NO FETCHING)**
If the user says: "Send this image to Kaif on WhatsApp" OR "Email golden_lambo.png to Kaif":
- **DO NOT USE** `workspace_action` to "read" the file. You cannot read images. 
- **DIRECT EXECUTION:** Immediately populate the `whatsapp_action` or `email_action` with the exact `file_path`. Leave `workspace_action` EMPTY. 

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

# ✅ PROMPT BUILDERS
# ==================================================================================

def build_fast_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    """Builder for Fast Brain (Llama 3.3)."""
    available_apps = ALL_OPEN_OPTIONS 
    context_summary = generate_context_summary()
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

    memory_block = f"\n[🧠 USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""
    search_block = f"\n[🌐 WEB SEARCH / FILE FINDINGS]\n{search_results}\n" if search_results and search_results.strip() else ""
    history_block = f"\n[🕒 LAST CONVERSATION]\n{context_summary}\n" if context_summary and context_summary.strip() else "No recent conversation."

    return f"""[SYSTEM STATUS]
Time: {current_time}
[AVAILABLE TOOLS & APPS]
You can ONLY open these explicitly requested apps: {", ".join(available_apps[:50])}...

{history_block}{memory_block}{search_block}
[🗣️ USER COMMAND]
"{raw_command}"

[ACTION REQUIRED]
Execute logic and return STRICT JSON. Follow the 2-Pass rule.
"""

def build_deep_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    """Builder for Deep Brain (GPT-OSS-120B). Handles Pass 1 (Fetch) and Pass 2 (Action/Conditions)."""
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

    memory_block = f"\n[🧠 USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""
    search_block = f"\n[🌐 WEB SEARCH / FILE FINDINGS]\n{search_results}\n" if search_results and search_results.strip() else ""

    if search_results:
        # 🟢 PASS 2: Data Mil Chuka Hai. Universal Conditional Logic!
        action_rules = """[ACTION REQUIRED - PASS 2 COMPLETION]
You have received the data. Now fulfill the COMPLETE original request based on your intelligence.
CRITICAL JSON RULES:
1. "response": Give the final answer in Hinglish. Clearly state whether the user's condition (if any) was met or not.
2. CONDITIONAL EXECUTION: Analyze the fetched data against the user's original command. If their condition is MET, you MUST generate the corresponding action JSON (email_action, workspace_action, gui_action, etc.) NOW. If the condition is NOT MET, keep the action JSON empty.
3. Do NOT skip pending actions just because you are in Pass 2.
4. "search_actions": MUST BE EMPTY."""
    else:
        # 🔴 PASS 1: Data nikalna hai
        action_rules = """[ACTION REQUIRED - PASS 1 FETCHING]
You need to fetch data (Weather/Search/File) before deciding the next step.
CRITICAL JSON RULES:
1. Fill ONLY "search_actions" or "workspace_action" (read).
2. "response": "Bhai, main check kar raha hu..."
3. Keep ALL other action fields (email, gui, apps, whatsapp) COMPLETELY EMPTY."""

    return f"""[SYSTEM STATUS]
Time: {current_time}
{memory_block}{search_block}

[🗣️ ORIGINAL USER COMMAND]
"{raw_command}"

{action_rules}
Output ONLY valid JSON matching the schema.
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


# --- ⚡ THE FAST BRAIN (GROQ Llama-3.3-70B) ---
def fetch_from_groq(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client: return None
    logger.info("⚡ Routing to Fast Brain (Llama-3.3-70B)")
    try:
        dynamic_prompt = build_fast_brain_prompt(raw_command, context, search_results)
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": dynamic_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"} 
        )
        return json.loads(clean_json_string(completion.choices[0].message.content.strip()))
    except Exception as e:
        logger.error(f"Fast Brain Error: {e}")
        return None

# --- 🧠 THE DEEP BRAIN (GROQ GPT-OSS-120B) ---
def fetch_from_oss_120b(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    """Handles complex reasoning, RAG analysis, and conditional execution using the 120B model."""
    if not groq_client: return None
    logger.info("🧠 Routing to Deep Brain (GPT-OSS-120B)")
    try:
        dynamic_prompt = build_deep_brain_prompt(raw_command, context, search_results)
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": dynamic_prompt}],
            temperature=0.1, 
            response_format={"type": "json_object"} 
        )
        return json.loads(clean_json_string(completion.choices[0].message.content.strip()))
    except Exception as e:
        logger.error(f"Deep Brain (120B) Error: {e}. Falling back to Fast Brain.")
        return fetch_from_groq(raw_command, context, search_results)


# --- 🚦 THE MICRO-AGENT ROUTER (NEW Llama-3-8B Logic) ---
def fetch_hybrid_response(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    """Intelligently routes commands using an ultra-fast Micro-Agent (Llama-3-8B)."""
    
    # 1. Guaranteed Deep Brain Pass: If we have search results (Pass 2) or huge context, skip routing.
    if search_results or len(context) > 1500:
        return fetch_from_oss_120b(raw_command, context, search_results)
    
    # 2. The Smart Traffic Cop: Let 8B decide in ~0.1s
    if groq_client:
        try:
            # 🚀 STRICT WORKSPACE-ONLY PROMPT
            router_prompt = f"""You are a high-speed traffic router for an AI assistant.
Analyze the user's command and decide the processing path: 'FAST' or 'DEEP'.

[STRICT RULES]
Output 'DEEP' ONLY IF the user explicitly wants to read, write, move, or analyze a local file or folder (Workspace, Vault, Creations, Temp).
Output 'FAST' FOR EVERYTHING ELSE (normal chat, web search, emails, whatsapp, youtube, apps, images, multi-step logic, etc.).

[EXAMPLES]
User: "Vault se report.pdf read karo." -> DEEP
User: "Ye text copy karke nayi file bana do." -> DEEP
User: "Search weather and if it's raining email Saad." -> FAST
User: "Open youtube and play arijit singh." -> FAST
User: "Ek car ki image generate karo." -> FAST

[CURRENT COMMAND]
User: "{raw_command}"

Reply ONLY with the exact word 'FAST' or 'DEEP'."""
            
            completion = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant", # Ultra-fast 8B model for routing
                messages=[{"role": "user", "content": router_prompt}],
                temperature=0.0,
                max_tokens=5 # ⚡ Super tight token limit for max speed
            )
            
            decision = completion.choices[0].message.content.strip().upper()
            logger.info(f"🚦 Router Decision: {decision}")
            
            if "DEEP" in decision:
                return fetch_from_oss_120b(raw_command, context, search_results)
                
        except Exception as e:
            logger.error(f"⚠️ Micro-Agent Router Error: {e}. Defaulting to Fast Brain.")

    # 3. Default to Fast Brain (For images, simple tasks, or if router fails)
    return fetch_from_groq(raw_command, context, search_results)


# ==================================================================================
# 🚀 MAIN PROCESSOR
# ==================================================================================

def process_with_cohere(raw_command: str, context: str, search_results: str = "") -> Dict[str, any]:
    """Core Entry Point for Jarvis Logic."""
    cmd_lower = raw_command.lower().strip()
    words = clean_and_split_apps(cmd_lower)

    if ("time" in cmd_lower or "samay" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("It's %I:%M %p, Sir.")
        speak(msg)
        return make_result(msg)
        
    if ("date" in cmd_lower or "tarikh" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("Today is %A, %d %B %Y.")
        speak(msg)
        return make_result(msg)

    # Note: complex_keywords are now primarily handled by the Micro-Agent, 
    # but we keep this list to bypass basic system app opening if the query is long.
    complex_keywords = ["search", "find", "google", "youtube", "play", "generate", "image", "write", "code", "who", "what", "aur", "and", "then", "sath", "email", "mail", "type", "likho", "mute", "volume", "badhao", "kam", "agar", "if", "toh"]
    is_complex = any(k in cmd_lower for k in complex_keywords) or len(cmd_lower.split()) > 5

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