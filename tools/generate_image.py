import os
import time
import base64
import requests
from PIL import Image
from io import BytesIO
from together import Together
from dotenv import load_dotenv
from modules.logger import logger
from modules.voice.tts import speak 

# ⚡ NAYA IMPORT: Workspace manager ko import kiya
from modules.workspace import workspace 

# --- SETUP ---
load_dotenv()

# Together AI Setup (For Fast Flux Generation)
VISION_API_KEY = os.getenv("VISION_API_KEY")
together_client = Together(api_key=VISION_API_KEY) if VISION_API_KEY else None

def image_to_base64(image_path):
    """Image ko base64 mein convert karta hai (Editing ke liye)"""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')

# --- ENGINE 1: FLUX (Together AI) for Generation ---
def generate_flux(prompt, filename):
    if not together_client:
        logger.error("VISION_API_KEY nahi mila. .env file check karein!")
        return None

    logger.info(f"Jarvis is generating NEW image with FLUX: {prompt}")
    try:
        response = together_client.images.generate(
            model="black-forest-labs/FLUX.1-schnell",
            prompt=prompt,
            steps=4,
            response_format="b64_json"
        )
        image_data = base64.b64decode(response.data[0].b64_json)
        img = Image.open(BytesIO(image_data))
        
        # 📁 NAYA LOGIC: Workspace mein dynamic naam se save karna
        safe_filename = f"{filename}.png" if not filename.endswith(".png") else filename
        save_path = workspace.creations_dir / safe_filename
        
        img.save(save_path)
        img.show() # Automatically screen par dikhayega
        
        # 📝 LEDGER UPDATE: Registry mein entry daalna
        workspace.add_file_record(safe_filename, "Creations", f"Generated image. Prompt: {prompt}")
        
        logger.info(f"Generation Complete! Saved at: {save_path}")
        return str(save_path)
    except Exception as e:
        logger.error(f"FLUX Error: {e}")
        return None

# --- ENGINE 2: AI HORDE for Editing ---
def edit_via_horde(prompt, source_image_path, new_filename):
    """AI Horde use karega editing ke liye with Clean Terminal UI"""
    url = "https://aihorde.net/api/v2/generate/async"
    headers = {"apikey": "0000000000", "Content-Type": "application/json"}

    logger.info(f"Jarvis is EDITING image via AI Horde: {prompt}")
    
    payload = {
        "prompt": f"{prompt} ### blurry, low quality, distorted, grainy",
        "source_image": image_to_base64(source_image_path),
        "source_processing": "img2img",
        "models": ["AlbedoBase XL (SDXL)"],
        "params": {
            "steps": 25,
            "width": 1024,
            "height": 1024,
            "denoising_strength": 0.65,
            "cfg_scale": 7
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 202: 
            logger.error("AI Horde server rejected the request.")
            return None
        
        task_id = response.json().get("id")
        status_url = f"https://aihorde.net/api/v2/generate/status/{task_id}"
        
        first_time_notified = False 

        while True:
            time.sleep(4)
            try:
                status_res = requests.get(status_url).json()
            except:
                continue 
            
            if status_res.get("done"):
                img_url = status_res["generations"][0]["img"]
                img_res = requests.get(img_url)
                img = Image.open(BytesIO(img_res.content))
                
                # 📁 NAYA LOGIC: Edited image ko naye naam se save karna
                safe_filename = f"{new_filename}.png" if not new_filename.endswith(".png") else new_filename
                save_path = workspace.creations_dir / safe_filename
                
                img.save(save_path)
                
                print("\n") # Line break for clean terminal
                img.show()
                
                # 📝 LEDGER UPDATE: Purani image ka link naye naam ke sath
                source_name = os.path.basename(source_image_path)
                workspace.add_file_record(safe_filename, "Creations", f"Edited from {source_name}. Prompt: {prompt}")
                
                # Success Voice Update
                success_msg = "Sir, image successfully edit ho gayi hai. Aap screen par dekh sakte hain."
                logger.info(f"Editing Complete! Saved successfully at {save_path}.")
                speak(success_msg) 
                
                return str(save_path)
            
            wait_time = status_res.get('wait_time', 0)
            queue_pos = status_res.get('queue_position', 0)

            if not first_time_notified and wait_time > 0:
                minutes = wait_time // 60
                seconds = wait_time % 60
                
                if minutes > 0 and seconds > 0:
                    time_str = f"{minutes} minute aur {seconds} second"
                elif minutes > 0 and seconds == 0:
                    time_str = f"{minutes} minute"
                else:
                    time_str = f"{seconds} second"
                
                notification = f"Sir, image ko edit karne mein lagbhag {time_str} lagenge. Main background mein kaam kar raha hoon."
                speak(notification) 
                first_time_notified = True
            
            
    except Exception as e:
        print("\n") 
        logger.error(f"Horde Error: {e}")
        return None

# --- MAIN ROUTER FOR JARVIS ---
def handle_image_command(action_type, prompt, filename=None, target_file=None):
    """
    Jarvis is function ko call karega.
    action_type: 'generate' ya 'edit'
    prompt: User ka diya gaya prompt
    filename: Nayi image ka naam (generate/edit dono ke baad save karne ke liye)
    target_file: Purani image ka naam jise edit karna hai
    """
    # Fallback filename agar LLM dena bhool jaye
    if not filename:
        filename = f"image_{int(time.time())}"

    if action_type == "generate":
        return generate_flux(prompt, filename)
        
    elif action_type == "edit":
        if not target_file:
            logger.warning("Edit karne ke liye target_file ka naam nahi mila.")
            speak("Sir, mujhe samajh nahi aaya ki konsi image edit karni hai. Kripya naam batayein.")
            return None
            
        # Workspace Creations folder mein target file dhoondhna
        safe_target = f"{target_file}.png" if not target_file.endswith(".png") else target_file
        source_image_path = workspace.creations_dir / safe_target
        
        if not source_image_path.exists():
            logger.warning(f"File nahi mili: {source_image_path}")
            speak(f"Sir, mujhe '{safe_target}' naam ki koi image workspace mein nahi mili.")
            return None
            
        return edit_via_horde(prompt, source_image_path, filename)
        
    else:
        logger.error(f"Unknown image action: {action_type}")
        return None