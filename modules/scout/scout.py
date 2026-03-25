import time
import json
import re
from datetime import datetime
from pathlib import Path

# External and Internal Modules
from modules.logger import logger
from modules.processor import groq_client
from tools.perform_search import search_serpapi
from modules.voice import tts 
from modules.voice.tts import speak

class SmartScout:
    def __init__(self, memory_instance):
        self.memory = memory_instance
        self.history_file = Path("Data/jarvis_memory/scout_smart_history.json")
        self.current_target_index = 0  
        self._init_history()

    def _init_history(self):
        """Initializes the history file if it doesn't exist."""
        if not self.history_file.exists():
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def is_already_told(self, title):
        """Check if this specific news title was already announced recently."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return title in history
        except Exception as e:
            logger.error(f"Error reading scout history: {e}")
            return False

    def save_to_history(self, title):
        """Saves announced title to avoid repetition."""
        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            history[title] = datetime.now().isoformat()
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving scout history: {e}")

    def _filter_scoutable_topics(self, raw_likes):
        """
        🧠 HYBRID UPGRADE: Uses Deep Brain (120B) to accurately filter out instructions 
        and only keep valid, searchable news topics.
        """
        if not raw_likes:
            return []
            
        try:
            prompt = f"""
            Analyze the following list of user preferences: {raw_likes}
            
            TASK: 
            Return ONLY a JSON object containing a list of factual topics, subjects, or entities that can be searched in the news (e.g., "AI", "Space", "Cricket", "Cybersecurity").
            STRICTLY IGNORE all system instructions, conversational preferences, or workflow habits (e.g., "speak in python", "keep it short", "use dark mode", "explain clearly").
            
            Format strictly like this: {{"topics": ["Topic 1", "Topic 2"]}}
            If no valid news topics exist, return: {{"topics": []}}
            """
            
            # ⚡ Using 120B Model here for high accuracy reasoning (Runs only once per cycle)
            response = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "You are a precise data extractor. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"} 
            )
            
            raw_text = response.choices[0].message.content.strip()
            clean_text = re.sub(r'^```json\n|```$', '', raw_text, flags=re.MULTILINE).strip()
            
            parsed = json.loads(clean_text)
            if "topics" in parsed and isinstance(parsed["topics"], list):
                return parsed["topics"]
                
        except Exception as e:
            logger.error(f"Scout Deep Brain Filter Error: {e}")
            # Fallback heuristic if 120B fails
            ignore_words = ["speak", "tell", "answer", "always", "never", "use", "when", "prefer", "explain"]
            return [l for l in raw_likes if len(l.split()) <= 3 and not any(w in l.lower() for w in ignore_words)]

        return []

    def run_scout_cycle(self):
        """Runs search, with Fallback Loop if one topic fails, and respects DND."""
        # 🛡️ DND MODE CHECK: Agar user Technical kaam kar raha hai, toh disturb na karein
        if hasattr(self.memory, 'current_mode') and self.memory.current_mode == "Technical":
            logger.info("🕵️ Scout Paused: User is in Technical Mode (Do Not Disturb).")
            return

        raw_likes = self.memory.preferences.get("likes", [])
        
        # ⚡ 1. 120B Deep Brain filters out workflow instructions, gets real topics
        valid_topics = self._filter_scoutable_topics(raw_likes)
        
        if not valid_topics:
            logger.info("🕵️ Scout Standby: No search-worthy topics found in preferences.")
            return

        # ⚡ 2. The Fallback Loop: Try topics until we find ONE good news item
        start_index = self.current_target_index if self.current_target_index < len(valid_topics) else 0
        topics_to_try = valid_topics[start_index:] + valid_topics[:start_index]
        
        for idx, target in enumerate(topics_to_try):
            logger.info(f"🕵️ Scout scanning topic: {target}...")
            
            # Fetching breaking news
            query = f"{target} breaking news updates {datetime.now().strftime('%d %B %Y')}"
            results = search_serpapi(query, max_results=4) 

            if results:
                for res in results:
                    title = res.get('title')
                    snippet = res.get('snippet')
                    source_date = res.get('date', 'Unknown date')

                    # Filter 1: Duplicate Check
                    if self.is_already_told(title):
                        continue

                    # Filter 2: 70B Fast Brain Freshness Audit
                    decision = self.evaluate_freshness(target, title, snippet, source_date)

                    if "IGNORE" not in decision.upper():
                        # We found good news! Announce, update pointer, and exit the cycle immediately.
                        self.announce(decision, title)
                        # Set pointer to the NEXT topic for the next 15-min run
                        original_idx = valid_topics.index(target)
                        self.current_target_index = (original_idx + 1) % len(valid_topics)
                        return # EXIT THE CYCLE
            
            logger.info(f"🕵️ No fresh news for '{target}'. Checking fallback topic...")

        # If loop finishes without returning, we found NO news for ANY topic.
        logger.info("🕵️ Scout Cycle Complete: No fresh news found across all topics.")
        self.current_target_index = (self.current_target_index + 1) % len(valid_topics)


    def evaluate_freshness(self, target, title, snippet, s_date):
        """⚡ FAST BRAIN: Uses Llama 3.3 70B to quickly confirm freshness and write dialogue."""
        today = datetime.now().strftime("%A, %d %B %Y")
        prompt = f"""
        Today's Date: {today}
        Target Interest: {target}
        News Title: {title}
        Snippet: {snippet}
        Reported Date: {s_date}

        TASK:
        1. If this news is older than 48 hours, or seems like clickbait, or irrelevant to {target}, reply ONLY 'IGNORE'.
        2. If it's fresh and important, write a 1-sentence Hinglish proactive announcement.
        Format: "Sir/Kaif bhai... [Brief news update]"
        """
        try:
            # ⚡ Using 70B Model here for speed since it runs multiple times per cycle
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Scout AI Eval Error: {e}")
            return "IGNORE"

    def announce(self, text, title):
        """Speaks the news only if Jarvis is not busy talking to the user."""
        # Collision Protection: Wait for user interaction to finish
        while tts.is_speaking:
            time.sleep(1)
            
        print(f"\n🔔 [PROACTIVE]: {text}")
        speak(text)
        self.save_to_history(title)
        
        # Memory update so Jarvis knows he told you this
        try:
            self.memory.add_message("CHATBOT", f"[PROACTIVE SCOUT]: {text}")
        except:
            pass