from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
from core.logger.logger import logger
from tools.OpenCloseApps.open_any import open_any_app
from tools.OpenCloseApps.close_any import close_any_app
from tools.ImageGeneration.generate_image import handle_image_command 
from tools.SearchTools.search_hub import execute_search_actions
from tools.Messanger.email_manager import send_email, delete_email
from tools.Messanger.whatsapp import send_whatsapp_message
from core.voice.tts import speak
from tools.workspace.workspace import workspace
import shutil
import platform
import subprocess
import json
import os
import webbrowser
import pywhatkit
import difflib

# --- ADD THIS IMPORT ---
from tools.SearchTools.deep_research import deep_research_as_tool


# ==================================================================================
# 🔥 OPTIMIZED smart_file_finder (uses workspace registry, no disk scanning)
# ==================================================================================
def smart_file_finder(requested_name):
    """Voice commands ke liye Fuzzy/Smart File Matching - uses registry.json for O(1) lookup"""
    if not requested_name:
        return None

    # 1. Pehle exact match try karo (direct filesystem check - fast)
    exact_match = workspace.find_file_in_workspace(requested_name)
    if exact_match:
        return exact_match

    # 2. Registry se saari files ka data load karo (no disk I/O)
    registry = workspace._load_registry()
    files_list = registry.get("files", [])
    if not files_list:
        return None

    # Build a map: clean_name -> (folder_name, filename, full_path)
    # Folder paths mapping
    folder_paths = {
        "Creations": workspace.creations_dir,
        "Vault": workspace.vault_dir,
        "Temp": workspace.temp_dir
    }

    clean_map = {}
    for entry in files_list:
        filename = entry.get("filename")
        location = entry.get("location", "/Vault").strip("/")  # e.g., "Vault"
        folder_name = location.split("/")[0] if location else "Vault"
        folder_path = folder_paths.get(folder_name, workspace.vault_dir)
        full_path = folder_path / filename

        # Ensure the file actually exists (safety check)
        if not full_path.exists():
            continue

        # Clean name for matching
        clean_name = os.path.splitext(filename)[0].lower().replace("_", " ").replace("-", " ")
        clean_map[clean_name] = full_path

    if not clean_map:
        return None

    # 3. User ke bole hue naam ko clean karo
    req_clean = requested_name.lower().replace(" file", "").replace(" wali", "").replace(" report", "").replace(".md", "").replace(".txt", "").strip()

    # 4. Exact match on cleaned names
    if req_clean in clean_map:
        return clean_map[req_clean]

    # 5. Fuzzy match as last resort
    matches = difflib.get_close_matches(req_clean, clean_map.keys(), n=1, cutoff=0.4)
    if matches:
        matched_path = clean_map[matches[0]]
        logger.info(f"🔍 Smart Finder: '{requested_name}' matched with '{matched_path.name}'")
        return matched_path

    return None


# ==================================================================================
# ⚡ ASYNC EXECUTOR (For Fast Brain)
# ==================================================================================
def execute_actions(result: Dict[str, any], executor: ThreadPoolExecutor) -> str:
    """Execute actions based on processed command result and return search results if any."""
    
    def log_action(message: str) -> None:
        logger.info(message)

    search_results = ""
    
    # 🗣️ TTS Feedback & Terminal Print
    response_text = result.get('response', '')
    if response_text:
        log_action(f"🤖 JARVIS: {response_text}")
        executor.submit(speak, response_text)

    # Agent already executed? Skip duplicate
    if result.get("agent_executed"):
        logger.debug("🤖 Agent tool execution complete. Skipping duplicate async execution.")
        return ""

    # 🎵 YouTube Player
    youtube_query = result.get('youtube_play')
    if youtube_query:
        def play_on_youtube(query):
            log_action(f"▶️ Playing on YouTube: {query}")
            try: 
                pywhatkit.playonyt(query)
            except Exception as e: 
                log_action(f"❌ Failed to play on YouTube: {e}")
        executor.submit(play_on_youtube, youtube_query)

    # 💻 System Actions (Apps & URLs)
    if result.get('apps_to_open'):
        def thread_open(apps):
            opened = open_any_app(apps)
            if opened: 
                log_action(f"Opened: {', '.join(opened)}")
        executor.submit(thread_open, result['apps_to_open'])

    if result.get('apps_to_close'):
        def thread_close(apps):
            closed = close_any_app(apps)
            if closed: 
                log_action(f"Closed: {', '.join(closed)}")
        executor.submit(thread_close, result['apps_to_close'])

    if result.get('urls_to_open'):
        def thread_open_urls(urls):
            for url in urls:
                if url.startswith('http'):
                    log_action(f"🔗 Opening Dynamic Link: {url}")
                    try: 
                        webbrowser.open(url)
                    except Exception as e: 
                        log_action(f"❌ Failed to open link: {e}")
        executor.submit(thread_open_urls, result['urls_to_open'])

    # 🎨 Image Generation & Editing
    image_cmd = result.get('image_command')
    if image_cmd and isinstance(image_cmd, dict) and image_cmd.get('action'):
        action = image_cmd.get('action', 'generate')
        prompt = image_cmd.get('prompt', '')
        filename = image_cmd.get('filename')
        target_file = image_cmd.get('target_file')
        if prompt:
            log_action(f"🖼️ Image Action: {action.upper()} | Prompt: {prompt}")
            executor.submit(handle_image_command, action, prompt, filename, target_file)
            
    # 📁 Workspace Manager (with rename support)
    workspace_cmd = result.get('workspace_action')
    if workspace_cmd and isinstance(workspace_cmd, dict) and workspace_cmd.get('action'):
        act = workspace_cmd.get('action')
        target_file = workspace_cmd.get('file')
        
        def manage_workspace(action_type, fname):
            if not fname: 
                return None
            fname = fname.strip("/\\")
            
            file_path = smart_file_finder(fname)
            
            if not file_path and action_type not in ["write", "list"]:
                msg = f"❌ Workspace Error: File '{fname}' nahi mili."
                log_action(msg)
                return msg

            try:
                if action_type == "open":
                    log_action(f"📂 Opening workspace file: {file_path.name}")
                    if platform.system() == 'Windows': 
                        os.startfile(str(file_path))
                    elif platform.system() == 'Darwin': 
                        subprocess.call(('open', str(file_path)))
                    else: 
                        subprocess.call(('xdg-open', str(file_path)))
                    return None
                        
                elif action_type == "delete":
                    os.remove(file_path)
                    log_action(f"🗑️ Deleted workspace file: {file_path.name}")
                    workspace.sync_registry() 
                    return None
                    
                elif action_type == "move":
                    dest_folder_name = workspace_cmd.get('to', 'Vault').capitalize()
                    if dest_folder_name not in ["Vault", "Creations", "Temp"]:
                        dest_folder_name = "Vault"
                    dest_dir = getattr(workspace, f"{dest_folder_name.lower()}_dir", workspace.vault_dir)
                    
                    dest_name = workspace_cmd.get('dest_name', '')
                    if not dest_name:
                        dest_name = file_path.name
                    
                    dest_path = dest_dir / dest_name
                    
                    if dest_path.exists():
                        msg = f"❌ Move failed: '{dest_name}' already exists in {dest_folder_name}. Please use a different dest_name or delete existing file."
                        log_action(msg)
                        executor.submit(speak, f"Bhai, {dest_folder_name} folder mein '{dest_name}' pehle se hai.")
                        return msg
                    
                    shutil.move(str(file_path), str(dest_path))
                    log_action(f"📦 Moved {file_path.name} to {dest_folder_name} as {dest_name}")
                    workspace.add_file_record(dest_name, dest_folder_name, f"Moved by Jarvis from {file_path.parent.name}")
                    workspace.sync_registry()
                    executor.submit(speak, f"Bhai, maine file ko {dest_folder_name} mein move kar diya hai.")
                    return None
                    
                elif action_type == "read":
                    log_action(f"📖 Reading workspace file: {file_path.name}")
                    if file_path.name.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.exe')):
                        return f"❌ Error: Cannot read binary file '{file_path.name}'."
                    with open(file_path, "r", encoding="utf-8") as f:
                        return f"📁 File Content ({file_path.name}):\n{f.read()[:5000]}"
                
                elif action_type == "write":
                    content = workspace_cmd.get('content', '')
                    target_dir = workspace.creations_dir
                    new_file_path = target_dir / fname
                    with open(new_file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    log_action(f"📝 Writing to workspace file: {fname}")
                    workspace.add_file_record(fname, "Creations", "Written by Jarvis Fast Brain.")
                    workspace.sync_registry()
                    return None
                    
            except Exception as e:
                log_action(f"❌ Workspace action failed: {e}")
                return None

        if act == "read":
            read_data = manage_workspace(act, target_file)
            if read_data: 
                search_results += f"\n{read_data}"
        else:
            executor.submit(manage_workspace, act, target_file)
    
    # Fast Brain Workspace File Open
    workspace_file_to_open = result.get('workspace_file_to_open')
    if workspace_file_to_open and isinstance(workspace_file_to_open, str) and workspace_file_to_open.strip():
        def open_workspace_file_fast(filename):
            file_path = smart_file_finder(filename)
            if file_path:
                log_action(f"📂 Fast Brain: Opening workspace file: {file_path.name}")
                try:
                    if platform.system() == 'Windows':
                        os.startfile(str(file_path))
                    elif platform.system() == 'Darwin':
                        subprocess.call(('open', str(file_path)))
                    else:
                        subprocess.call(('xdg-open', str(file_path)))
                    executor.submit(speak, f"Sir, {file_path.name} khol diya.")
                except Exception as e:
                    log_action(f"❌ Failed to open file: {e}")
                    executor.submit(speak, f"Sir, file nahi khul rahi.")
            else:
                log_action(f"❌ Workspace file not found: {filename}")
                executor.submit(speak, f"Sir, '{filename}' workspace mein nahi mili.")
        executor.submit(open_workspace_file_fast, workspace_file_to_open.strip())

    # Email
    email_action = result.get('email_action', {})
    if email_action and isinstance(email_action, dict) and email_action.get('action_type') == "send":
        params = email_action.get('params', {})
        def thread_email():
            contact_book = {}
            contact_file_path = os.path.join(os.path.dirname(__file__), "emailManager", "contact_book.json")
            try:
                with open(contact_file_path, "r", encoding="utf-8") as f: 
                    contact_book = json.load(f)
            except: 
                pass

            requested_to = params.get('to', '').lower()
            to_address = contact_book.get(requested_to, params.get('to', ''))
            
            file_path_raw = params.get('file_path', '')
            attachment_abs_path = None
            if file_path_raw:
                found = smart_file_finder(file_path_raw)
                if found:
                    attachment_abs_path = str(found)
                    log_action(f"🔍 Auto-resolved attachment: {found.name}")
                else:
                    log_action(f"❌ Attachment file not found: {file_path_raw}")

            log_action(f"📧 Drafting Email to: {to_address} (Attachment: {'Yes' if attachment_abs_path else 'No'})")
            success = send_email(to_address, params.get('subject', 'Update'), params.get('body', ''), attachment_abs_path)
            if success: 
                log_action("✅ Email sent successfully.")
        executor.submit(thread_email)

    # WhatsApp
    whatsapp_action = result.get('whatsapp_action', {})
    if whatsapp_action and isinstance(whatsapp_action, dict) and whatsapp_action.get('to'):
        to_name = whatsapp_action.get('to')
        msg_body = whatsapp_action.get('message', '')
        file_path_raw = whatsapp_action.get('file_path', '')
        
        def thread_whatsapp():
            attachment_abs_path = None
            if file_path_raw:
                found = smart_file_finder(file_path_raw)
                if found:
                    attachment_abs_path = str(found)
                    log_action(f"🔍 Auto-resolved WhatsApp attachment: {found.name}")
            
            log_action(f"📱 Sending WhatsApp to '{to_name}'...")
            wa_result = send_whatsapp_message(to_name, msg_body, attachment_abs_path)
            log_action(wa_result)
        executor.submit(thread_whatsapp)

    return search_results


# ==================================================================================
# 🤖 SYNCHRONOUS EXECUTOR (For Agentic Loop) - with rename support
# ==================================================================================
def execute_single_tool_sync(action_dict: Dict[str, any]) -> str:
    """
    Executes a single tool synchronously and returns the Observation string.
    Supports 'dest_name' for rename during move.
    """
    observation = "Observation: No valid action executed."

    # 1. SEARCH ACTION
    search_actions = action_dict.get('search_actions')
    if search_actions and isinstance(search_actions, dict) and any(search_actions.values()):
        try:
            logger.info(f"🤖 Agent executing Search: {list(search_actions.keys())}")
            from tools.SearchTools.search_hub import execute_search_actions
            search_output = execute_search_actions(search_actions)
            if search_output:
                return f"Observation: Search successful. Fetched Data -> {search_output[:4000]}..."
            return "Observation: Search completed but NO data found. 💡 Tip: Try different keywords or a broader search."
        except Exception as e:
            return f"Observation: Search API failed -> {e}"

    # 2. WORKSPACE ACTION (Read/Open/Delete/Move/List/Write)
    workspace_cmd = action_dict.get('workspace_action')
    if workspace_cmd and isinstance(workspace_cmd, dict) and workspace_cmd.get('action'):
        act = workspace_cmd.get('action')
        fname = workspace_cmd.get('file', '').strip("/\\")
        
        if act == "list":
            try:
                context_str = workspace.get_workspace_context()
                return f"Observation: Workspace files:\n{context_str}"
            except Exception as e:
                return f"Observation: Workspace list failed -> {e}"
        
        if not fname:
            return "Observation: Workspace action requires 'file' parameter."
            
        if act == "write":
            try:
                logger.info(f"🤖 Agent Creating/Writing File: {fname}")
                content = workspace_cmd.get('content', '')
                if not content:
                    return f"Observation: Error -> Missing 'content' parameter to write into '{fname}'."
                
                target_dir = workspace.creations_dir
                file_path = target_dir / fname
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                
                workspace.add_file_record(fname, "Creations", "Generated and saved by AI Agent.")
                workspace.sync_registry()
                return f"Observation: Successfully created and wrote to '{fname}' in Creations folder. [Length: {len(content)} chars]"
            except Exception as e:
                return f"Observation: Workspace file write failed -> {e}"
        
        # SMART FILE FINDER FOR READ/OPEN/DELETE/MOVE (now registry-based)
        file_path = smart_file_finder(fname)
        if not file_path:
            # Before giving up, try a direct exact filename match in known folders (legacy support)
            for folder in [workspace.creations_dir, workspace.vault_dir, workspace.temp_dir]:
                candidate = folder / fname
                if candidate.exists():
                    file_path = candidate
                    break
            if not file_path:
                return f"Observation: File '{fname}' NOT FOUND. 💡 Tip: Try using {{\"workspace_action\": {{\"action\": \"list\"}}}} to see exact available filenames."

        try:
            if act == "read":
                logger.info(f"🤖 Agent Reading File: {file_path.name}")
                if file_path.name.lower().endswith(('.png', '.jpg', '.pdf', '.exe')):
                    return f"Observation: Error -> Cannot read binary file '{file_path.name}'. Do not try to read this again."
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()[:5000]
                return f"Observation: Content of {file_path.name} fetched. [Length: {len(content)} chars] -> {content}"
            
            elif act == "open":
                logger.info(f"🤖 Agent Opening File: {file_path.name}")
                if platform.system() == 'Windows':
                    os.startfile(str(file_path))
                elif platform.system() == 'Darwin':
                    subprocess.call(('open', str(file_path)))
                else:
                    subprocess.call(('xdg-open', str(file_path)))
                return f"Observation: Successfully opened file '{file_path.name}' on screen."
            
            elif act == "delete":
                logger.info(f"🤖 Agent Deleting File: {file_path.name}")
                os.remove(file_path)
                workspace.sync_registry()
                return f"Observation: Successfully deleted file '{file_path.name}'."
            
            elif act == "move":
                dest_folder = workspace_cmd.get('to', 'Vault').capitalize()
                if dest_folder not in ["Vault", "Creations", "Temp"]:
                    dest_folder = "Vault"
                dest_dir = getattr(workspace, f"{dest_folder.lower()}_dir", workspace.vault_dir)
                
                dest_name = workspace_cmd.get('dest_name', '')
                if not dest_name:
                    dest_name = file_path.name
                
                dest_path = dest_dir / dest_name
                
                if dest_path.exists():
                    return f"Observation: Move FAILED. File '{dest_name}' already exists in {dest_folder}. Please use a different dest_name or delete the existing file first."
                
                shutil.move(str(file_path), str(dest_path))
                workspace.add_file_record(dest_name, dest_folder, f"Moved by Agent from {file_path.parent.name}")
                workspace.sync_registry()
                return f"Observation: Successfully moved '{file_path.name}' to {dest_folder} as '{dest_name}'."
            
            else:
                return f"Observation: Workspace action '{act}' not supported."
                
        except Exception as e:
            return f"Observation: Workspace action failed -> {e}"

    # 3. EMAIL ACTION 
    email_action = action_dict.get('email_action', {})
    if email_action and isinstance(email_action, dict) and email_action.get('action_type') == "send":
        params = email_action.get('params', {})
        requested_to = params.get('to', '').lower()
        
        contact_book = {}
        contact_file_path = os.path.join(os.path.dirname(__file__), "emailManager", "contact_book.json")
        try:
            with open(contact_file_path, "r", encoding="utf-8") as f:
                contact_book = json.load(f)
        except:
            pass
        to_address = contact_book.get(requested_to, params.get('to', ''))

        file_path_raw = params.get('file_path', '')
        attachment_abs_path = None
        if file_path_raw:
            found = smart_file_finder(file_path_raw)
            if found:
                attachment_abs_path = str(found)
                logger.info(f"🔍 Auto-resolved email attachment: {found.name}")
            else:
                return f"Observation: Failed to send email. Attachment '{file_path_raw}' not found in workspace."

        logger.info(f"🤖 Agent Sending Email to: {to_address}")
        success = send_email(to_address, params.get('subject', 'Update'), params.get('body', ''), attachment_abs_path)
        if success:
            return f"Observation: Email successfully sent to {requested_to}."
        return f"Observation: Failed to send email to {requested_to}. Check if SMTP or credentials are correct."

    # 4. WHATSAPP ACTION
    whatsapp_action = action_dict.get('whatsapp_action', {})
    if whatsapp_action and isinstance(whatsapp_action, dict) and whatsapp_action.get('to'):
        to_name = whatsapp_action.get('to')
        msg_body = whatsapp_action.get('message', '')
        file_path_raw = whatsapp_action.get('file_path', '')
        
        attachment_abs_path = None
        if file_path_raw:
            found = smart_file_finder(file_path_raw)
            if found:
                attachment_abs_path = str(found)
            else:
                return f"Observation: Failed to send WhatsApp. Attachment '{file_path_raw}' not found."
        
        logger.info(f"🤖 Agent Sending WhatsApp to: {to_name}")
        wa_result = send_whatsapp_message(to_name, msg_body, attachment_abs_path)
        return f"Observation: {wa_result}"

    # 5. APP OPEN/CLOSE
    apps_to_open = action_dict.get('apps_to_open')
    if apps_to_open and isinstance(apps_to_open, list) and apps_to_open:
        try:
            opened = open_any_app(apps_to_open)
            if opened:
                return f"Observation: Opened {', '.join(opened)}"
            else:
                return f"Observation: Could not find or open {', '.join(apps_to_open)}. They might not be installed."
        except Exception as e:
            return f"Observation: Error opening apps -> {e}"

    apps_to_close = action_dict.get('apps_to_close')
    if apps_to_close and isinstance(apps_to_close, list) and apps_to_close:
        try:
            closed = close_any_app(apps_to_close)
            if closed:
                return f"Observation: Closed {', '.join(closed)}"
            else:
                return f"Observation: Could not close {', '.join(apps_to_close)}. They might not be running."
        except Exception as e:
            return f"Observation: Error closing apps -> {e}"

    # 6. YOUTUBE PLAYBACK
    youtube_query = action_dict.get('youtube_play')
    if youtube_query and isinstance(youtube_query, str) and youtube_query.strip():
        try:
            import pywhatkit
            logger.info(f"🤖 Agent playing YouTube: {youtube_query}")
            pywhatkit.playonyt(youtube_query)
            return f"Observation: Playing '{youtube_query}' on YouTube."
        except Exception as e:
            return f"Observation: YouTube error -> {e}"

    # 7. IMAGE GENERATION/EDITING
    image_cmd = action_dict.get('image_command')
    if image_cmd and isinstance(image_cmd, dict) and image_cmd.get('action'):
        try:
            action = image_cmd.get('action', 'generate')
            prompt = image_cmd.get('prompt', '')
            filename = image_cmd.get('filename', 'agent_image')
            target_file = image_cmd.get('target_file')
            
            if not prompt:
                return "Observation: Image action missing prompt."
            
            logger.info(f"🤖 Agent executing image {action}: {prompt}")
            result_path = handle_image_command(action, prompt, filename, target_file)
            if result_path:
                return f"Observation: Image successfully {action}d at {result_path}. It is now in the workspace."
            else:
                return f"Observation: Image {action} failed. API might be down."
        except Exception as e:
            return f"Observation: Image error -> {e}"

    # 9. OPEN URLS
    urls_to_open = action_dict.get('urls_to_open')
    if urls_to_open and isinstance(urls_to_open, list) and urls_to_open:
        try:
            import webbrowser
            for url in urls_to_open:
                if url.startswith('http'):
                    webbrowser.open(url)
            return f"Observation: Opened URLs in default browser: {', '.join(urls_to_open)}"
        except Exception as e:
            return f"Observation: URL open error -> {e}"

    # ==================================================================
    # 🆕 10. DEEP RESEARCH TOOL
    # ==================================================================
    deep_research_cmd = action_dict.get('deep_research')
    if deep_research_cmd and isinstance(deep_research_cmd, dict):
        topic = deep_research_cmd.get('topic', '')
        if not topic:
            return "Observation: Deep research called without 'topic' parameter."
        logger.info(f"🤖 Agent initiating Deep Research on: {topic}")
        try:
            result_obs = deep_research_as_tool(topic)
            return f"Observation: {result_obs}"
        except Exception as e:
            return f"Observation: Deep research error: {e}"

    return observation