from typing import Dict, List
from concurrent.futures import ThreadPoolExecutor
from modules.logger import logger
from tools.open_any import open_any_app
from tools.close_any import close_any_app
from tools.generate_image import handle_image_command 
from tools.gui_automation import perform_gui_action
from tools.perform_search import perform_search
from modules.emailManager.email_manager import send_email, delete_email
from modules.voice.tts import speak

# ⚡ NAYE IMPORTS: Workspace aur File System operations ke liye
from modules.workspace import workspace
import shutil
import platform
import subprocess

import json
import os
import webbrowser
import pywhatkit

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
            try:
                pywhatkit.playonyt(query)
            except Exception as e:
                log_action(f"❌ Failed to play on YouTube: {e}")
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
                    try:
                        webbrowser.open(url)
                    except Exception as e:
                        log_action(f"❌ Failed to open link: {e}")
        executor.submit(thread_open_urls, result['urls_to_open'])

    # 🎨 3.7 HYBRID IMAGE GENERATION & EDITING
    image_cmd = result.get('image_command')
    if image_cmd and isinstance(image_cmd, dict) and image_cmd.get('action'):
        action = image_cmd.get('action', 'generate')
        prompt = image_cmd.get('prompt', '')
        
        filename = image_cmd.get('filename')
        target_file = image_cmd.get('target_file')
        
        if prompt:
            log_action(f"🖼️ Image Action: {action.upper()} | Prompt: {prompt}")
            executor.submit(handle_image_command, action, prompt, filename, target_file)
            
    # 📁 3.8 WORKSPACE MANAGER (🚀 WITH 3-ROOM MOVEMENT)
    workspace_cmd = result.get('workspace_action')
    if workspace_cmd and isinstance(workspace_cmd, dict) and workspace_cmd.get('action'):
        act = workspace_cmd.get('action')
        target_file = workspace_cmd.get('file')
        
        def manage_workspace(action_type, fname):
            if not fname: return None
            
            # File ko teeno sub-folders mein dhoondho
            file_path = None
            for d in [workspace.creations_dir, workspace.vault_dir, workspace.temp_dir]:
                potential_path = d / fname
                if potential_path.exists():
                    file_path = potential_path
                    break
            
            if not file_path:
                msg = f"❌ Workspace Error: File '{fname}' nahi mili."
                log_action(msg)
                return msg

            try:
                if action_type == "open":
                    log_action(f"📂 Opening workspace file: {fname}")
                    if platform.system() == 'Windows':
                        os.startfile(str(file_path))
                    elif platform.system() == 'Darwin': 
                        subprocess.call(('open', str(file_path)))
                    else: 
                        subprocess.call(('xdg-open', str(file_path)))
                    return None
                        
                elif action_type == "delete":
                    os.remove(file_path)
                    log_action(f"🗑️ Deleted workspace file: {fname}")
                    workspace.sync_registry() # Sync instantly
                    return None
                    
                elif action_type == "move":
                    # 🛡️ 1. Fetch Target & Validate
                    dest_folder_name = workspace_cmd.get('to', 'Vault').capitalize()
                    
                    # Strict Security Lock: Only 3 allowed folders
                    if dest_folder_name not in ["Vault", "Creations", "Temp"]:
                        dest_folder_name = "Vault"
                        
                    dest_dir = getattr(workspace, f"{dest_folder_name.lower()}_dir", workspace.vault_dir)
                    
                    # 🛡️ 2. Overwrite Protection (Auto-rename logic)
                    base_name, ext = os.path.splitext(fname)
                    counter = 1
                    safe_name = fname
                    while (dest_dir / safe_name).exists():
                        safe_name = f"{base_name} ({counter}){ext}"
                        counter += 1
                        
                    dest_path = dest_dir / safe_name
                    
                    # 🚀 3. Execute Move
                    shutil.move(str(file_path), str(dest_path))
                    log_action(f"📦 Moved {fname} to {dest_folder_name} as {safe_name}")
                    
                    # 4. Update Registry & Speak
                    workspace.add_file_record(safe_name, dest_folder_name, f"Moved by Jarvis from {file_path.parent.name}")
                    workspace.sync_registry()
                    
                    # Voice feedback for the user
                    executor.submit(speak, f"Bhai, maine file ko {dest_folder_name} mein move kar diya hai.")
                    return None
                    
                elif action_type == "read":
                    log_action(f"📖 Reading workspace file: {fname}")
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    # Return data for the LLM to process
                    return f"📁 File Content ({fname}):\n{content[:5000]}" # Thoda token limit badha diya hai!
                    
            except Exception as e:
                log_action(f"❌ Workspace action '{action_type}' failed: {e}")
                return None

        # Execute Workspace logic
        if act == "read":
            # "Read" must be synchronous so the data can be returned to Pass 2
            read_data = manage_workspace(act, target_file)
            if read_data:
                search_results += f"\n{read_data}"
        else:
            # "Open", "Move", "Delete" run in the background thread
            executor.submit(manage_workspace, act, target_file)
    
    # 🖱️ 3.9 GUI Actions
    gui_actions = result.get('gui_action', [])
    if isinstance(gui_actions, dict): gui_actions = [gui_actions]
    if gui_actions:
        def thread_gui(actions):
            for action in actions:
                if isinstance(action, dict):
                    gui_response = perform_gui_action(action)
                    if gui_response: log_action(gui_response)
        executor.submit(thread_gui, gui_actions)

    # 🌐 4. Information Gathering (Search)
    search_query = result.get('search_query')
    if search_query:
        try:
            search_output = perform_search(search_query, return_results=True)
            if search_output:
                search_results += "\n" + "\n".join([
                    f"Result {i+1}: {r['title']} ({r['link']})\nSnippet: {r['snippet'][:200]}...\nReliability: {'High' if r['reliable'] else 'Standard'}"
                    for i, r in enumerate(search_output)
                ])
                log_action(f"Search results for query '{search_query}' fetched.")
            else:
                log_action(f"No search results for query: {search_query}")
        except Exception as e:
            log_action(f"Search failed for query '{search_query}': {e}")

    # 🛑 5. Universal Agentic Manager
    external_actions = [k for k in result.keys() if k.endswith('_action') and k != 'gui_action' and result[k]]
    execute_external = True
    
    # ⚡ FIX: Pause tools if we searched the web OR read a file
    has_fetched_data = bool(search_query) or (workspace_cmd and workspace_cmd.get('action') == 'read')
    
    if has_fetched_data and external_actions:
        log_action(f"🛑 Universal Manager: Data Fetch + {external_actions} detected. Pausing tools until AI reads data.")
        execute_external = False

    # 📧 6. Execute External Tools (Email)
    if execute_external:
        email_action = result.get('email_action', {})
        if email_action and isinstance(email_action, dict) and email_action.get('action_type'):
            action_type = email_action.get('action_type')
            params = email_action.get('params', {})
            
            if action_type == "send":
                contact_book = {}
                contact_file_path = os.path.join(os.path.dirname(__file__), "emailManager", "contact_book.json")
                try:
                    with open(contact_file_path, "r", encoding="utf-8") as f:
                        contact_book = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError):
                    log_action("⚠️ Warning: Contact book not found or corrupted.")

                requested_to = params.get('to', '').lower()
                to_address = contact_book.get(requested_to, params.get('to', ''))
                
                log_action(f"Drafting Email to: {to_address}")
                success = send_email(to_address, params.get('subject', 'Update'), params.get('body', ''))
                if success: log_action("Email sent successfully.")
                    
            elif action_type == "delete":
                delete_email(params.get('query', ''))

    return search_results