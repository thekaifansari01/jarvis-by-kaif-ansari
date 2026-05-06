import os
import json
import logging
import requests
from twilio.rest import Client
from dotenv import load_dotenv
from PIL import Image  # ⚡ Added for Image Compression

# Load environment variables
load_dotenv()

# Twilio Credentials from .env
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_FROM_NUMBER")

# Path to your contacts JSON file
CONTACTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Data", "contacts.json")

def load_contacts():
    """Load the contact book from JSON file."""
    if not os.path.exists(CONTACTS_FILE):
        logging.warning("⚠️ contacts.json file nahi mili Data folder mein!")
        return {}
    with open(CONTACTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def compress_image_for_upload(file_path: str) -> str:
    """ 
    ⚡ AUTO-COMPRESSION ENGINE:
    Badi images (jaise 8K FLUX) ko upload se pehle chhota karta hai.
    Isse upload 10x fast hota hai aur timeout ka error nahi aata.
    """
    valid_exts = ['.png', '.jpg', '.jpeg', '.webp']
    ext = os.path.splitext(file_path)[1].lower()
    
    # Agar image nahi hai (jaise PDF), toh direct return kar do
    if ext not in valid_exts:
        return file_path

    try:
        img = Image.open(file_path)
        
        # PNG (RGBA) ko JPG (RGB) mein convert karna zaroori hai size kam karne ke liye
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Image ko max 1920x1920 (1080p HD) tak limit karna (Aspect ratio maintain rahega)
        max_size = (1920, 1920)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Temporary compressed file banana
        temp_compressed_path = os.path.join(os.path.dirname(file_path), "temp_compressed_upload.jpg")
        
        # 75% Quality par save karna (Human eye ko difference nahi dikhega par size MBs se KBs mein aa jayega)
        img.save(temp_compressed_path, "JPEG", optimize=True, quality=75)
        
        original_size = os.path.getsize(file_path) / (1024 * 1024)
        compressed_size = os.path.getsize(temp_compressed_path) / (1024 * 1024)
        logging.info(f"🗜️ Image Compressed: {original_size:.2f}MB -> {compressed_size:.2f}MB")
        
        return temp_compressed_path
    except Exception as e:
        logging.error(f"Compression failed, using original file: {e}")
        return file_path # Fail hua toh original file bhej denge

def upload_for_twilio(file_path: str) -> str:
    """
    Local file ko temporary upload karke direct download link nikalta hai.
    Ye link Twilio ko file WhatsApp par bhejne ke kaam aayega.
    """
    # Step 1: Compress the file before uploading
    upload_path = compress_image_for_upload(file_path)
    
    try:
        url = "https://tmpfiles.org/api/v1/upload"
        with open(upload_path, 'rb') as f:
            files = {'file': f}
            # 🕒 TIMEOUT INCREASED: 15 se 60 seconds kar diya safety ke liye
            response = requests.post(url, files=files, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            original_url = data['data']['url']
            # Twilio ko raw file chahiye hoti hai, isliye /dl/ lagana zaroori hai
            direct_url = original_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
            return direct_url
        else:
            logging.error(f"Upload failed: {response.text}")
            return None
    except Exception as e:
        logging.error(f"Upload error: {e}")
        return None
    finally:
        # 🧹 Cleanup: Upload hone ke baad temporary compressed file ko delete kar do
        if upload_path != file_path and os.path.exists(upload_path):
            try:
                os.remove(upload_path)
            except Exception as e:
                logging.error(f"Temp file cleanup failed: {e}")

def send_whatsapp_message(to_name: str, message: str, attachment_path: str = None) -> str:
    """
    Jarvis ke executor dwara call kiya jane wala main function.
    Ab ye attachment bhi support karta hai!
    """
    if not all([TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM]):
        return "❌ Bhai, Twilio ki keys .env mein set nahi hain."

    # Load contacts and find the target number
    contacts = load_contacts()
    target_number = contacts.get(to_name.lower())

    if not target_number:
        return f"❌ '{to_name}' ka number contacts.json mein nahi mila."

    # Agar attachment hai, toh pehle use upload karo
    media_url = None
    if attachment_path:
        if os.path.exists(attachment_path):
            logging.info(f"🚀 Uploading attachment for Twilio: {attachment_path}")
            media_url = upload_for_twilio(attachment_path)
            if not media_url:
                return f"❌ File upload fail ho gayi, message nahi bheja gaya."
        else:
            return f"❌ Workspace file nahi mili: {attachment_path}"

    try:
        # Initialize Twilio Client
        client = Client(TWILIO_SID, TWILIO_TOKEN)
        
        # Message payload build karna
        message_data = {
            "from_": TWILIO_FROM,
            "body": message,
            "to": target_number
        }
        
        # Agar file upload ho gayi hai, toh uski link media_url mein daal do
        if media_url:
            message_data["media_url"] = [media_url]

        # Send the message
        msg = client.messages.create(**message_data)
        
        status_text = f"✅ WhatsApp message (with attachment)" if media_url else f"✅ WhatsApp message"
        success_text = f"{status_text} successfully sent to {to_name}."
        logging.info(f"{success_text} (SID: {msg.sid})")
        return success_text

    except Exception as e:
        error_text = f"❌ Message bhejne mein error aayi: {e}"
        logging.error(error_text)
        return error_text