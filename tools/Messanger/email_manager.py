import os
import time
import base64
import mimetypes
import webbrowser
import json
from email.message import EmailMessage
from pathlib import Path
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.logger.logger import logger
from core.security import load_decrypted_token, save_encrypted_token

try:
    from core.voice.tts import speak
except ImportError:
    def speak(text):
        logger.warning(f"TTS not available, speaking via log: {text}")

load_dotenv()

SCOPES = ['https://mail.google.com/', 'https://www.googleapis.com/auth/pubsub']
BASE_DIR = Path(__file__).resolve().parent.parent.parent
COOKIES_DIR = BASE_DIR / "Data" / "SessionCookies"
COOKIES_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = COOKIES_DIR / "token.enc"

def authenticate_gmail(interactive: bool = True):
    logger.info("🔐 Authenticating Gmail...")
    creds = None
    if TOKEN_PATH.exists():
        try:
            token_info = load_decrypted_token(str(TOKEN_PATH))
            if token_info:
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                logger.debug("✅ Gmail token found.")
        except Exception:
            creds = None
            try:
                TOKEN_PATH.unlink()
            except Exception:
                pass

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_encrypted_token(json.loads(creds.to_json()), str(TOKEN_PATH))
                logger.info("🔄 Gmail token refreshed.")
            except Exception:
                creds = None
                try:
                    TOKEN_PATH.unlink()
                except Exception:
                    pass

        if (not creds or not creds.valid) and interactive:
            import uuid
            secure_session = str(uuid.uuid4())
            logger.info("🌐 Opening browser for Gmail OAuth...")
            webbrowser.open(f"https://jarvis-os-agent.vercel.app/api/oauth/start?service=gmail&state={secure_session}")
            timeout = 120
            start_time = time.time()
            while time.time() - start_time < timeout:
                if TOKEN_PATH.exists():
                    try:
                        token_info = load_decrypted_token(str(TOKEN_PATH))
                        if token_info:
                            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                            if creds and creds.valid:
                                logger.info("✅ Gmail OAuth completed.")
                                break
                    except Exception:
                        pass
                time.sleep(3)

    if creds and creds.valid:
        return build('gmail', 'v1', credentials=creds, cache_discovery=False)
    logger.error("❌ Gmail authentication failed.")
    return None

def send_email(to_address, subject, body, attachment_path=None):
    logger.info(f"📧 Sending email to {to_address} | Subject: {subject}")
    if attachment_path and not os.path.exists(attachment_path):
        logger.warning(f"Attachment not found: {attachment_path}")
        return False

    try:
        service = authenticate_gmail()
        if not service:
            return False

        message = EmailMessage()
        message.set_content(body)
        message['To'] = to_address
        message['From'] = 'me'
        message['Subject'] = subject

        if attachment_path and os.path.exists(attachment_path):
            ctype, encoding = mimetypes.guess_type(attachment_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)

            with open(attachment_path, 'rb') as fp:
                message.add_attachment(fp.read(),
                                       maintype=maintype,
                                       subtype=subtype,
                                       filename=os.path.basename(attachment_path))

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        service.users().messages().send(userId="me", body=create_message).execute()
        logger.info(f"✅ Email sent successfully to {to_address}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False

def delete_email(query):
    logger.info(f"🗑️ Attempting to delete email with query: {query}")
    try:
        service = authenticate_gmail()
        if not service:
            return False
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])

        if not messages:
            logger.warning(f"No email found for query: {query}")
            return False

        msg_id = messages[0]['id']
        service.users().messages().trash(userId='me', id=msg_id).execute()
        logger.info(f"✅ Email deleted (trashed) with ID: {msg_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete email: {e}")
        return False

if __name__ == "__main__":
    auth = authenticate_gmail()