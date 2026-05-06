import os
import time
import base64
import mimetypes
from email.message import EmailMessage
from datetime import datetime, timedelta
from groq import Groq
from dotenv import load_dotenv

# Google API Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.brain.config import GROQ_EMAIL_SUMMARY_MODEL, EMAIL_SUMMARY_MAX_TOKENS, GROQ_API_KEY

# Voice Import
try:
    from core.voice.tts import speak
except ImportError:
    def speak(text): print(f"🔊 JARVIS SAYS: {text}")

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

SCOPES = ['https://mail.google.com/']

def authenticate_gmail():
    """Google API connection with relative path management."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(base_path, 'credentials.json')
    token_path = os.path.join(base_path, 'token.json')

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print(f"🔐 Gmail Access: Using {credentials_path}")
            if not os.path.exists(credentials_path):
                print(f"❌ Error: credentials.json nahi mili is path par: {credentials_path}")
                return None
                
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

# ==========================================
# 🚀 1. ACTION: SEND EMAIL (WITH ATTACHMENT + FALLBACK)
# ==========================================
def send_email(to_address, subject, body, attachment_path=None):
    """Jarvis ke through kisi ko email bhejna, ab attachments ke saath."""
    
    # 🔧 FIX: Agar attachment path diya gaya hai aur file exist nahi karti, toh fail karo
    if attachment_path and not os.path.exists(attachment_path):
        print(f"❌ Attachment file missing: {attachment_path}")
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
            print(f"📎 Attached file: {os.path.basename(attachment_path)}")

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f"✅ Email sent successfully to {to_address}! ID: {send_message['id']}")
        return True
    except Exception as e:
        print(f"⚠️ Failed to send email: {e}")
        return False

# ==========================================
# 🗑️ 2. ACTION: DELETE EMAIL
# ==========================================
def delete_email(query):
    try:
        service = authenticate_gmail()
        if not service:
            return False
        results = service.users().messages().list(userId='me', q=query, maxResults=1).execute()
        messages = results.get('messages', [])
        
        if not messages:
            print("😶 Koi matching email nahi mila delete karne ke liye.")
            return False

        msg_id = messages[0]['id']
        service.users().messages().trash(userId='me', id=msg_id).execute()
        print(f"🗑️ Email successfully moved to Trash. (Query: {query})")
        return True
    except Exception as e:
        print(f"⚠️ Error deleting email: {e}")
        return False

# ==========================================
# 📡 3. BACKGROUND RADAR (WITH DYNAMIC DATE)
# ==========================================
def summarize_email(sender, subject, snippet):
    if not client:
        return f"Sir, {sender.split('<')[0]} se ek naya mail aaya hai."
    prompt = f"""
    Analyze this email: From: {sender} | Subject: {subject} | Content: {snippet}
    Task: Provide a factual, max 12 words Hinglish summary.
    Rule: If empty or test, just say "Sir, [Sender] se ek test email aaya hai." DO NOT hallucinate.
    """
    try:
        response = client.chat.completions.create(
            model=GROQ_EMAIL_SUMMARY_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=EMAIL_SUMMARY_MAX_TOKENS        )
        return response.choices[0].message.content.strip().replace('"', '')
    except:
        return f"Sir, {sender.split('<')[0]} se ek mail aaya hai."

def check_new_emails():
    try:
        service = authenticate_gmail()
        if not service:
            return
            
        # 🔧 FIX: Dynamic date – last 7 days
        days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y/%m/%d')
        query = f"is:unread after:{days_ago}"
        
        results = service.users().messages().list(userId='me', q=query, labelIds=['INBOX']).execute()
        messages = results.get('messages', [])

        if not messages:
            return

        print(f"📧 [{datetime.now().strftime('%I:%M %p')}] New mail detected...")
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = msg_data['payload']['headers']
            subject = "No Subject"
            sender = "Unknown"
            for header in headers:
                if header['name'] == 'Subject':
                    subject = header['value']
                if header['name'] == 'From':
                    sender = header['value']
            
            snippet = msg_data.get('snippet', '')
            summary = summarize_email(sender, subject, snippet)
            print(f"🗣️  JARVIS: {summary}")
            speak(summary)

            service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['UNREAD']}).execute()
            time.sleep(1)
    except Exception as e:
        print(f"⚠️ Gmail Error: {e}")