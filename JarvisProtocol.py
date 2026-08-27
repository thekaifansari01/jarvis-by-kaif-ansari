import sys
import os
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv
from core.logger.logger import logger
from core.security import save_encrypted_token

load_dotenv()

def handle_protocol(url):
    if not url.lower().startswith("jarvis://"):
        logger.error(f"Invalid protocol scheme detected in URL: {url}")
        return

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        session_id = query_params.get('session_id', [None])[0]
        service = query_params.get('service', ['unknown'])[0]

        if not session_id:
            logger.error("The 'session_id' parameter is missing from the provided URL.")
            return

        api_base = os.getenv('API_BASE_URL', '').rstrip('/')
        if not api_base:
            logger.error("'API_BASE_URL' is not configured in the environment variables.")
            return

        exchange_url = f"{api_base}/api/oauth/exchange"
        response = requests.post(
            exchange_url,
            json={'session_id': session_id},
            timeout=10
        )

        if response.status_code != 200:
            logger.error(f"Failed to exchange session ID for token. HTTP Status Code: {response.status_code}")
            logger.error(f"Response Payload: {response.text}")
            return

        tokens = response.json()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        cookies_dir = os.path.join(base_dir, "Data", "SessionCookies")
        os.makedirs(cookies_dir, exist_ok=True)

        if service == "calendar":
            token_file = "calendar_token.enc"
        else:
            token_file = "token.enc"

        save_path = os.path.join(cookies_dir, token_file)

        save_encrypted_token(tokens, save_path)

        logger.info(f"SUCCESS: OAuth token for '{service}' was successfully retrieved and saved securely.")
        logger.info(f"File Path: {save_path}")

    except Exception as e:
        logger.error(f"An unexpected exception occurred during token processing. Details: {e}")

if __name__ == "__main__":
    logger.info("Initializing Jarvis Protocol Handler...")
    if len(sys.argv) > 1:
        jarvis_url = sys.argv[1]
        handle_protocol(jarvis_url)
    else:
        logger.warning("Script was executed directly without a target URL argument.")

    input("\nPress Enter to exit...")