from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
from modules.logger import logger
from tools.open_any import open_any_app
from tools.close_any import close_any_app
from tools.generate_image import handle_image_command 
from tools.gui_automation import perform_gui_action
from tools.search_tools.search_hub import execute_search_actions
from modules.emailManager.email_manager import send_email, delete_email
from tools.messenger import send_whatsapp_message
from modules.voice.tts import speak
from modules.workspace import workspace
import shutil
import platform
import subprocess
import json
import os
import webbrowser
import pywhatkit

# ==================================================================================
# ⚡ THE ORIGINAL ASYNC EXECUTOR (For Fast Brain)
# ==================================================================================
def execute_actions(result: Dict[str, any], executor: ThreadPoolExecutor) -> str:
    """Execute actions based on processed command result and return search results if any."""
    def log_action(message: str) -> None:
        logger.info(message)

    search_results = ""
    
    # 🗣️ 1. TTS Feedback
    response_text = result.get('response', '')
    if response_text:
        executor.submit(speak, response_text)

    # 🎵 2. YOUTUBE PLAYER
    youtube_query = result.get('youtube_play')
    if youtube_query:
        def play_on_youtube(query):
            log_action(f"▶️ Playing on YouTube: {query}")
            try: pywhatkit.playonyt(query)
            except Exception as e: log_action(f"❌ Failed to play on YouTube: {e}")
        executor.submit(play_on_youtube, youtube_query)

    # 💻 3. System Actions (Apps & URLs)
    if result.get('apps_to_open'):
        def thread_open(apps):
            opened = open_any_app(apps)
            if opened: log_action(f"Opened: {', '.join(opened)}")
        executor.submit(thread_open, result['apps_to_open'])

    if result.get('apps_to_close'):
        def thread_close(apps):
            closed = close_any_app(apps)
            if closed: log_action(f"Closed: {', '.join(closed)}")
        executor.submit(thread_close, result['apps_to_close'])

    if result.get('urls_to_open'):
        def thread_open_urls(urls):
            for url in urls:
                if url.startswith('http'):
                    log_action(f"🔗 Opening Dynamic Link: {url}")
                    try: webbrowser.open(url)
                    except Exception as e: log_action(f"❌ Failed to open link: {e}")
        executor.submit(thread_open_urls, result['urls_to_open'])

    # 🎨 4. HYBRID IMAGE GENERATION & EDITING
    image_cmd = result.get('image_command')
    if image_cmd and isinstance(image_cmd, dict) and image_cmd.get('action'):
        action = image_cmd.get('action', 'generate')
        prompt = image_cmd.get('prompt', '')
        filename = image_cmd.get('filename')
        target_file = image_cmd.get('target_file')
        if prompt:
            log_action(f"🖼️ Image Action: {action.upper()} | Prompt: {prompt}")
            executor.submit(handle_image_command, action, prompt, filename, target_file)
            
    # 📁 5. WORKSPACE MANAGER (🚀 WITH 3-ROOM MOVEMENT)
    workspace_cmd = result.get('workspace_action')
    if workspace_cmd and isinstance(workspace_cmd, dict) and workspace_cmd.get('action'):
        act = workspace_cmd.get('action')
        target_file = workspace_cmd.get('file')
        
        def manage_workspace(action_type, fname):
            if not fname: return None
            fname = fname.strip("/\\")
            
            file_path = None
            for d in [workspace.creations_dir, workspace.vault_dir, workspace.temp_dir]:
                if (d / fname).exists():
                    file_path = d / fname
                    break
            
            if not file_path:
                msg = f"❌ Workspace Error: File '{fname}' nahi mili."
                log_action(msg)
                return msg

            try:
                if action_type == "open":
                    log_action(f"📂 Opening workspace file: {fname}")
                    if platform.system() == 'Windows': os.startfile(str(file_path))
                    elif platform.system() == 'Darwin': subprocess.call(('open', str(file_path)))
                    else: subprocess.call(('xdg-open', str(file_path)))
                    return None
                        
                elif action_type == "delete":
                    os.remove(file_path)
                    log_action(f"🗑️ Deleted workspace file: {fname}")
                    workspace.sync_registry() 
                    return None
                    
                elif action_type == "move":
                    dest_folder_name = workspace_cmd.get('to', 'Vault').capitalize()
                    if dest_folder_name not in ["Vault", "Creations", "Temp"]: dest_folder_name = "Vault"
                        
                    dest_dir = getattr(workspace, f"{dest_folder_name.lower()}_dir", workspace.vault_dir)
                    base_name, ext = os.path.splitext(fname)
                    counter = 1
                    safe_name = fname
                    while (dest_dir / safe_name).exists():
                        safe_name = f"{base_name} ({counter}){ext}"
                        counter += 1
                        
                    dest_path = dest_dir / safe_name
                    shutil.move(str(file_path), str(dest_path))
                    log_action(f"📦 Moved {fname} to {dest_folder_name} as {safe_name}")
                    workspace.add_file_record(safe_name, dest_folder_name, f"Moved by Jarvis from {file_path.parent.name}")
                    workspace.sync_registry()
                    executor.submit(speak, f"Bhai, maine file ko {dest_folder_name} mein move kar diya hai.")
                    return None
                    
                elif action_type == "read":
                    log_action(f"📖 Reading workspace file: {fname}")
                    if fname.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.exe')):
                        return f"❌ Error: Cannot read binary file '{fname}'."
                    with open(file_path, "r", encoding="utf-8") as f: return f"📁 File Content ({fname}):\n{f.read()[:5000]}"
                    
            except Exception as e:
                log_action(f"❌ Workspace action failed: {e}")
                return None

        if act == "read":
            read_data = manage_workspace(act, target_file)
            if read_data: search_results += f"\n{read_data}"
        else:
            executor.submit(manage_workspace, act, target_file)
    
    # 🖱️ 6. GUI Actions
    gui_actions = result.get('gui_action', [])
    if isinstance(gui_actions, dict): gui_actions = [gui_actions]
    if gui_actions:
        def thread_gui(actions):
            for action in actions:
                if isinstance(action, dict):
                    gui_response = perform_gui_action(action)
                    if gui_response: log_action(gui_response)
        executor.submit(thread_gui, gui_actions)

    # 📧 7. EMAIL BLOCK
    email_action = result.get('email_action', {})
    if email_action and isinstance(email_action, dict) and email_action.get('action_type') == "send":
        params = email_action.get('params', {})
        def thread_email():
            contact_book = {}
            contact_file_path = os.path.join(os.path.dirname(__file__), "emailManager", "contact_book.json")
            try:
                with open(contact_file_path, "r", encoding="utf-8") as f: contact_book = json.load(f)
            except: pass

            requested_to = params.get('to', '').lower()
            to_address = contact_book.get(requested_to, params.get('to', ''))
            
            file_path_raw = params.get('file_path', '')
            attachment_abs_path = None
            if file_path_raw:
                clean_rel_path = file_path_raw.lstrip("/\\")
                potential_path = workspace.base_path / clean_rel_path
                if potential_path.exists(): attachment_abs_path = str(potential_path)

            log_action(f"📧 Drafting Email to: {to_address} (Attachment: {'Yes' if attachment_abs_path else 'No'})")
            success = send_email(to_address, params.get('subject', 'Update'), params.get('body', ''), attachment_abs_path)
            if success: log_action("✅ Email sent successfully.")
        executor.submit(thread_email)

    # 📱 8. WHATSAPP BLOCK
    whatsapp_action = result.get('whatsapp_action', {})
    if whatsapp_action and isinstance(whatsapp_action, dict) and whatsapp_action.get('to'):
        to_name = whatsapp_action.get('to')
        msg_body = whatsapp_action.get('message', '')
        file_path_raw = whatsapp_action.get('file_path', '')
        
        def thread_whatsapp():
            attachment_abs_path = None
            if file_path_raw:
                clean_rel_path = file_path_raw.lstrip("/\\")
                potential_path = workspace.base_path / clean_rel_path
                if potential_path.exists(): attachment_abs_path = str(potential_path)
            
            log_action(f"📱 Sending WhatsApp to '{to_name}'...")
            wa_result = send_whatsapp_message(to_name, msg_body, attachment_abs_path)
            log_action(wa_result)
        executor.submit(thread_whatsapp)

    return search_results

# ==================================================================================
# 🤖 NEW: SYNCHRONOUS EXECUTOR (Specifically for the AutoGPT Agentic Loop)
# ==================================================================================
def execute_single_tool_sync(action_dict: Dict[str, any]) -> str:
    """Executes a single tool synchronously and returns the Observation string."""
    observation = "Observation: No valid action executed."

    # 1. SEARCH ACTION
    search_actions = action_dict.get('search_actions')
    if search_actions and isinstance(search_actions, dict) and any(search_actions.values()):
        try:
            logger.info(f"🤖 Agent executing Search: {list(search_actions.keys())}")
            search_output = execute_search_actions(search_actions)
            if search_output: return f"Observation: Search Data Fetched -> {search_output[:2000]}..."
            return "Observation: Search completed but no data found."
        except Exception as e: return f"Observation: Search failed -> {e}"

    # 2. WORKSPACE ACTION (Read files to memory)
    workspace_cmd = action_dict.get('workspace_action')
    if workspace_cmd and isinstance(workspace_cmd, dict) and workspace_cmd.get('action'):
        act = workspace_cmd.get('action')
        fname = workspace_cmd.get('file', '').strip("/\\")
        
        file_path = None
        for d in [workspace.creations_dir, workspace.vault_dir, workspace.temp_dir]:
            if (d / fname).exists():
                file_path = d / fname
                break

        if not file_path: return f"Observation: Workspace Error -> File '{fname}' not found."

        try:
            if act == "read":
                logger.info(f"🤖 Agent Reading File: {fname}")
                if fname.lower().endswith(('.png', '.jpg', '.pdf', '.exe')): return f"Observation: Error -> Cannot read binary file '{fname}'."
                with open(file_path, "r", encoding="utf-8") as f: return f"Observation: File Content ({fname}) -> {f.read()[:3000]}"
            else: return f"Observation: Agent can only 'read' files right now. Use normal command for move/delete."
        except Exception as e: return f"Observation: Workspace action failed -> {e}"

    # 3. EMAIL ACTION
    email_action = action_dict.get('email_action', {})
    if email_action and isinstance(email_action, dict) and email_action.get('action_type') == "send":
        params = email_action.get('params', {})
        requested_to = params.get('to', '').lower()
        
        contact_book = {}
        contact_file_path = os.path.join(os.path.dirname(__file__), "emailManager", "contact_book.json")
        try:
            with open(contact_file_path, "r", encoding="utf-8") as f: contact_book = json.load(f)
        except: pass
        to_address = contact_book.get(requested_to, params.get('to', ''))

        file_path_raw = params.get('file_path', '')
        attachment_abs_path = None
        if file_path_raw:
            clean_rel_path = file_path_raw.lstrip("/\\")
            potential_path = workspace.base_path / clean_rel_path
            if potential_path.exists(): attachment_abs_path = str(potential_path)

        logger.info(f"🤖 Agent Sending Email to: {to_address}")
        success = send_email(to_address, params.get('subject', 'Update'), params.get('body', ''), attachment_abs_path)
        if success: return f"Observation: Email successfully sent to {requested_to}."
        return f"Observation: Failed to send email to {requested_to}."

    # 4. WHATSAPP ACTION
    whatsapp_action = action_dict.get('whatsapp_action', {})
    if whatsapp_action and isinstance(whatsapp_action, dict) and whatsapp_action.get('to'):
        to_name = whatsapp_action.get('to')
        msg_body = whatsapp_action.get('message', '')
        file_path_raw = whatsapp_action.get('file_path', '')
        
        attachment_abs_path = None
        if file_path_raw:
            clean_rel_path = file_path_raw.lstrip("/\\")
            potential_path = workspace.base_path / clean_rel_path
            if potential_path.exists(): attachment_abs_path = str(potential_path)
        
        logger.info(f"🤖 Agent Sending WhatsApp to: {to_name}")
        wa_result = send_whatsapp_message(to_name, msg_body, attachment_abs_path)
        return f"Observation: {wa_result}"

    return observation