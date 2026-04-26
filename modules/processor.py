import json
import os
import re
import difflib
import datetime
import time
from typing import Dict, Optional

# --- EXTERNAL LIBS ---
from groq import Groq
from google import genai
from google.genai import types
from dotenv import load_dotenv

# --- INTERNAL MODULES ---
from modules.config import CONFIG
from modules.logger import logger
from modules.utils import clean_and_split_apps, resolve_pronouns
from modules.history import generate_context_summary
from modules.voice.tts import speak
from tools.open_any import APP_PATHS, WEB_URLS
from tools.close_any import APP_PROCESS_NAMES
from modules.executor import execute_single_tool_sync
from modules.workspace import workspace

load_dotenv()

# --- GLOBAL SPEED CACHE & MODELS ---
USER_NAME = os.getenv("USER_NAME", "Bhai")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 2-TIER HYBRID BRAIN SYSTEM
ROUTER_MODEL = "llama-3.1-8b-instant"
FAST_MODEL = "llama-3.3-70b-versatile"
AGENT_MODEL_GEMINI = "gemma-4-31b-it" 

ALL_OPEN_OPTIONS = list(APP_PATHS.keys()) + list(WEB_URLS.keys())
ALL_CLOSE_OPTIONS = list(APP_PROCESS_NAMES.keys())

# --- INIT CLIENTS ---
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# ==================================================================================
# ⚡ MASTER SYSTEM PROMPT (FAST BRAIN) - UPDATED WITH EPHEMERAL CONTEXT
# ==================================================================================
SYSTEM_PROMPT = """
You are Jarvis, an elite, highly responsive AI assistant created by Kaif Ansari (Mindly).
Your tone is sharp, witty, concise, and professional. Always use natural Hinglish in the 'response' field.

### CORE DIRECTIVE
You are the Fast Execution Engine. Your ONLY job is to handle quick reflex actions. 
DO NOT attempt to send emails, whatsapp, or handle complex file operations (read/write/move). 
You may ONLY open files from the user's workspace (Creations/Vault/Temp).

### YOUR CAPABILITIES (JSON MAPPING)
1. **APP CONTROLLER**: `apps_to_open`, `apps_to_close` (Local system apps).
2. **URL OPENER**: `urls_to_open` (Direct HTTP/HTTPS links).
3. **YOUTUBE PLAYER**: `youtube_play` (Direct song or video names).
4. **WORKSPACE FILE OPENER**: `workspace_file_to_open` (Exact filename or fuzzy match, e.g., "report.md", "my_image.png").

### STRICT JSON OUTPUT SCHEMA
Return ONLY raw JSON. No markdown formatting.
{
  "response": "Hinglish conversational reply confirming the action",
  "apps_to_open": [],
  "apps_to_close": [],
  "urls_to_open": [],
  "youtube_play": "",
  "workspace_file_to_open": "",
  "priority": "high"
}
"""

# ==================================================================================
# 🤖 AGENTIC LOOP PROMPT (GEMINI - MASTERMIND WITH ALL TOOLS) - WITH RENAME SUPPORT
# ==================================================================================
AGENT_SYSTEM_PROMPT = """
You are Jarvis, operating in Autonomous Agent Mode. You are a Mastermind AI with strict Goal-Oriented Focus.

### 🎯 GOAL-ORIENTED THINKING (ReAct Framework)
Always start your reasoning by explicitly stating the User's Ultimate Goal. Compare this Goal with the Scratchpad and the COMPLETED ACTIONS list to see what is missing. 
Your `thought` field MUST follow this exact structure (in Hinglish):
"Step 1: Mera ultimate GOAL hai [State Goal]. Step 2: Scratchpad aur Completed Actions ke hisaab se maine [State what is done]. Step 3: Isliye mera NEXT step hai [State Next Action]."

### 🛑 ANTI-DUPLICATION RULE (CRITICAL)
- Before calling any tool, check the [COMPLETED ACTIONS] list below.
- If you have already performed the exact same action (e.g., sent email to Kaif with same attachment, or wrote the same file), DO NOT repeat it.
- If the goal is already achieved based on completed actions, set `is_task_complete: true` immediately.

### 🛠️ STRICT TOOL USAGE GUIDE (CRITICAL) - WITH RENAME
1. **Emailing (`email_action`)**: If you need to attach a file, you MUST put the exact filename inside the `file_path` string (e.g., "report.md"). 
2. **WhatsApp (`whatsapp_action`)**: If you need to attach a file, put the filename inside `file_path` string.
3. **Workspace (`workspace_action`)**: 
   - Use actions: 'read', 'write', 'move', 'list', or 'open'.
   - 'open' will launch the file with its default application (images, PDFs, text files, etc.).
   - Always populate 'file' field with the exact filename.
   - For **rename during move**: use action 'move', provide 'file' (source), 'to' (target folder), and **'dest_name'** (new filename). If dest_name is omitted, filename stays same.
4. **Image Generation/Editing (`image_command`)**: Use 'generate' or 'edit'.

### ⏱️ BUDGET-AWARE PLANNING
- You have a strict limit of {max_steps} Steps. Check the [BUDGET TRACKER].
- If you reach Step {panic_step} or higher (PANIC MODE): Stop gathering new information. Synthesize data, execute final action, and set `is_task_complete: true`.

### 🚫 ANTI-SHORTCUT RULE
NEVER assume an action was successful until you read the "Observation:" in the Scratchpad. Do not repeat failed actions.

### 📋 STRICT JSON SCHEMA (CRITICAL)
Return ONLY raw JSON matching the required Native Schema. DO NOT output free-text markdown outside the JSON.
"""

# ==================================================================================
# PROMPT BUILDERS
# ==================================================================================
def build_fast_brain_prompt(raw_command: str, context: str, search_results: str = "", ephemeral: dict = None) -> str:
    available_apps = ALL_OPEN_OPTIONS
    context_summary = generate_context_summary()
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')
    memory_block = f"\n[USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""
    history_block = f"\n[LAST CONVERSATION]\n{context_summary}\n" if context_summary and context_summary.strip() else "No recent conversation."
    
    # Inject ephemeral data (last links, files from agent)
    ephemeral_block = ""
    if ephemeral:
        ephemeral_block = f"\n[RECENT AGENT OUTPUT (USE THESE FOR OPENING LINKS/FILES)]\n"
        if ephemeral.get("last_found_links"):
            ephemeral_block += f"Links found earlier: {', '.join(ephemeral['last_found_links'])}\n"
        if ephemeral.get("last_generated_image"):
            ephemeral_block += f"Last generated image: {ephemeral['last_generated_image']}\n"
        if ephemeral.get("last_accessed_file"):
            ephemeral_block += f"Last file accessed: {ephemeral['last_accessed_file']}\n"
    
    return f"""[SYSTEM STATUS]\nTime: {current_time}\n[AVAILABLE APPS]\n{", ".join(available_apps[:50])}...\n{history_block}{memory_block}{ephemeral_block}\n[USER COMMAND]\n"{raw_command}"\nReturn STRICT JSON."""

def make_result(response, **kwargs):
    base = {
        "response": response, "apps_to_open": [], "apps_to_close": [], "urls_to_open": [],
        "image_command": {}, "search_actions": {}, "youtube_play": "", "gui_action": [],
        "email_action": {}, "workspace_action": {}, "whatsapp_action": {}, "priority": "high",
        "workspace_file_to_open": ""
    }
    base.update(kwargs)
    return base

def clean_json_string(raw_text: str) -> str:
    json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
    if json_match: return json_match.group(1).strip()
    return re.sub(r'^```json\n|```$', '', raw_text, flags=re.MULTILINE).strip()

# ==================================================================================
# FAST BRAIN (Groq) with Ephemeral Context
# ==================================================================================
def fetch_from_groq(raw_command: str, context: str, search_results: str = "", ephemeral: dict = None) -> Optional[Dict[str, any]]:
    if not groq_client: return None
    logger.info("⚡ Routing to Fast Brain (Groq Llama-3.3-70B)")
    try:
        dynamic_prompt = build_fast_brain_prompt(raw_command, context, search_results, ephemeral)
        completion = groq_client.chat.completions.create(
            model=FAST_MODEL,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": dynamic_prompt}],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        result = json.loads(clean_json_string(completion.choices[0].message.content.strip()))
        if "workspace_file_to_open" not in result:
            result["workspace_file_to_open"] = ""
        return result
    except Exception as e:
        logger.error(f"Fast Brain Error: {e}")
        return None

# ==================================================================================
# AGENTIC LOOP (Google Gemini with DEEP NATIVE SCHEMA) - WITH dest_name SUPPORT
# ==================================================================================
def summarize_scratchpad(scratchpad: str) -> str:
    if len(scratchpad) <= CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000): return scratchpad
    logger.info("🗜️ Summarizing agent scratchpad...")
    try:
        summary_prompt = f"Summarize these agent observations into bullet points, preserving ALL factual data:\n{scratchpad}"
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.2,
            max_tokens=500
        )
        return f"[Previous steps summary]:\n{completion.choices[0].message.content.strip()}"
    except:
        return scratchpad[-CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000):]

def run_agentic_loop(raw_command: str, context: str, memory_instance=None) -> Dict[str, any]:
    logger.info(f"🤖 AGENTIC LOOP INITIATED (Gemini {AGENT_MODEL_GEMINI} - DEEP SCHEMA MODE)...")
    scratchpad = ""
    max_steps = CONFIG.get("AGENT_MAX_STEPS", 10)  # Use config value
    timeout_seconds = CONFIG.get("AGENT_TIMEOUT", 120)
    retry_limit = CONFIG.get("AGENT_RETRY_LIMIT", 2)
    step = 0
    start_time = time.time()
    
    # Completed actions tracker to prevent duplicates
    completed_actions = set()
    
    # Ephemeral storage for links, files, etc.
    if memory_instance and not hasattr(memory_instance, 'ephemeral'):
        memory_instance.ephemeral = {}
    ephemeral = memory_instance.ephemeral if memory_instance else {}

    # --- 🛡️ TOOL CONTRACT (UPDATED with dest_name) ---
    agent_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "thought": types.Schema(type=types.Type.STRING, description="Step 1: Goal. Step 2: Scratchpad. Step 3: Next action."),
            "is_task_complete": types.Schema(type=types.Type.BOOLEAN, description="True ONLY if the ultimate goal is fully achieved."),
            "response": types.Schema(type=types.Type.STRING, description="Final natural response to speak to the user. (Only if is_task_complete is true)"),
            
            "search_actions": types.Schema(type=types.Type.OBJECT, properties={
                "web": types.Schema(type=types.Type.STRING, description="Search query string.")
            }),
            
            "workspace_action": types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "action": types.Schema(type=types.Type.STRING, description="Must be exactly: 'read', 'write', 'move', 'list', or 'open'"),
                    "file": types.Schema(type=types.Type.STRING, description="Exact filename with extension (e.g., 'report.md')"),
                    "content": types.Schema(type=types.Type.STRING, description="Full file content if action is 'write'"),
                    "to": types.Schema(type=types.Type.STRING, description="Target folder name if action is 'move' (e.g., 'Vault')"),
                    "dest_name": types.Schema(type=types.Type.STRING, description="OPTIONAL: New filename when moving (rename). Only used for 'move' action.")
                }
            ),
            
            "email_action": types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "action_type": types.Schema(type=types.Type.STRING, description="Must be 'send'"),
                    "params": types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "to": types.Schema(type=types.Type.STRING, description="Recipient name or email"),
                            "subject": types.Schema(type=types.Type.STRING),
                            "body": types.Schema(type=types.Type.STRING),
                            "file_path": types.Schema(type=types.Type.STRING, description="MANDATORY IF ATTACHING: Exact filename")
                        },
                        required=["to", "subject", "body"]
                    )
                }
            ),
            
            "whatsapp_action": types.Schema(
                type=types.Type.OBJECT, 
                properties={
                    "to": types.Schema(type=types.Type.STRING, description="Contact name"),
                    "message": types.Schema(type=types.Type.STRING, description="Text message to send"),
                    "file_path": types.Schema(type=types.Type.STRING, description="OPTIONAL: Exact filename to attach.")
                }
            ),
            
            "image_command": types.Schema(type=types.Type.OBJECT, properties={
                "action": types.Schema(type=types.Type.STRING, description="Must be 'generate' or 'edit'"),
                "prompt": types.Schema(type=types.Type.STRING),
                "filename": types.Schema(type=types.Type.STRING),
                "target_file": types.Schema(type=types.Type.STRING, description="For edit, original filename")
            }),

            "apps_to_open": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
            "apps_to_close": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
            "urls_to_open": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
            "youtube_play": types.Schema(type=types.Type.STRING)
        },
        required=["thought", "is_task_complete"]
    )

    while step < max_steps:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.warning(f"⏰ Agent loop timeout after {elapsed:.1f} seconds")
            return make_result("Bhai, task thoda zyada time le raha tha, timeout ho gaya. Aap phir se try karo ya simple command do.", priority="high", agent_executed=True)

        logger.info(f"🔄 Agent Loop Step {step + 1}/{max_steps}")
        current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

        if scratchpad and len(scratchpad) > CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000):
            scratchpad = summarize_scratchpad(scratchpad)

        panic_warning = f"⚠️ WARNING: You are running out of steps! Execute final action NOW." if step + 1 >= max_steps - 1 else ""
        
        completed_list = "\n".join([f"- {act}" for act in completed_actions]) if completed_actions else "None yet."
        
        ephemeral_prompt = ""
        if ephemeral.get("last_found_links"):
            ephemeral_prompt += f"\n[EPHEMERAL: Last found links = {ephemeral['last_found_links']}]"
        if ephemeral.get("last_generated_image"):
            ephemeral_prompt += f"\n[EPHEMERAL: Last generated image = {ephemeral['last_generated_image']}]"

        prompt = f"""[SYSTEM STATUS]
Time: {current_time}
[BUDGET TRACKER]
Current Step: {step + 1} out of {max_steps}. {panic_warning}

[COMPLETED ACTIONS (DO NOT REPEAT)]
{completed_list}

[MEMORY & CONTEXT]
{context if step == 0 else "[Context loaded in Step 1. Focus on Goal and Scratchpad.]"}

[ORIGINAL COMMAND]
{raw_command}

[SCRATCHPAD]
{scratchpad if scratchpad else "No actions taken yet."}

{ephemeral_prompt}

Based on the Scratchpad and Completed Actions, select the NEXT tool in the Native JSON Schema. If goal achieved, set is_task_complete=true.
"""

        try:
            ai_response = None
            if gemini_client:
                panic_step = max_steps - 2
                full_prompt = AGENT_SYSTEM_PROMPT.format(max_steps=max_steps, panic_step=panic_step) + "\n\n" + prompt
                response = gemini_client.models.generate_content(
                    model=AGENT_MODEL_GEMINI,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                        response_schema=agent_schema
                    )
                )
                ai_response = json.loads(clean_json_string(response.text))
            else:
                # Fallback to Groq
                panic_step = max_steps - 2
                full_prompt = AGENT_SYSTEM_PROMPT.format(max_steps=max_steps, panic_step=panic_step)
                completion = groq_client.chat.completions.create(
                    model=FAST_MODEL,
                    messages=[{"role": "system", "content": full_prompt}, {"role": "user", "content": prompt}],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                ai_response = json.loads(clean_json_string(completion.choices[0].message.content.strip()))
            
            logger.info(f"🧠 Agent Thought: {ai_response.get('thought', 'Thinking...')}")

            if ai_response.get("is_task_complete"):
                logger.info("✅ Agent declared task complete!")
                final_text = ai_response.pop("response", "Task completed sir.")
                if ai_response.get("urls_to_open"):
                    ephemeral["last_found_links"] = ai_response["urls_to_open"]
                if ai_response.get("image_command", {}).get("filename"):
                    ephemeral["last_generated_image"] = ai_response["image_command"]["filename"]
                return make_result(final_text, is_agentic=True, agent_executed=True, **ai_response)

            observation = None
            for attempt in range(retry_limit):
                try:
                    observation = execute_single_tool_sync(ai_response)
                    if observation:
                        if "http" in observation and "link" in observation.lower():
                            urls = re.findall(r'https?://[^\s]+', observation)
                            if urls:
                                ephemeral["last_found_links"] = urls[:3]
                        if "file" in observation.lower() and (".png" in observation or ".md" in observation):
                            file_match = re.search(r'([\w\-]+\.(png|md|txt|jpg))', observation)
                            if file_match:
                                ephemeral["last_accessed_file"] = file_match.group(1)
                    
                    obs_prefix = str(observation).lower()[:50]
                    if observation and ("error" not in obs_prefix and "❌" not in obs_prefix and "failed" not in obs_prefix):
                        action_fingerprint = f"{list(ai_response.keys())[0]}:{str(ai_response.get(list(ai_response.keys())[0]))[:100]}"
                        completed_actions.add(action_fingerprint)
                        break
                    elif attempt < retry_limit - 1:
                        logger.warning(f"⚠️ Tool attempt {attempt+1} failed: {observation}. Retrying in 2s...")
                        time.sleep(2)
                except Exception as tool_err:
                    observation = f"Observation: Tool execution error - {tool_err}"
                    if attempt < retry_limit - 1: time.sleep(2)
            else:
                observation = f"Observation: Tool failed after {retry_limit} retries. Try a different approach."

            scratchpad += f"\n- Step {step+1}: {observation}"
            step += 1
            time.sleep(1)

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "quota" in error_msg.lower():
                logger.error("❌ Gemini API Rate Limit (429) Hit!")
                return make_result("Bhai, Google Gemini ki free API speed limit khatam ho gayi hai. 60 seconds ruko aur phir try karo.", priority="high", agent_executed=True)
            
            logger.error(f"❌ Agent Loop Error (API/Crash): {e}")
            time.sleep(3)
            scratchpad += f"\n- System Error on Step {step+1}: {e}. Skipping this tool."
            step += 1

    return make_result(f"Bhai, maine maximum steps ({max_steps}) le liye hain. Task loop limit tak pahunch gaya hai. Kripya simple command do.", priority="high", agent_executed=True)

# ==================================================================================
# 🚦 PURE AI ROUTER (ULTRA-SMART 2-TIER ROUTING)
# ==================================================================================
def fetch_hybrid_response(raw_command: str, context: str, search_results: str = "", memory_instance=None) -> Optional[Dict[str, any]]:
    if not groq_client: return None
    try:
        router_prompt = f"""You are Jarvis's core Intent Router.
Your job is to logically classify the user's command into exactly ONE of two categories: 'FAST' or 'AGENTIC'.

[CLASSIFICATION RULES]

1. 'FAST' (For Instant Reflexes & Chat ONLY)
   - ALWAYS use for opening/closing apps, URLs, or playing YouTube videos.
   - ALWAYS use for general chat, jokes, or direct factual questions.
   - ALWAYS use for opening a file from workspace (e.g., "khol report.md" or "open my image").
   - ALWAYS use if the command is just to open links that were already provided in previous conversation.

2. 'AGENTIC' (For All Advanced Tools & Multi-step Tasks)
   - ALWAYS use if the command mentions SENDING Email or WhatsApp.
   - ALWAYS use if the user wants to search the internet.
   - ALWAYS use for ANY file operations other than simple open (creating, writing, reading, moving, or viewing file contents).
   - ALWAYS use for creating/generating images.

[CRITICAL OVERRIDES - DO NOT FAIL THESE]
- Email, WhatsApp, File write/read/move, Search -> Route to 'AGENTIC'.
- App opening/closing, YouTube, or just opening a workspace file -> Route to 'FAST'.

[DATA]
User Command: "{raw_command}"

Reply strictly with ONLY ONE WORD: 'FAST' or 'AGENTIC'."""

        completion = groq_client.chat.completions.create(
            model=ROUTER_MODEL,
            messages=[{"role": "user", "content": router_prompt}],
            temperature=0.0,
            max_tokens=5
        )
        
        decision = completion.choices[0].message.content.strip().upper()
        
        if "AGENTIC" in decision:
            logger.info("🚦 Smart Router: AGENTIC (Deep Tasks & Comms)")
            return run_agentic_loop(raw_command, context, memory_instance)
        else:
            logger.info("🚦 Smart Router: FAST (Direct Apps / Quick Chat / File Open)")
            ephemeral = memory_instance.ephemeral if memory_instance else None
            return fetch_from_groq(raw_command, context, search_results, ephemeral)
            
    except Exception as e:
        logger.error(f"⚠️ Smart Router Error: {e}. Defaulting to Fast Brain.")
        return fetch_from_groq(raw_command, context, search_results)

# ==================================================================================
# MAIN PROCESSOR
# ==================================================================================
def process_with_cohere(raw_command: str, context: str, search_results: str = "", memory_instance=None) -> Dict[str, any]:
    cmd_lower = raw_command.lower().strip()

    if ("time" in cmd_lower or "samay" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("It's %I:%M %p, Sir.")
        speak(msg)
        return make_result(msg)
    if ("date" in cmd_lower or "tarikh" in cmd_lower) and "what" in cmd_lower:
        msg = datetime.datetime.now().strftime("Today is %A, %d %B %Y.")
        speak(msg)
        return make_result(msg)

    resolved_command = resolve_pronouns(raw_command)
    result = fetch_hybrid_response(resolved_command, context, search_results, memory_instance)

    if not result: return make_result("Connection failed, Sir.", priority="low")

    required_keys = ["response", "apps_to_open", "apps_to_close", "urls_to_open", "image_command",
                     "search_actions", "youtube_play", "gui_action", "email_action", "workspace_action",
                     "whatsapp_action", "workspace_file_to_open"]
    for k in required_keys:
        if k not in result:
            if k in ["email_action", "workspace_action", "image_command", "search_actions", "whatsapp_action"]:
                result[k] = {}
            elif k == "workspace_file_to_open":
                result[k] = ""
            elif k == "youtube_play":
                result[k] = ""
            else:
                result[k] = []

    if isinstance(result.get("gui_action"), dict):
        result["gui_action"] = [result["gui_action"]]
    for action in result["gui_action"]:
        if isinstance(action, dict) and action.get("action_type") == "type":
            action["action_type"] = "typewrite"

    if result["apps_to_open"]:
        false_positives = ["google", "chrome", "browser", "photos", "gallery", "image", "gmail", "mail"]
        result["apps_to_open"] = [app for app in result["apps_to_open"] if app.lower() not in false_positives]

    return result