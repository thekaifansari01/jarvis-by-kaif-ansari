import os
import json
import base64
import re
import html
import time
import threading
from google.cloud import pubsub_v1

import tools.Messanger.email_manager as email_manager
from tools.Messanger.email_manager import authenticate_gmail
from Proactive.event_queue import push_proactive_event
from core.logger.logger import logger

PUBSUB_SCOPE = 'https://www.googleapis.com/auth/pubsub'
if PUBSUB_SCOPE not in email_manager.SCOPES:
    email_manager.SCOPES.append(PUBSUB_SCOPE)

from core.security import load_decrypted_token

base_path = os.path.dirname(os.path.abspath(__file__))
project_root = base_path
while os.path.basename(project_root) in ["tools", "Messanger", "core", "brain", "Proactive", "Email"]:
    project_root = os.path.dirname(project_root)
token_path = os.path.join(project_root, 'Data', 'SessionCookies', 'token.enc')

if os.path.exists(token_path):
    try:
        token_data = load_decrypted_token(token_path)
        if token_data and PUBSUB_SCOPE not in token_data.get('scopes', []):
            os.remove(token_path)
    except Exception:
        pass

PROJECT_ID = "jarvisemailmanager"
TOPIC_NAME = f"projects/{PROJECT_ID}/topics/jarvis-email-topic"
SUBSCRIPTION_NAME = f"projects/{PROJECT_ID}/subscriptions/jarvis-email-sub"

_stop_event = threading.Event()
_subscriber = None
_streaming_future = None
_watch_timer = None
_email_service = None
_email_lock = threading.Lock()
_processed_ids = set()
_processed_ids_lock = threading.Lock()
_START_TIME_MS = int(time.time() * 1000)

def stop_email_listener():
    global _streaming_future, _subscriber, _watch_timer
    _stop_event.set()
    if _watch_timer:
        _watch_timer.cancel()
        _watch_timer = None
    if _streaming_future:
        _streaming_future.cancel()
    if _subscriber:
        try:
            _subscriber.close()
        except:
            pass

def _renew_watch():
    global _email_service, _watch_timer
    if _stop_event.is_set():
        return
    try:
        if _email_service:
            body = {'topicName': TOPIC_NAME, 'labelIds': ['INBOX'], 'labelFilterAction': 'include'}
            _email_service.users().watch(userId='me', body=body).execute()
            logger.info("Gmail Watch renewed.")
    except Exception as e:
        logger.warning(f"Watch renewal failed: {e}")
    finally:
        if not _stop_event.is_set():
            _watch_timer = threading.Timer(6 * 24 * 3600, _renew_watch)
            _watch_timer.daemon = True
            _watch_timer.start()

def decode_base64(data_str):
    try:
        data_str += "=" * ((4 - len(data_str) % 4) % 4)
        return base64.urlsafe_b64decode(data_str).decode('utf-8', errors='ignore')
    except Exception:
        return ""

def extract_email_content(service, msg_id, msg):
    payload = msg.get('payload', {})
    headers = payload.get('headers', [])
    sender_name, sender_email, subject = "Unknown", "Unknown", "No Subject"
    for header in headers:
        if header['name'] == 'From':
            from_val = header['value']
            if '<' in from_val:
                sender_name = from_val.split('<')[0].strip()
                sender_email = from_val.split('<')[1].replace('>', '').strip()
            else:
                sender_name, sender_email = from_val, from_val
        if header['name'] == 'Subject':
            subject = header['value']

    plain_text = ""
    html_text = ""
    saved_attachments = []

    media_vault_dir = os.path.join(os.path.expanduser('~'), 'Documents', 'Jarvis', 'MediaVault', 'Email_Attachments')
    os.makedirs(media_vault_dir, exist_ok=True)

    def download_attachment(att_id, filename):
        try:
            att_res = service.users().messages().attachments().get(
                userId='me', messageId=msg_id, id=att_id
            ).execute()
            file_data = base64.urlsafe_b64decode(att_res.get('data', '').encode('UTF-8'))
            safe_filename = re.sub(r'[^\w\-_\. ]', '_', filename)
            timestamp_str = str(int(time.time()))
            final_filename = f"{timestamp_str}_{safe_filename}"
            save_path = os.path.join(media_vault_dir, final_filename)
            with open(save_path, "wb") as f:
                f.write(file_data)
            saved_attachments.append(os.path.abspath(save_path).replace("\\", "/"))
        except Exception as e:
            logger.warning(f"Attachment download error: {e}")

    def traverse_parts(parts):
        nonlocal plain_text, html_text
        for part in parts:
            mime_type = part.get('mimeType', '')
            data = part.get('body', {}).get('data', '')
            filename = part.get('filename', '')
            att_id = part.get('body', {}).get('attachmentId', '')

            if filename and att_id:
                download_attachment(att_id, filename)
            elif mime_type == 'text/plain' and data and not filename:
                plain_text += decode_base64(data) + "\n"
            elif mime_type == 'text/html' and data and not filename:
                html_text += decode_base64(data) + "\n"
            elif 'parts' in part:
                traverse_parts(part['parts'])

    top_mime_type = payload.get('mimeType', '')
    top_data = payload.get('body', {}).get('data', '')
    top_filename = payload.get('filename', '')
    top_att_id = payload.get('body', {}).get('attachmentId', '')

    if top_filename and top_att_id:
        download_attachment(top_att_id, top_filename)
    elif top_mime_type == 'text/plain' and top_data:
        plain_text += decode_base64(top_data)
    elif top_mime_type == 'text/html' and top_data:
        html_text += decode_base64(top_data)
    elif 'parts' in payload:
        traverse_parts(payload['parts'])

    final_body = plain_text.strip()
    if not final_body and html_text:
        clean = re.sub(r'<style.*?>.*?</style>', '', html_text, flags=re.IGNORECASE|re.DOTALL)
        clean = re.sub(r'<script.*?>.*?</script>', '', clean, flags=re.IGNORECASE|re.DOTALL)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        clean = html.unescape(clean)
        clean = re.sub(r' {2,}', ' ', clean)
        clean = re.sub(r'\n\s*\n', '\n', clean)
        final_body = clean.strip()
    if not final_body:
        final_body = msg.get('snippet', 'No readable text found in this email.')

    return sender_name, sender_email, subject, final_body, saved_attachments, msg_id

def get_all_unread_emails(service, start_time_ms, max_results=10):
    try:
        results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD'], maxResults=max_results).execute()
        messages = results.get('messages', [])
        emails = []
        for msg in messages:
            msg_id = msg['id']
            full_msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            internal_date = int(full_msg.get('internalDate', 0))
            if internal_date < start_time_ms:
                continue
            name, email, sub, body, saved_attachments, msg_id = extract_email_content(service, msg_id, full_msg)
            emails.append((name, email, sub, body, saved_attachments, msg_id))
        return emails
    except Exception as e:
        logger.warning(f"Error fetching unread emails: {e}")
        return []

def mark_as_read(service, msg_id):
    try:
        service.users().messages().modify(userId='me', id=msg_id, body={'removeLabelIds': ['UNREAD']}).execute()
    except Exception as e:
        logger.warning(f"Failed to mark email {msg_id} as read: {e}")

def start_gmail_watch():
    global _email_service, _watch_timer
    try:
        service = authenticate_gmail(interactive=False)
        if not service:
            return None
        body = {'topicName': TOPIC_NAME, 'labelIds': ['INBOX'], 'labelFilterAction': 'include'}
        response = service.users().watch(userId='me', body=body).execute()
        logger.info(f"Gmail Watch Active! History ID: {response.get('historyId')}")
        _email_service = service
        if _watch_timer:
            _watch_timer.cancel()
        _watch_timer = threading.Timer(6 * 24 * 3600, _renew_watch)
        _watch_timer.daemon = True
        _watch_timer.start()
        return service
    except Exception as e:
        logger.warning(f"Watch setup failed: {e}")
        return None

def listen_for_emails():
    global _subscriber, _streaming_future
    service = start_gmail_watch()
    if not service:
        return

    logger.info("Jarvis Universal Email Listener connected to Proactive Queue...")

    def process_notification(message):
        try:
            message.ack()
            with _email_lock:
                emails = get_all_unread_emails(service, _START_TIME_MS)
            for name, email, sub, body, saved_attachments, msg_id in emails:
                if _stop_event.is_set():
                    break
                with _processed_ids_lock:
                    if msg_id in _processed_ids:
                        continue
                    _processed_ids.add(msg_id)
                mark_as_read(service, msg_id)
                logger.info(f"Email from: {name} ({email}) | Subject: {sub}")
                if saved_attachments:
                    logger.info(f"Attachments: {', '.join(saved_attachments)}")
                event_data = f"Email from: {name} ({email})\nSubject: {sub}\nBody: {body}"
                if saved_attachments:
                    att_str = ", ".join(saved_attachments)
                    event_data += f"\n[Attachments Saved]: {att_str}"
                push_proactive_event("Gmail", event_data)
        except Exception as e:
            logger.error(f"Error processing notification: {e}")

    try:
        subscriber = pubsub_v1.SubscriberClient(credentials=service._http.credentials)
        _subscriber = subscriber
        streaming_pull_future = subscriber.subscribe(SUBSCRIPTION_NAME, callback=process_notification)
        _streaming_future = streaming_pull_future

        while not _stop_event.is_set():
            try:
                streaming_pull_future.result(timeout=1)
            except TimeoutError:
                continue
            except Exception as e:
                if not _stop_event.is_set():
                    logger.warning(f"Streaming error: {e}")
                break

    except KeyboardInterrupt:
        logger.info("Listener stopped.")
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        if _streaming_future:
            _streaming_future.cancel()
        if _subscriber:
            try:
                _subscriber.close()
            except:
                pass
        if _watch_timer:
            _watch_timer.cancel()