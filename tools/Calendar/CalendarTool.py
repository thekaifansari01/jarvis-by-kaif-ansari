import os
import time
import datetime
import webbrowser
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from core.logger.logger import logger
from core.security import load_decrypted_token, save_encrypted_token

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COOKIES_DIR = BASE_DIR / "Data" / "SessionCookies"
COOKIES_DIR.mkdir(parents=True, exist_ok=True)
TOKEN_PATH = COOKIES_DIR / "calendar_token.enc"
SCOPES = ['https://www.googleapis.com/auth/calendar']
DEFAULT_TIMEZONE = 'Asia/Kolkata'

def helper_format_to_iso(time_str: str, default_time_suffix: str = "00:00:00") -> str:
    if not time_str:
        return ""
    time_str = time_str.strip()
    if "T" in time_str and ("+" in time_str or "Z" in time_str):
        return time_str
    try:
        if len(time_str) == 10:
            time_str = f"{time_str} {default_time_suffix}"
        dt = datetime.datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime('%Y-%m-%dT%H:%M:%S+05:30')
    except Exception:
        return ""

def authenticate_calendar(interactive: bool = True):
    logger.info("🔐 Authenticating Google Calendar...")
    creds = None
    if TOKEN_PATH.exists():
        try:
            token_info = load_decrypted_token(str(TOKEN_PATH))
            if token_info:
                creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                logger.debug("✅ Calendar token found.")
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
                logger.info("🔄 Calendar token refreshed.")
            except Exception:
                creds = None
                try:
                    TOKEN_PATH.unlink()
                except Exception:
                    pass

        if (not creds or not creds.valid) and interactive:
            import uuid
            secure_session = str(uuid.uuid4())
            logger.info("🌐 Opening browser for Calendar OAuth...")
            webbrowser.open(f"https://jarvis-os-agent.vercel.app/api/oauth/start?service=calendar&state={secure_session}")
            timeout = 120
            start_time = time.time()
            while time.time() - start_time < timeout:
                if TOKEN_PATH.exists():
                    try:
                        token_info = load_decrypted_token(str(TOKEN_PATH))
                        if token_info:
                            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
                            if creds and creds.valid:
                                logger.info("✅ Calendar OAuth completed.")
                                break
                    except Exception:
                        pass
                time.sleep(3)

    if creds and creds.valid:
        return build('calendar', 'v3', credentials=creds), "Success"
    logger.error("❌ Calendar authentication failed.")
    return None, "Observation: Error -> Authentication timed out or failed."

def create_event(summary: str, start_time: str, end_time: str, description: str = "") -> str:
    logger.info(f"📅 Creating calendar event: {summary}")
    service, auth_status = authenticate_calendar()
    if not service:
        return auth_status

    start_iso = helper_format_to_iso(start_time, "00:00:00")
    end_iso = helper_format_to_iso(end_time, "23:59:59")

    if not start_iso or not end_iso:
        logger.error("Invalid time format in create_event")
        return "Observation: Error -> Invalid time format provided. Use 'YYYY-MM-DD HH:MM:SS' format."

    try:
        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_iso, 'timeZone': DEFAULT_TIMEZONE},
            'end': {'dateTime': end_iso, 'timeZone': DEFAULT_TIMEZONE},
            'reminders': {
                'useDefault': False,
                'overrides': [{'method': 'popup', 'minutes': 15}],
            },
        }
        event = service.events().insert(calendarId='primary', body=event_body).execute()
        logger.info(f"✅ Event created: {summary} (ID: {event.get('id')})")
        return f"Observation: Success -> Event '{summary}' scheduled successfully. Event ID: '{event.get('id')}'."
    except Exception as e:
        logger.error(f"❌ Failed to create event: {e}")
        return f"Observation: API Error while creating event -> {e}"

def check_events(start_time: str = None, end_time: str = None, max_results: int = 10) -> str:
    logger.info("🔍 Checking calendar events...")
    service, auth_status = authenticate_calendar()
    if not service:
        return auth_status

    if not start_time:
        start_iso = datetime.datetime.utcnow().isoformat() + 'Z'
    else:
        start_iso = helper_format_to_iso(start_time, "00:00:00")

    end_iso = helper_format_to_iso(end_time, "23:59:59") if end_time else None

    try:
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_iso,
            timeMax=end_iso,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])
        if not events:
            logger.info("No events found in the given range.")
            return "Observation: Is time range mein calendar mein koi event ya reminder schedule nahi hai."

        output = "Observation: Found these scheduled events:\n"
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            title = event.get('summary', 'Untitled Event')
            e_id = event.get('id')
            output += f"- Event: '{title}' | ID: '{e_id}' | Time: {start}\n"
        logger.info(f"✅ Found {len(events)} events.")
        return output
    except Exception as e:
        logger.error(f"❌ Failed to fetch events: {e}")
        return f"Observation: API Error while fetching events -> {e}"

def delete_event(event_id: str = None, summary_query: str = None) -> str:
    logger.info(f"🗑️ Deleting calendar event (ID: {event_id}, query: {summary_query})")
    service, auth_status = authenticate_calendar()
    if not service:
        return auth_status

    if not event_id and not summary_query:
        logger.warning("Delete called without ID or query.")
        return "Observation: Error -> Deletion requires either an 'event_id' or a 'summary_query'."

    try:
        if event_id:
            service.events().delete(calendarId='primary', eventId=event_id).execute()
            logger.info(f"✅ Deleted event with ID: {event_id}")
            return f"Observation: Success -> Event with ID '{event_id}' has been deleted successfully."

        if summary_query:
            now_iso = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(
                calendarId='primary', timeMin=now_iso, maxResults=50, singleEvents=True
            ).execute()

            events = events_result.get('items', [])
            target_id = None
            matched_title = ""

            for event in events:
                title = event.get('summary', '').lower()
                if summary_query.lower() in title:
                    target_id = event.get('id')
                    matched_title = event.get('summary')
                    break

            if target_id:
                service.events().delete(calendarId='primary', eventId=target_id).execute()
                logger.info(f"✅ Deleted event '{matched_title}' (ID: {target_id})")
                return f"Observation: Success -> Found and deleted the event '{matched_title}' (ID: {target_id}) successfully."
            else:
                logger.warning(f"No future event found with summary containing '{summary_query}'")
                return f"Observation: Error -> '{summary_query}' naam ka koi bhi event aane wale dino mein nahi mila."

    except Exception as e:
        logger.error(f"❌ Failed to delete event: {e}")
        return f"Observation: API Error while deleting event -> {e}"

if __name__ == '__main__':
    auth, stat = authenticate_calendar()