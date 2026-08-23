import os
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import telebot
from core.logger.logger import logger
from core.main.CommandHandler import main_command_processor, is_jarvis_busy

_bot_instance = None
_bot_thread = None
_is_polling = False
_global_executor = None
_global_memory = None

def get_token_path():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "Data", "SessionCookies", "telegram_bot_token.json")

def set_telegram_remote_context(executor: ThreadPoolExecutor, memory):
    global _global_executor, _global_memory
    _global_executor = executor
    _global_memory = memory

def start_telegram_remote_listener():
    global _bot_instance, _bot_thread, _is_polling

    token_path = get_token_path()
    if not os.path.exists(token_path):
        return False

    try:
        with open(token_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            token = data.get("token")
            allowed_chat_id = data.get("allowed_chat_id")

        if not token:
            return False

        if _is_polling and _bot_instance:
            return True

        _bot_instance = telebot.TeleBot(token)
        _is_polling = True

        @_bot_instance.message_handler(commands=['start', 'help'])
        def send_welcome(message):
            msg = "🤖 **Jarvis Remote Controller Bot Active!**\n\nSend any text command to execute on your PC."
            _bot_instance.reply_to(message, msg, parse_mode="Markdown")

        @_bot_instance.message_handler(func=lambda message: True)
        def handle_remote_command(message):
            if allowed_chat_id and str(message.chat.id) != str(allowed_chat_id):
                _bot_instance.reply_to(message, "⛔ Unauthorized access denied.")
                return

            cmd_text = message.text.strip() if message.text else ""
            if not cmd_text:
                return

            logger.info(f"Remote Telegram Command: '{cmd_text}' from Chat ID: {message.chat.id}")

            if is_jarvis_busy():
                _bot_instance.reply_to(message, "Jarvis is currently busy. Added to live feedback queue.")
                if _global_memory and hasattr(_global_memory, 'add_live_feedback'):
                    _global_memory.add_live_feedback(cmd_text)
            else:
                _bot_instance.reply_to(message, f"Executing: `{cmd_text}`", parse_mode="Markdown")
                if _global_executor and _global_memory:
                    _global_executor.submit(main_command_processor, cmd_text, _global_executor, _global_memory, "telegram_bot")

        def _poll_worker():
            global _is_polling
            logger.info("Telegram Remote Bot Service started listening...")
            retries = 0
            while _is_polling:
                try:
                    _bot_instance.infinity_polling(timeout=20, long_polling_timeout=10)
                    break
                except Exception as e:
                    error_msg = str(e).lower()
                    if "polling exited" in error_msg or "break infinity polling" in error_msg:
                        break
                    retries += 1
                    logger.error(f"Telegram Bot Polling Error: {e}. Retry {retries}/5.")
                    if retries >= 5:
                        logger.error("Max retries reached. Stopping Telegram polling.")
                        _is_polling = False
                        break
                    time.sleep(5)
            _is_polling = False
            logger.info("Telegram polling stopped.")

        _bot_thread = threading.Thread(target=_poll_worker, daemon=True)
        _bot_thread.start()
        return True

    except Exception as e:
        logger.error(f"Failed to start Telegram Remote Bot: {e}")
        _is_polling = False
        return False

def stop_telegram_remote_listener():
    global _bot_instance, _is_polling
    if _bot_instance and _is_polling:
        try:
            _bot_instance.stop_bot()
            _bot_instance.stop_polling()
            logger.info("Telegram Remote Bot listener stopped.")
        except Exception as e:
            logger.error(f"Error stopping Telegram Bot: {e}")
        finally:
            _is_polling = False
            _bot_instance = None

def is_telegram_remote_running() -> bool:
    global _is_polling
    return _is_polling