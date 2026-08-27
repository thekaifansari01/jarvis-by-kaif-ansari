import os
import sys
import shutil
import time
import subprocess
import platform
import tempfile
import json
import requests
from pathlib import Path

from core.logger.logger import logger
from core.security import load_decrypted_token, save_encrypted_token

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
LOCK_FILE = os.path.join(PROJECT_ROOT, ".jarvis.lock")
SESSION_DIR = os.path.join(PROJECT_ROOT, "Data", "SessionCookies")

CRED_PATHS = {
    "whatsapp": os.path.join(SESSION_DIR, "auth_info_baileys", "creds.json"),
    "telegram": os.path.join(SESSION_DIR, "jarvis_telegram_session.session"),
    "mail": os.path.join(SESSION_DIR, "token.enc"),
    "calendar": os.path.join(SESSION_DIR, "calendar_token.enc")
}

def is_jarvis_running():
    if not os.path.exists(LOCK_FILE):
        return False
    try:
        with open(LOCK_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise ValueError("Empty lock file")
        pid = int(content)
        if platform.system() == "Windows":
            output = subprocess.check_output(f'tasklist /FI "PID eq {pid}" /NH', shell=True).decode()
            if str(pid) in output:
                return True
        else:
            os.kill(pid, 0)
            return True
    except ValueError:
        logger.warning("Lock file corrupted. Proceeding with auto-cleanup.")
    except Exception:
        pass
    
    remove_lock_file()
    return False

def create_lock_file():
    try:
        with open(LOCK_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"Could not create lock file: {e}")

def remove_lock_file():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        logger.warning(f"Could not remove lock file: {e}")

def safe_delete(path, retries=3, delay=0.5):
    if not os.path.exists(path):
        return False
    for attempt in range(1, retries + 1):
        try:
            if os.path.isdir(path):
                def remove_readonly(func, path, exc_info):
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                shutil.rmtree(path, onerror=remove_readonly)
                return True
            elif os.path.isfile(path) or os.path.islink(path):
                os.chmod(path, 0o777)
                os.remove(path)
                return True
        except PermissionError:
            if attempt < retries:
                time.sleep(delay)
            else:
                return False
        except FileNotFoundError:
            return True
        except Exception:
            return False
    return False

def get_user_confirmation(prompt_text: str) -> bool:
    while True:
        ans = input(f"{prompt_text} (y/n): ").strip().lower()
        if ans in ['y', 'yes']:
            return True
        elif ans in ['n', 'no']:
            return False
        else:
            print("Invalid input. Please enter 'y' or 'n'.")

def deleteMemory():
    try:
        target_folder = os.path.join(PROJECT_ROOT, "Data", "jarvis_memory")
        if not os.path.exists(target_folder):
            logger.info("Memory is already cleared. Nothing to delete.")
            return
            
        if safe_delete(target_folder):
            logger.info("Memory cleared successfully.")
        else:
            logger.warning("Could not clear memory completely. Please check file permissions.")
    except Exception as e:
        logger.error(f"Error encountered while clearing memory: {e}")

def deleteSessionCookies(*targets):
    if not targets:
        logger.warning("No service specified.")
        return
        
    paths_map = {
        "whatsapp": [
            os.path.join(SESSION_DIR, "auth_info_baileys"),
            os.path.join(SESSION_DIR, "chats.db")
        ],
        "calendar": [
            os.path.join(SESSION_DIR, "calendar_token.enc")
        ],
        "mail": [
            os.path.join(SESSION_DIR, "token.enc")
        ],
        "telegram": [
            os.path.join(SESSION_DIR, "jarvis_telegram_session.session"),
            os.path.join(SESSION_DIR, "jarvis_telegram_session.session-journal")
        ]
    }
    
    services_logged_out = []
    already_logged_out = []
    failed_services = []
    
    for target in targets:
        key = str(target).strip().lower()
        if key not in paths_map:
            failed_services.append(target)
            continue
            
        path_list = paths_map[key]
        exists = any(os.path.exists(p) for p in path_list)
        service_name = {"whatsapp": "WhatsApp", "calendar": "Calendar", "mail": "Gmail", "telegram": "Telegram"}.get(key, key.capitalize())
        
        if not exists:
            already_logged_out.append(service_name)
            continue

        all_deleted = True
        for item_path in path_list:
            if os.path.exists(item_path):
                if not safe_delete(item_path):
                    all_deleted = False
                    break
        
        if all_deleted:
            services_logged_out.append(service_name)
        else:
            failed_services.append(service_name)
            
    if already_logged_out:
        logger.info(f"Already logged out: {', '.join(already_logged_out)}")
    if services_logged_out:
        logger.info(f"Successfully logged out: {', '.join(services_logged_out)}")
    if failed_services:
        logger.warning(f"Failed to logout completely (files in use): {', '.join(failed_services)}")

def login_service(service: str):
    service_name_map = {"whatsapp": "WhatsApp", "telegram": "Telegram", "mail": "Gmail", "calendar": "Google Calendar"}
    svc_name = service_name_map.get(service, service.capitalize())

    if service in CRED_PATHS and os.path.exists(CRED_PATHS[service]):
        if not get_user_confirmation(f"{svc_name} is already logged in. Do you want to overwrite the existing session?"):
            logger.info(f"Skipping {svc_name} login.")
            return

    if service == "whatsapp":
        baileys_dir = os.path.join(PROJECT_ROOT, "tools", "Messanger", "whatsapp", "BaileysServer")
        script_path = os.path.join(baileys_dir, "baileys_service.js")
        if not os.path.exists(script_path):
            logger.error("WhatsApp login service script not found.")
            return
            
        logger.info("Starting WhatsApp login. Scan the QR code from the popup window.")
        logger.info("Press Ctrl+C after scanning to complete the process.")
        try:
            subprocess.run(["node", script_path], cwd=baileys_dir, check=True)
            logger.info("WhatsApp login process finished successfully.")
        except FileNotFoundError:
            logger.error("Node.js is not installed or not in the system PATH. Please install Node.js to use WhatsApp.")
        except subprocess.CalledProcessError as e:
            logger.error(f"WhatsApp login process failed with exit code {e.returncode}.")
        except KeyboardInterrupt:
            logger.info("WhatsApp login process cancelled by the user.")
        except Exception as e:
            logger.error(f"WhatsApp login encountered an unexpected error: {e}")
            
    elif service == "telegram":
        temp_script_path = None
        try:
            logger.info("Initializing Telegram Interactive Setup...")
            auth_script = f"""
import os, sys, asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneNumberInvalidError
from telethon.utils import get_display_name
from dotenv import load_dotenv
import logging

logging.getLogger('telethon').setLevel(logging.CRITICAL)

PROJECT_ROOT = r"{PROJECT_ROOT}"
SESSION_DIR = os.path.join(PROJECT_ROOT, "Data", "SessionCookies")
os.makedirs(SESSION_DIR, exist_ok=True)
SESSION_FILE = os.path.join(SESSION_DIR, "jarvis_telegram_session")

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

async def do_login():
    print('\\n' + '='*65)
    print(' 📱 \033[1;36mJARVIS TELEGRAM SECURE AUTHENTICATION\033[0m')
    print('='*65)
    
    if not API_ID or not API_HASH:
        print(' ❌ \033[1;31mERROR: TELEGRAM_API_ID or TELEGRAM_API_HASH missing in the .env file\033[0m')
        print('='*65 + '\\n')
        return

    client = TelegramClient(SESSION_FILE, int(API_ID), API_HASH)
    await client.connect()
    
    if not await client.is_user_authorized():
        print(' 💡 \033[1;33mTIP: You MUST include your country code (e.g., +919876543210)\033[0m')
        print('-'*65)
        phone = input(' 📞 Enter Phone Number : ').strip()
        
        if not phone.startswith('+'):
            print(' ⚠️ \033[1;33mWarning: Country code missing! This might cause an error.\033[0m')
            
        try:
            await client.send_code_request(phone)
            print(' 📩 \033[1;32mOTP sent successfully! Please check your Telegram app.\033[0m')
            code = input(' 🔑 Enter OTP Code     : ').strip()
            
            try:
                await client.sign_in(phone, code)
            except SessionPasswordNeededError:
                print('\\n 🔐 \033[1;33mTwo-Step Verification (2FA) is enabled.\033[0m')
                password = input(' 🔑 Enter 2FA Password : ').strip()
                await client.sign_in(password=password)
                
        except PhoneNumberInvalidError:
            print('\\n ❌ \033[1;31mERROR: Invalid Phone Number! Did you forget the country code?\033[0m')
            await client.disconnect()
            print('='*65 + '\\n')
            return
        except Exception as e:
            print(f'\\n ❌ \033[1;31mAUTHENTICATION FAILED: {{e}}\033[0m')
            await client.disconnect()
            print('='*65 + '\\n')
            return

    me = await client.get_me()
    name = get_display_name(me)
    print(f'\\n ✅ \033[1;32mSUCCESS: Logged in successfully as {{name}}!\033[0m')
    print(' 📁 Session securely saved to: Data/SessionCookies/')
    print('='*65 + '\\n')
    
    try:
        await client.send_message('me', '🤖 **Jarvis Telegram Session Authenticated Successfully!**')
    except:
        pass
        
    await client.disconnect()

if __name__ == '__main__':
    asyncio.run(do_login())
"""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
                f.write(auth_script)
                temp_script_path = f.name
            
            subprocess.run([sys.executable, temp_script_path], check=True)
            logger.info("Telegram login process finished successfully.")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Telegram login process failed with exit code {e.returncode}.")
        except KeyboardInterrupt:
            logger.info("Telegram login process cancelled by the user.")
        except Exception as e:
            logger.error(f"Telegram login encountered an unexpected error: {e}")
        finally:
            if temp_script_path and os.path.exists(temp_script_path):
                os.remove(temp_script_path)
            
    elif service == "mail":
        try:
            from tools.Messanger.email_manager import authenticate_gmail
            logger.info("Starting Gmail login. The browser will open for authentication.")
            service_obj = authenticate_gmail(interactive=True)
            if service_obj:
                logger.info("Gmail login successful.")
            else:
                logger.error("Gmail login failed or timed out.")
        except ImportError as e:
            logger.error(f"Required module missing for Gmail login: {e}")
        except Exception as e:
            logger.error(f"Gmail login encountered an unexpected error: {e}")
            
    elif service == "calendar":
        try:
            from tools.Calendar.CalendarTool import authenticate_calendar
            logger.info("Starting Google Calendar login. The browser will open for authentication.")
            service_obj, status = authenticate_calendar(interactive=True)
            if service_obj:
                logger.info("Calendar login successful.")
            else:
                logger.error("Calendar login failed.")
        except ImportError as e:
            logger.error(f"Required module missing for Google Calendar login: {e}")
        except Exception as e:
            logger.error(f"Calendar login encountered an unexpected error: {e}")
    else:
        logger.error(f"Unknown service specified: {service}")

def show_help_menu():
    help_text = """
====================================================================
                        JARVIS HELP MENU
====================================================================

USAGE:
    jarvis                     Start Jarvis AI Voice Assistant
    jarvis --help              Show this help menu

LOGIN COMMANDS (Jarvis must be OFF):
    jarvis login --whatsapp    Login to WhatsApp
    jarvis login --telegram    Login to Telegram
    jarvis login --mail        Login to Gmail
    jarvis login --calendar    Login to Google Calendar
    jarvis login --all         Login to all services

LOGOUT COMMANDS (Jarvis must be OFF):
    jarvis logout --whatsapp   Logout from WhatsApp
    jarvis logout --telegram   Logout from Telegram
    jarvis logout --mail       Logout from Gmail
    jarvis logout --calendar   Logout from Google Calendar
    jarvis logout --all        Logout from all services

TELEGRAM REMOTE BOT:
    jarvis bot --activate      Setup and activate the Remote Telegram Bot
    jarvis bot --deactivate    Revoke the token and stop the remote bot
    jarvis bot --status        Check if the remote bot is active

MEMORY & RESET COMMANDS (Jarvis must be OFF):
    jarvis memory --clear      Clear Jarvis memory and chat history
    jarvis reset --hard        Factory reset (clear memory and log out all services)

====================================================================
"""
    logger.info(help_text)

def handle_cli_commands():
    args = [arg.lower() for arg in sys.argv[1:]]
    if not args:
        return False
        
    dev_flags = {"test_jarvis", "no_wake"}
    non_dev_args = [a for a in args if a not in dev_flags and not a.startswith("voice=")]
    
    if not non_dev_args:
        return False
        
    if any(h in non_dev_args for h in ("help", "--help", "-h")):
        show_help_menu()
        return True
        
    subcommands = {"logout", "memory", "reset", "login", "bot"}
    has_valid_subcommand = any(arg in subcommands for arg in non_dev_args)
    
    if not has_valid_subcommand:
        alias_map = {
            "--clear": "jarvis memory --clear",
            "-c": "jarvis memory --clear",
            "clear": "jarvis memory --clear",
            "mem": "jarvis memory --clear",
            "lgout": "jarvis logout --all",
            "log": "jarvis logout --all",
            "signout": "jarvis logout --all",
            "purge": "jarvis reset --hard",
            "factory": "jarvis reset --hard",
            "--hard": "jarvis reset --hard"
        }
        logger.error("Invalid command. Type 'jarvis --help' to view the available commands.")
        for arg in non_dev_args:
            if arg in alias_map:
                logger.info(f"Did you mean: '{alias_map[arg]}'?")
                break
        return True

    if "bot" in non_dev_args:
        token_path = os.path.join(PROJECT_ROOT, "Data", "SessionCookies", "telegram_bot_token.enc")
        
        if "--activate" in non_dev_args or "activate" in non_dev_args:
            if os.path.exists(token_path):
                try:
                    data = load_decrypted_token(token_path)
                    if data:
                        bot_username = data.get("bot_username", "Unknown")
                        if not get_user_confirmation(f"A Remote Bot (@{bot_username}) is already active. Do you want to replace it?"):
                            logger.info("Bot activation skipped.")
                            return True
                except Exception:
                    pass

            logger.info("Telegram Remote Bot Activation")
            token = input("Enter the Telegram Bot Token (from @BotFather): ").strip()
            if not token:
                logger.error("The token cannot be empty!")
                return True
                
            try:
                logger.info("Verifying the Bot Token with the Telegram API...")
                res = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=8)
                if res.status_code == 200:
                    try:
                        bot_data = res.json().get("result", {})
                    except json.JSONDecodeError:
                        logger.error("Invalid response format received from the Telegram server.")
                        return True
                        
                    bot_username = bot_data.get("username", "Unknown")
                    bot_name = bot_data.get("first_name", "Jarvis Bot")
                    
                    os.makedirs(SESSION_DIR, exist_ok=True)
                    save_encrypted_token({
                        "token": token,
                        "bot_name": bot_name,
                        "bot_username": bot_username,
                        "active": True
                    }, token_path)
                        
                    logger.info(f"SUCCESS: Bot @{bot_username} ({bot_name}) is now activated!")
                    logger.info("The Remote Bot Service will automatically start when Jarvis is launched.")
                else:
                    logger.error("Invalid Token! Telegram API authentication failed.")
            except requests.exceptions.RequestException as e:
                logger.error(f"A connection error occurred while verifying the token: {e}")
                
        elif any(k in non_dev_args for k in ["--deactivate", "--revoke", "--delete", "deactivate", "revoke", "delete"]):
            if safe_delete(token_path):
                logger.info("Telegram Remote Bot deactivated and the token was revoked successfully.")
            else:
                logger.warning("No active Telegram Bot configuration was found.")
                
        elif "--status" in non_dev_args or "status" in non_dev_args:
            if os.path.exists(token_path):
                try:
                    data = load_decrypted_token(token_path)
                    if data:
                        logger.info("Bot Status : ACTIVE")
                        logger.info(f"Bot Name   : {data.get('bot_name')}")
                        logger.info(f"Username   : @{data.get('bot_username')}")
                    else:
                        raise ValueError("Decryption failed")
                except Exception:
                    logger.warning("Bot Status : Active (However, the information file is corrupted or the encryption key is missing)")
            else:
                logger.info("Bot Status : INACTIVE (Not Configured)")
        else:
            logger.warning("Usage: jarvis bot --activate | jarvis bot --deactivate | jarvis bot --status")
            
        return True

    if is_jarvis_running():
        logger.error("Jarvis is currently running! Please stop Jarvis first before executing CLI setup commands.")
        sys.exit(1)
        
    logger.info("Executing command...")
    
    if "login" in non_dev_args:
        services = []
        if "--whatsapp" in non_dev_args: services.append("whatsapp")
        if "--telegram" in non_dev_args: services.append("telegram")
        if "--mail" in non_dev_args: services.append("mail")
        if "--calendar" in non_dev_args: services.append("calendar")
        if "--all" in non_dev_args:
            services = ["whatsapp", "telegram", "mail", "calendar"]
            
        if not services:
            logger.warning("Please specify a service: --whatsapp, --telegram, --mail, --calendar, or --all")
            logger.info("Type 'jarvis --help' for usage details.")
        else:
            for svc in services:
                login_service(svc)
                
    if "logout" in non_dev_args:
        targets = []
        if "--whatsapp" in non_dev_args: targets.append("whatsapp")
        if "--telegram" in non_dev_args: targets.append("telegram")
        if "--mail" in non_dev_args: targets.append("mail")
        if "--calendar" in non_dev_args: targets.append("calendar")
        if "--all" in non_dev_args:
            targets = ["whatsapp", "telegram", "mail", "calendar"]
            
        if not targets:
            logger.warning("Please specify a service: --whatsapp, --telegram, --mail, --calendar, or --all")
            logger.info("Type 'jarvis --help' for usage details.")
        else:
            deleteSessionCookies(*targets)
            
    if "memory" in non_dev_args:
        if "--clear" in non_dev_args or "--purge" in non_dev_args:
            if get_user_confirmation("Are you sure you want to clear Jarvis's memory? This will delete past context."):
                deleteMemory()
            else:
                logger.info("Memory clear operation aborted.")
        else:
            logger.warning("Use 'jarvis memory --clear' to clear the memory.")
            logger.info("Type 'jarvis --help' for usage details.")
            
    if "reset" in non_dev_args:
        if "--hard" in non_dev_args:
            if get_user_confirmation("WARNING: This will factory reset Jarvis (clear all memory and log out all services). Are you absolutely sure?"):
                logger.info("Factory reset is in progress...")
                deleteMemory()
                deleteSessionCookies("whatsapp", "telegram", "mail", "calendar")
                token_path = os.path.join(PROJECT_ROOT, "Data", "SessionCookies", "telegram_bot_token.enc")
                safe_delete(token_path)
                logger.info("Factory reset completed successfully.")
            else:
                logger.info("Factory reset operation aborted.")
        else:
            logger.warning("Use 'jarvis reset --hard' to perform a factory reset.")
            logger.info("Type 'jarvis --help' for usage details.")
            
    return True