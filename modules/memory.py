import json
import os
import hashlib
import re
from datetime import datetime
from pathlib import Path
import cohere
import chromadb
from chromadb.config import Settings
from groq import Groq # ⚡ Imported Groq
from modules.config import COHERE_API_KEY
from modules.logger import logger
from modules.workspace import workspace

class ContextMemory:
    def __init__(self, memory_path="Data/jarvis_memory", rag_base_path="Data/RAG"):
        self.memory_path = Path(memory_path)
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.rag_base_path = Path(rag_base_path)
        self.rag_base_path.mkdir(exist_ok=True)
        
        self.summary_file = self.memory_path / "summary.txt" 
        self.user_bio_file = self.memory_path / "user_bio.json" 
        self.file_hashes_file = self.memory_path / "file_hashes.json"
        self.preferences_file = self.memory_path / "preferences.json"
        self.user_mood_file = self.memory_path / "user_mood.json" # 🎭 NEW: Mood File
        
        self.user_bio = self._load_json(self.user_bio_file, {"name": "User", "facts": []})
        self.file_hashes = self._load_json(self.file_hashes_file, {})
        self.preferences = self._load_json(self.preferences_file, {"likes": []})
        self.user_mood = self._load_json(self.user_mood_file, {"mood_history": []}) # 🎭 NEW: Mood Data
        
        self.current_mode = "General Assistant"
        self.mode_timer = datetime.now()
        
        # 🤖 AI CLIENTS
        self.cohere_client = cohere.Client(COHERE_API_KEY)
        self.groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        
        # 🔥 CHROMADB
        self.chroma_client = chromadb.PersistentClient(path=str(self.memory_path / "chroma_db"))
        self.chat_collection = self.chroma_client.get_or_create_collection(name="chat_history")
        self.rag_collection = self.chroma_client.get_or_create_collection(name="rag_documents")
        
        if self.rag_base_path.exists():
            self._index_rag_files()

    def _load_json(self, file_path, default):
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f: return json.load(f)
            return default
        except Exception as e: return default
    
    def _save_json(self, file_path, data):
        try:
            with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, indent=2)
        except Exception as e: pass

    # 🛑 DO NOT CHANGE: Database mapping relies on this Cohere model
    def get_embedding(self, text, input_type="search_document"):
        if not text or not text.strip(): return None
        try:
            response = self.cohere_client.embed(
                texts=[text],
                model="embed-english-v3.0",
                input_type=input_type
            )
            return response.embeddings[0]
        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    def _smart_chunk_text(self, text, max_chars=600):
        paragraphs = text.split('\n\n')
        chunks, current_chunk = [], ""
        for p in paragraphs:
            if len(current_chunk) + len(p) < max_chars: current_chunk += p + "\n\n"
            else:
                if current_chunk: chunks.append(current_chunk.strip())
                current_chunk = p + "\n\n"
        if current_chunk: chunks.append(current_chunk.strip())
        return chunks if chunks else [text]

    def _get_file_hash(self, file_path):
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f: hasher.update(f.read())
        return hasher.hexdigest()

    def _index_rag_files(self):
        supported_extensions = ['.txt', '.md', '.json', '.py', '.js', '.csv']
        new_hashes, updated = {}, False
        
        for root, _, files in os.walk(self.rag_base_path):
            for file_name in files:
                if any(file_name.endswith(ext) for ext in supported_extensions):
                    file_path = Path(root) / file_name
                    file_hash = self._get_file_hash(file_path)
                    new_hashes[str(file_path)] = file_hash
                    
                    if self.file_hashes.get(str(file_path)) == file_hash: continue 
                        
                    logger.info(f"Indexing file: {file_name}...")
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            if file_path.suffix in ['.py', '.js']:
                                lines = f.readlines()
                                content = "".join([f"Line {idx+1}: {line}" for idx, line in enumerate(lines)])
                            else:
                                content = f.read()
                                
                            if not content.strip(): continue
                            for i, chunk in enumerate(self._smart_chunk_text(content)):
                                embedding = self.get_embedding(chunk, "search_document")
                                if embedding:
                                    self.rag_collection.upsert(ids=[f"{file_name}_chunk_{i}"], embeddings=[embedding], metadatas=[{"file_name": file_name}], documents=[chunk])
                            updated = True
                    except Exception as e: logger.error(f"Error indexing: {e}")
        
        if updated or len(new_hashes) != len(self.file_hashes):
            self.file_hashes = new_hashes
            self._save_json(self.file_hashes_file, self.file_hashes)
            logger.info("RAG Indexing complete.")

    def _track_session_state(self, message):
        msg_lower = message.lower()
        if any(w in msg_lower for w in ["code", "python", "error", "bug"]): self.current_mode = "Technical"
        elif any(w in msg_lower for w in ["joke", "song", "play", "movie"]): self.current_mode = "Casual"
        self.mode_timer = datetime.now()
        if (datetime.now() - self.mode_timer).total_seconds() / 60 > 30: self.current_mode = "General Assistant"

    def _extract_insights_ai(self, message):
        """⚡ UPGRADED: Extracts Bio, Prefs, AND User Mood using 120B with Full Context."""
        if len(message.split()) < 3: return 
            
        # 🕒 1. Fetch recent conversation history from ChromaDB for context
        recent_history = ""
        try:
            if self.chat_collection.count() > 0:
                all_data = self.chat_collection.get()
                docs = [{"role": all_data['metadatas'][i]['role'], "doc": all_data['documents'][i], "time": all_data['metadatas'][i]['timestamp']} for i in range(len(all_data['ids']))]
                docs.sort(key=lambda x: x['time'])
                # Get last 4 messages for context
                recent_history = "\n".join([f"{d['role']}: {d['doc']}" for d in docs[-4:]])
        except Exception as e:
            logger.error(f"Could not fetch history for context: {e}")

        try:
            prompt = f"""Analyze the user's latest message to extract ONLY NEW, high-value personal insights AND their current emotional state.

            🚨 STRICT FILTERS & RULES:
            1. The 30-Day Rule: Will this info (bio/prefs) be useful to know a month from now? If no, DO NOT save it.
            2. The Assistant Rule: Only save things that an AI Assistant needs to know (workflow, major life facts, relationships).
            3. No Duplicates / Update Rule: Review the [EXISTING KNOWLEDGE] block. DO NOT extract facts we already know. Only extract if it's new or a modification to existing info.
            4. Mood Tracker: ALWAYS detect the current emotional 'mood' (e.g., Happy, Tired, Stressed, Excited, Frustrated, Neutral) based on the tone of the user's message and the recent conversation history.

            [EXISTING KNOWLEDGE]
            Known Bio Facts: {[f['text'] for f in self.user_bio.get("facts", [])]}
            Known Preferences: {self.preferences.get("likes", [])}

            [RECENT CONVERSATION HISTORY]
            {recent_history if recent_history else "No recent history."}

            CATEGORIES:
            1. 'bio': Hard, unchanging facts (Name, Profession, City, Goals).
            2. 'prefs': Actionable preferences (Coding style, habits).
            3. 'mood': A single word describing the user's current emotional vibe.

            Return STRICTLY a JSON object. Format: {{"bio": ["new fact 1"], "prefs": ["new pref 1"], "mood": "Tired"}}
            If no NEW bio/prefs meet the filters, return empty arrays but ALWAYS return a mood: {{"bio": [], "prefs": [], "mood": "Neutral"}}
            
            User's Latest Message: "{message}"
            """
            
            response = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "You are a highly analytical memory and sentiment extractor. Output only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            raw_text = response.choices[0].message.content.strip()
            clean_text = re.sub(r'^```json\n|```$', '', raw_text, flags=re.MULTILINE).strip()
            insights = json.loads(clean_text)
            
            updated = False
            mood_updated = False
            
            # 1. Save Bio Facts (Case-insensitive check)
            if insights.get("bio") and len(insights["bio"]) > 0:
                for fact in insights["bio"]:
                    if not any(f["text"].lower() == fact.lower() for f in self.user_bio["facts"]):
                        self.user_bio["facts"].append({"text": fact, "date": datetime.now().isoformat()})
                        updated = True
                if updated: self._save_json(self.user_bio_file, self.user_bio)
            
            # 2. Save Preferences (Case-insensitive check)
            if insights.get("prefs") and len(insights["prefs"]) > 0:
                for pref in insights["prefs"]:
                    if not any(p.lower() == pref.lower() for p in self.preferences["likes"]):
                        self.preferences["likes"].append(pref)
                        updated = True
                if len(self.preferences["likes"]) > 20: self.preferences["likes"] = self.preferences["likes"][-20:]
                if updated: self._save_json(self.preferences_file, self.preferences)
                
            # 🎭 3. Save Mood Timeline (Rolling Window of 10)
            current_mood = insights.get("mood", "Neutral")
            if current_mood and current_mood.lower() != "neutral":
                now = datetime.now()
                mood_entry = {
                    "mood": current_mood.capitalize(),
                    "date": now.strftime("%Y-%m-%d"),
                    "time": now.strftime("%H:%M")
                }
                self.user_mood["mood_history"].append(mood_entry)
                # Keep only the last 10 entries so it doesn't get cluttered
                if len(self.user_mood["mood_history"]) > 10:
                    self.user_mood["mood_history"] = self.user_mood["mood_history"][-10:]
                self._save_json(self.user_mood_file, self.user_mood)
                mood_updated = True
                
            if updated or mood_updated: 
                logger.info(f"🧠 120B AI learned NEW context/mood: {insights}")
                    
        except Exception as e:
            logger.error(f"AI Insights extraction failed: {e}")

    def add_message(self, role, message):
        if not message or not message.strip(): return
        ignore_words = ["ok", "okay", "yes", "no", "thanks", "thank you", "clear", "done", "nice", "cool", "hmm", "acha"]
        if role == "USER" and message.lower().strip() in ignore_words: return

        if role == "USER":
            self._track_session_state(message)
            self._extract_insights_ai(message)

        embedding = self.get_embedding(message, "search_document")
        if not embedding: return

        msg_id = f"msg_{datetime.now().timestamp()}"
        self.chat_collection.add(ids=[msg_id], embeddings=[embedding], metadatas=[{"role": role, "timestamp": datetime.now().isoformat()}], documents=[message])
        
        if self.chat_collection.count() > 50: self._summarize_old_messages()

    def _summarize_old_messages(self):
        try:
            all_data = self.chat_collection.get()
            if len(all_data['ids']) < 30: return

            docs = [{"id": all_data['ids'][i], "doc": all_data['documents'][i], "meta": all_data['metadatas'][i]} for i in range(len(all_data['ids']))]
            docs.sort(key=lambda x: x['meta']['timestamp'])
            to_summarize = docs[:15]
            conversation_text = "\n".join([f"{d['meta']['role']}: {d['doc']}" for d in to_summarize])
            
            response = self.groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": f"Summarize this conversation history into a brief narrative paragraph:\n{conversation_text}"}],
                temperature=0.3
            )
            summary = response.choices[0].message.content.strip()
            
            with open(self.summary_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().strftime('%Y-%m-%d')}] {summary}")
            
            self.chat_collection.delete(ids=[d['id'] for d in to_summarize])
            logger.info("🗜️ Master memory updated by 120B model.")
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")

    def search_similar(self, query, top_k=3, distance_threshold=1.3):
        if not query or not query.strip(): return []
        query_embedding = self.get_embedding(query, "search_query")
        if not query_embedding or self.chat_collection.count() == 0: return []
        
        results = self.chat_collection.query(query_embeddings=[query_embedding], n_results=min(top_k, self.chat_collection.count()), include=["documents", "metadatas", "distances"])
        hits = []
        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                dist = results['distances'][0][i] if 'distances' in results and results['distances'] else 0
                if dist <= distance_threshold: hits.append({"role": results['metadatas'][0][i]['role'], "message": results['documents'][0][i]})
        return hits

    def search_rag_files(self, query, top_k=2, distance_threshold=1.3):
        if not query or not query.strip(): return []
        query_embedding = self.get_embedding(query, "search_query")
        if not query_embedding or self.rag_collection.count() == 0: return []
        
        results = self.rag_collection.query(query_embeddings=[query_embedding], n_results=min(top_k, self.rag_collection.count()), include=["documents", "metadatas", "distances"])
        hits = []
        if results['documents'] and results['documents'][0]:
            for i in range(len(results['documents'][0])):
                dist = results['distances'][0][i] if 'distances' in results and results['distances'] else 0
                if dist <= distance_threshold: hits.append({"file_path": results['metadatas'][0][i]['file_name'], "content": results['documents'][0][i]})
        return hits

    def get_relevant_context(self, query):
        """⚡ UPGRADED: Now injects Mood History and Live Workspace Status."""
        similar_chats = self.search_similar(query)
        rag_hits = self.search_rag_files(query)
        long_term_summary = ""
        if self.summary_file.exists():
            with open(self.summary_file, "r", encoding="utf-8") as f: long_term_summary = "".join(f.readlines()[-5:])

        context = [f"⏱️ Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}", f"🧠 SESSION MODE: {self.current_mode}"]
        
        if self.user_bio.get("facts"): context.append("\n👤 USER FACTS:\n" + "\n".join([f"- {fact['text']}" for fact in self.user_bio["facts"]]))
        if self.preferences.get("likes"): context.append("\n🎯 USER PREFS:\n" + "\n".join([f"- {like}" for like in self.preferences["likes"]]))
        
        # 🎭 Injecting the Mood Timeline
        if self.user_mood.get("mood_history"):
            moods = "\n".join([f"- {m['date']} {m['time']} | Mood: {m['mood']}" for m in self.user_mood["mood_history"][-5:]]) # Show last 5 to AI
            context.append(f"\n🎭 RECENT MOOD HISTORY:\n{moods}")
            
        if long_term_summary: context.append(f"\n📜 Long Term Memory:\n{long_term_summary}")
        if similar_chats: context.append("\n💬 Recent Chats:\n" + "\n".join([f"- {msg['role']}: {msg['message']}" for msg in similar_chats]))
        if rag_hits: context.append("\n📂 Knowledge Base (Files):\n" + "\n".join([f"- From {hit['file_path']}: {hit['content']}" for hit in rag_hits]))
        
        # 📂 Injecting Workspace Files Memory & Storage Status
        workspace_data = workspace.get_workspace_context()
        context.append(f"\n📁 MY WORKSPACE FILES & STORAGE STATUS:\n{workspace_data}")
                
        return "\n".join(context)