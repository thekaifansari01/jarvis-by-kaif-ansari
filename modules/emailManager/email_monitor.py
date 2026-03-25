import os
import time
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv

# Google API Imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Voice Import
try:
    from modules.voice.tts import speak
except ImportError:
    def speak(text): print(f"🔊 JARVIS SAYS: {text}")

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# SCOPES for Gmail (Read, Write, and Modify)
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def authenticate_gmail():
    """Google API connection with token management."""
    creds = None
    if os.path.exists('modules/emailManager/token.json'):
        creds = Credentials.from_authorized_user_file('modules/emailManager/token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("🔐 Gmail Access: Check your browser to authorize Jarvis...")
            flow = InstalledAppFlow.from_client_secrets_file('modules/emailManager/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def summarize_email(sender, subject, snippet):
    """Smart 1-line summary using Groq AI."""
    if not client: 
        return f"Sir, {sender.split('<')[0]} se ek naya mail aaya hai: {subject}"
    
    prompt = f"""
    Analyze this email:
    From: {sender}
    Subject: {subject}
    Content: {snippet}
    
    Task: Provide a very short (max 12 words) natural Hinglish summary for Jarvis to speak.
    Example: "Sir, Amazon se aapka refund initiate ho gaya hai."
    Response must be ONLY the sentence.
    """
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6, max_tokens=40
        )
        return response.choices[0].message.content.strip().replace('"', '')
    except:
        return f"Sir, {sender.split('<')[0]} se ek mail aaya hai: {subject}"

def check_new_emails():
    """Radar to check unread emails strictly after 21st March 2026."""
    try:
        service = authenticate_gmail()
        
        # 🔥 FILTER: Unread emails received AFTER March 21, 2026
        # Format in Gmail API: q="after:YYYY/MM/DD"
        query = "is:unread after:2026/03/21"
        
        results = service.users().messages().list(
            userId='me', 
            q=query,
            labelIds=['INBOX']
        ).execute()
        
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
                if header['name'] == 'Subject': subject = header['value']
                if header['name'] == 'From': sender = header['value']
            
            snippet = msg_data.get('snippet', '')

            # 1. AI Summary
            summary = summarize_email(sender, subject, snippet)
            print(f"🗣️  JARVIS: {summary}")
            
            # 2. Voice Output
            speak(summary)

            # 3. Mark as Read (Crucial: to avoid repeating the same mail)
            service.users().messages().modify(
                userId='me', 
                id=msg['id'], 
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
            
            time.sleep(1) # Gap between multiple emails

    except Exception as e:
        print(f"⚠️ Gmail Error: {e}")

# if __name__ == "__main__":
#     print("🚀 Jarvis Email Radar is now monitoring from 21st March 2026 onwards...")
#     while True:
#         check_new_emails()
#         time.sleep(30) # Har 30 second mein check karega