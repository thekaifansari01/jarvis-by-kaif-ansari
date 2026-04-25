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
from modules.executor import execute_single_tool_sync
from modules.workspace import workspace

load_dotenv()

# --- GLOBAL SPEED CACHE & MODELS ---
USER_NAME = os.getenv("USER_NAME", "Bhai")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# 3-TIER BRAIN SYSTEM
ROUTER_MODEL = "llama-3.1-8b-instant"
FAST_MODEL = "llama-3.3-70b-versatile"
AGENT_MODEL = "llama-3.3-70b-versatile"  # Tool Loop ke liye 70B (Rate Limits bachane ke liye)
DEEP_MODEL = "openai/gpt-oss-120b"       # Direct complex queries ke liye 120B

ALL_OPEN_OPTIONS = list(APP_PATHS.keys()) + list(WEB_URLS.keys())
ALL_CLOSE_OPTIONS = list(APP_PROCESS_NAMES.keys())

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ==================================================================================
# ⚡ MASTER SYSTEM PROMPT (FAST BRAIN) - ULTRA-SHARP & ACTION FOCUSED
# ==================================================================================
SYSTEM_PROMPT = """
You are Jarvis, an elite, highly responsive AI assistant created by Kaif Ansari (Mindly).
Your tone is sharp, witty, concise, and professional. Always use natural Hinglish in the 'response' field.

### CORE DIRECTIVE
You are the Fast Execution Engine. Your absolute priority is to instantly map the user's intent to the exact JSON tool parameters.
Address the user as "Kaif bhai" or their preferred name. Adapt your tone to their mood.

### YOUR CAPABILITIES (JSON MAPPING)
1. **APP CONTROLLER**: `apps_to_open`, `apps_to_close` (Local system apps).
2. **URL OPENER**: `urls_to_open` (Direct HTTP/HTTPS links).
3. **YOUTUBE PLAYER**: `Youtube` (Direct song or video names).
4. **IMAGE GENERATOR**: `image_command` -> `{"action":"generate","prompt":"...","filename":"..."}`
5. **DIRECT MESSAGING**: `whatsapp_action` -> `{"to":"name", "message":"..."}` | `email_action` -> `{"action_type":"send","params":{"to":"name","subject":"...","body":"..."}}`
6. **WORKSPACE CONTROLLER**: `workspace_action` -> `{"action":"open", "file":"filename.ext"}` OR `{"action":"list"}` (For opening files on screen or checking existing files).

### STRICT JSON OUTPUT SCHEMA
Return ONLY raw JSON. No markdown formatting. No conversational filler outside the JSON.
{
  "response": "Hinglish conversational reply confirming the action",
  "apps_to_open": [],
  "apps_to_close": [],
  "urls_to_open": [],
  "youtube_play": "",
  "image_command": {},
  "email_action": {},
  "whatsapp_action": {},
  "workspace_action": {},
  "priority": "high"
}
"""

# ==================================================================================
# 🤖 AGENTIC LOOP PROMPT (GOAL-ORIENTED, MULTI-PERSONA & BUDGET AWARE)
# ==================================================================================
AGENT_SYSTEM_PROMPT = """
You are Jarvis, operating in Autonomous Agent Mode. You are a Mastermind AI with Dynamic Personas and strict Goal-Oriented Focus.

### 🎯 GOAL-ORIENTED THINKING (ReAct Framework)
Always start your reasoning by explicitly stating the User's Ultimate Goal. Compare this Goal with the Scratchpad to see what is missing. 
Your `thought` field MUST follow this exact structure (in Hinglish):
"Step 1: Mera ultimate GOAL hai [State Goal]. Step 2: Scratchpad ke hisaab se maine [State what is done]. Step 3: Isliye mera NEXT step hai [State Next Action]."

### 🎭 MULTI-PERSONA FRAMEWORK (Adapt dynamically based on the current action)
1. 🕵️‍♂️ THE RESEARCHER (When using Search): Focus on 100% coverage. Gather deep, factual data from multiple sources if needed.
2. ✍️ THE WRITER (When Writing/Creating Files): Write the COMPLETE detailed document in a SINGLE step. DO NOT repeatedly rewrite or update the same file. Documents MUST be detailed (300+ words), use proper Markdown (`# Headings`, `**Bold**`, Bullet points). Once the file is written successfully, move on to the next task (like moving it) or complete the goal.
3. 👨‍💻 THE CODER/ANALYST (When solving math/code): Focus on Accuracy. Provide clean, bug-free logic without fluff.
4. 🗣️ THE COMMUNICATOR (When completing the task): Keep the `response` field crisp, professional, and in natural Hinglish.

### ⏱️ BUDGET-AWARE PLANNING & PANIC MODE
- You have a strict limit of 10 Steps per task. Look at the [BUDGET TRACKER] in your prompt.
- If you reach Step 8 or 9 (PANIC MODE): Stop gathering new information immediately. Synthesize whatever data you currently have, execute your final action (write file or formulate answer), and set `is_task_complete: true`. Do not leave the task hanging.

### 🚫 ANTI-SHORTCUT RULE
NEVER assume an action was successful until you read the "Observation:" in the Scratchpad. Do not repeat failed actions blindly.

### 🛠️ YOUR TOOLKIT
1. **SEARCH HUB** (`search_actions`): `{"web":"query"}`, `{"weather":"city"}`, `{"reddit":"query"}`, `{"arxiv":"query"}`
2. **WORKSPACE MANAGER** (`workspace_action`):
   - Write: `{"action":"write", "file":"name.txt", "content":"Full detailed report/data here"}`
   - Read: `{"action":"read", "file":"name"}`
   - Organize/View: `{"action":"move", "file":"...", "to":"Vault"}`, `{"action":"open", "file":"..."}`, `{"action":"list"}`
3. **SMART MESSAGING**: `email_action` & `whatsapp_action`
4. **GUI AUTOMATION**: `gui_action`

### 📋 STRICT JSON SCHEMA
Return ONLY raw JSON. No markdown formatting outside the content fields.
{
  "thought": "Step 1: Goal... Step 2: Scratchpad... Step 3: Next action... (in Hinglish)",
  "is_task_complete": false,
  "response": "Final comprehensive answer in Hinglish (ONLY populate this if is_task_complete is true)",
  "search_actions": {},
  "workspace_action": {},
  "email_action": {},
  "whatsapp_action": {},
  "gui_action": [],
  "apps_to_open": [],
  "apps_to_close": [],
  "urls_to_open": [],
  "youtube_play": "",
  "image_command": {}
}
"""

# ==================================================================================
# PROMPT BUILDERS
# ==================================================================================
def build_fast_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    available_apps = ALL_OPEN_OPTIONS
    context_summary = generate_context_summary()
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

    memory_block = f"\n[USER CONTEXT / MEMORY / FILES]\n{context}\n" if context and context.strip() else ""
    history_block = f"\n[LAST CONVERSATION]\n{context_summary}\n" if context_summary and context_summary.strip() else "No recent conversation."

    return f"""[SYSTEM STATUS]
Time: {current_time}
[AVAILABLE APPS]
{", ".join(available_apps[:50])}...

{history_block}{memory_block}
[USER COMMAND]
"{raw_command}"

Return STRICT JSON.
"""

def build_deep_brain_prompt(raw_command: str, context: str, search_results: str = "") -> str:
    current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')
    memory_block = f"\n[USER CONTEXT]\n{context}\n" if context and context.strip() else ""
    return f"""[SYSTEM STATUS]
Time: {current_time}
{memory_block}
[USER COMMAND]
"{raw_command}"
Return STRICT JSON.
"""

def make_result(response, **kwargs):
    base = {
        "response": response,
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
    base.update(kwargs)
    return base

def get_fuzzy_matches(words: list, options: list, cutoff=0.85) -> list:
    matches = set()
    full_cmd = " ".join(words).lower()
    for option in options:
        opt_lower = option.lower()
        if opt_lower in words or (opt_lower in full_cmd and len(opt_lower) > 4):
            matches.add(option)
    if not matches:
        for word in words:
            if len(word) > 3:
                close = difflib.get_close_matches(word, options, n=1, cutoff=cutoff)
                if close:
                    matches.add(close[0])
    return list(matches)

def clean_json_string(raw_text: str) -> str:
    json_match = re.search(r'(\{.*\})', raw_text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()
    return re.sub(r'^```json\n|```$', '', raw_text, flags=re.MULTILINE).strip()

# ==================================================================================
# FAST BRAIN (Groq)
# ==================================================================================
def fetch_from_groq(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client:
        return None
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
# DEEP BRAIN (120B)
# ==================================================================================
def fetch_from_oss_120b(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client:
        return None
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
# AGENTIC LOOP (OPTIMIZED)
# ==================================================================================
def summarize_scratchpad(scratchpad: str) -> str:
    if len(scratchpad) <= CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000):
        return scratchpad
    logger.info("🗜️ Summarizing agent scratchpad...")
    try:
        summary_prompt = f"Summarize these agent observations into bullet points, preserving ALL factual data:\n{scratchpad}"
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": summary_prompt}],
            temperature=0.2,
            max_tokens=500
        )
        summary = completion.choices[0].message.content.strip()
        return f"[Previous steps summary]:\n{summary}"
    except Exception as e:
        logger.warning(f"Scratchpad summarization failed: {e}")
        return scratchpad[-CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000):]

def run_agentic_loop(raw_command: str, context: str) -> Dict[str, any]:
    logger.info("🤖 AGENTIC LOOP INITIATED (Multi-Persona & Budget Aware)...")
    scratchpad = ""
    max_steps = 10  # 🚀 UPGRADED TO 10 STEPS
    timeout_seconds = CONFIG.get("AGENT_TIMEOUT", 120) 
    retry_limit = CONFIG.get("AGENT_RETRY_LIMIT", 2)
    step = 0
    start_time = time.time()

    while step < max_steps:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            logger.warning(f"⏰ Agent loop timeout after {elapsed:.1f} seconds")
            return make_result("Bhai, task thoda zyada time le raha tha, main timeout ho gaya. Kya aage badhein?", priority="high", agent_executed=True)

        logger.info(f"🔄 Agent Loop Step {step + 1}/{max_steps}")
        current_time = datetime.datetime.now().strftime('%A, %d %B %Y | %I:%M %p')

        if scratchpad and len(scratchpad) > CONFIG.get("AGENT_SCRATCHPAD_MAX_CHARS", 8000):
            scratchpad = summarize_scratchpad(scratchpad)

        current_step_context = context if step == 0 else "[Context loaded in Step 1. Please focus on the Goal and Scratchpad observations below.]"

        # 🚀 DYNAMIC BUDGET TRACKER INJECTED HERE
        panic_warning = "⚠️ WARNING: You are running out of steps! Synthesize data and wrap up the task NOW." if step + 1 >= max_steps - 1 else "You have enough steps to thoroughly research or process."

        prompt = f"""[SYSTEM STATUS]
Time: {current_time}
[BUDGET TRACKER]
Current Step: {step + 1} out of {max_steps}. 
{panic_warning}
[MEMORY & CONTEXT]
{current_step_context}
[ORIGINAL COMMAND]
{raw_command}
[SCRATCHPAD]
{scratchpad if scratchpad else "No actions taken yet."}
Based on the Scratchpad and Budget, what is the NEXT logical step? Return JSON."""

        try:
            completion = groq_client.chat.completions.create(
                model=AGENT_MODEL,
                messages=[{"role": "system", "content": AGENT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            ai_response = json.loads(clean_json_string(completion.choices[0].message.content.strip()))
            logger.info(f"🧠 Agent Thought: {ai_response.get('thought', 'Thinking...')}")

            if ai_response.get("is_task_complete"):
                logger.info("✅ Agent declared task complete!")
                final_text = ai_response.pop("response", "")
                
                # Aggressive fallback logic in case of lazy model
                if not final_text or len(final_text.strip()) < 5:
                    if scratchpad:
                        lines = scratchpad.split('\n')
                        for line in reversed(lines):
                            if "Observation:" in line:
                                final_text = line.split("Observation:", 1)[-1].strip()
                                break
                        if not final_text and len(lines) > 0:
                            last_line = lines[-1].strip()
                            if last_line and ":" in last_line:
                                final_text = last_line.split(":", 1)[-1].strip()
                if not final_text:
                    final_text = "Task completed sir."
                
                return make_result(final_text, is_agentic=True, agent_executed=True, **ai_response)

            observation = None
            for attempt in range(retry_limit):
                try:
                    observation = execute_single_tool_sync(ai_response)
                    
                    obs_prefix = observation[:50].lower()
                    if observation and ("error" not in obs_prefix and "❌" not in obs_prefix and "failed" not in obs_prefix):
                        break
                    elif attempt < retry_limit - 1:
                        logger.warning(f"⚠️ Tool attempt {attempt+1} failed: {observation}. Retrying in 2s...")
                        time.sleep(2) # Backoff for rate limits
                except Exception as tool_err:
                    logger.error(f"Tool execution exception: {tool_err}")
                    observation = f"Observation: Tool execution error - {tool_err}"
                    if attempt < retry_limit - 1:
                        time.sleep(2)
            else:
                observation = f"Observation: Tool failed after {retry_limit} retries. Analyze this failure and try a different approach."

            if scratchpad == "":
                scratchpad = f"- Step {step+1}: {observation}"
            else:
                scratchpad += f"\n- Step {step+1}: {observation}"

        except Exception as e:
            logger.error(f"❌ Agent Loop Error (Possibly Rate Limit): {e}")
            time.sleep(3)
            break

        step += 1
        time.sleep(1)

    return make_result("Bhai, maine maximum steps (10) le liye hain. Task loop limit tak pahunch gaya hai.", priority="high", agent_executed=True)

# ==================================================================================
# 🚦 PURE AI ROUTER (ULTRA-SMART 2-TIER ROUTING)
# ==================================================================================
def fetch_hybrid_response(raw_command: str, context: str, search_results: str = "") -> Optional[Dict[str, any]]:
    if not groq_client:
        logger.warning("⚠️ No Groq client found, defaulting to Fast Brain.")
        return fetch_from_groq(raw_command, context, search_results)

    try:
        router_prompt = f"""You are Jarvis's core Intent Router.
Your job is to logically classify the user's command into exactly ONE of two categories: 'FAST' or 'AGENTIC'.

[CLASSIFICATION RULES]

1. 'AGENTIC' (For Research, Thinking, and Writing)
   - ALWAYS use if the user wants to search the internet, fetch news, or check weather.
   - ALWAYS use if the user wants to WRITE, CREATE, READ, or MOVE a file in the Workspace.
   - ALWAYS use if the command requires research, summarization, or gathering data before answering (e.g., "Deep research on X and make a report").

2. 'FAST' (For Instant Reflexes, Actions, and Chat)
   - ALWAYS use if the user wants to OPEN a workspace file on their screen (e.g., "open AGI report", "show file").
   - ALWAYS use for opening/closing apps, URLs, or playing YouTube videos.
   - ALWAYS use for sending Emails or WhatsApp messages.
   - ALWAYS use for generating/editing images.
   - ALWAYS use for general chat, jokes, or direct questions that don't need internet search.

[CRITICAL OVERRIDES - DO NOT FAIL THESE]
- If the command implies OPENING or VIEWING a file (open, kholo, dikhao) -> Route to 'FAST'.
- If the command implies CREATING, WRITING, or RESEARCHING -> Route to 'AGENTIC'.

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
            logger.info("🚦 Smart Router: AGENTIC (Web Search / File Analysis / Multi-step)")
            return run_agentic_loop(raw_command, context)
        else:
            # Default fallback to Fast Brain
            logger.info("🚦 Smart Router: FAST (Direct Action / Quick Chat)")
            return fetch_from_groq(raw_command, context, search_results)
            
    except Exception as e:
        logger.error(f"⚠️ Smart Router Error: {e}. Defaulting to Fast Brain.")
        return fetch_from_groq(raw_command, context, search_results)

# ==================================================================================
# MAIN PROCESSOR
# ==================================================================================
def process_with_cohere(raw_command: str, context: str, search_results: str = "") -> Dict[str, any]:
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

    complex_keywords = ["search", "find", "google", "youtube", "play", "generate", "image", "write", "code",
                        "who", "what", "aur", "and", "then", "sath", "email", "mail", "type", "likho",
                        "mute", "volume", "badhao", "kam", "agar", "if", "toh", "read", "padho"]
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

    if not result:
        return make_result("Connection failed, Sir.", priority="low")

    required_keys = ["response", "apps_to_open", "apps_to_close", "urls_to_open", "image_command",
                     "search_actions", "youtube_play", "gui_action", "email_action", "workspace_action",
                     "whatsapp_action"]
    for k in required_keys:
        if k not in result:
            result[k] = "" if k == "youtube_play" else ({} if k in ["email_action", "workspace_action", "image_command", "search_actions", "whatsapp_action"] else [])

    if isinstance(result.get("gui_action"), dict):
        result["gui_action"] = [result["gui_action"]]
    for action in result["gui_action"]:
        if isinstance(action, dict) and action.get("action_type") == "type":
            action["action_type"] = "typewrite"

    if result["apps_to_open"]:
        false_positives = ["google", "chrome", "browser", "photos", "gallery", "image", "gmail", "mail"]
        result["apps_to_open"] = [app for app in result["apps_to_open"] if app.lower() not in false_positives]

    return result