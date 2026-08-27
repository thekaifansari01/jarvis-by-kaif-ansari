import os
import json
from cryptography.fernet import Fernet
from core.logger.logger import logger

KEY_FILE = os.path.join(os.path.dirname(__file__), 'secret.key')

def get_or_create_key():
    if not os.path.exists(KEY_FILE):
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as f:
            f.write(key)
    else:
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
    return key

cipher_suite = Fernet(get_or_create_key())

def save_encrypted_token(data: dict, file_path: str):
    try:
        json_data = json.dumps(data).encode('utf-8')
        encrypted_data = cipher_suite.encrypt(json_data)
        with open(file_path, 'wb') as f:
            f.write(encrypted_data)
    except Exception as e:
        logger.error(f"Encryption failed: {e}")

def load_decrypted_token(file_path: str) -> dict:
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'rb') as f:
            encrypted_data = f.read()
        decrypted_data = cipher_suite.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode('utf-8'))
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return None