import os
import json
import logging
import time
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types

from core.brain.config import GEMINI_AGENT_MODEL, DEEP_RESEARCH_TIMEOUT, GEMINI_API_KEY

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DeepResearcher:
    def __init__(self, topic, max_steps=10):
        self.topic = topic
        self.max_steps = max_steps
        self.accumulated_data = ""
        self.scratchpad = ""
        self.completed_actions = set()
        self.step = 0
        
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.model_name = GEMINI_AGENT_MODEL        
        # 🆕 System Prompt ab Intent-Driven hai (Koi forced dates nahi)
        self.system_prompt = (
            "Tu ek World-Class Deep Research Agent hai. Tera goal: user ke topic par exhaustive, fact-based, professional report (2000-4000 words) banana.\n\n"
            "Tu strict JSON output karega. Schema:\n"
            "{\n"
            "  \"thought\": \"Step1: Goal... Step2: Scratchpad... Step3: Next action\",\n"
            "  \"is_task_complete\": false,\n"
            "  \"final_report\": \"\",\n"
            "  \"search_actions\": {\"web\": \"query\", \"arxiv\": \"query\"}\n"
            "}\n\n"
            "CRITICAL RULES:\n"
            "- Analyze the user's topic carefully. If they ask for 'latest' or 'recent' data, use current years in your search queries.\n"
            "- If the topic is historical, frame your queries around those specific historical dates.\n"
            "- Seek quantitative metrics and exact data points where relevant to the topic.\n"
            "- Include specific citations: article titles, authors, DOI/arXiv IDs, URLs.\n"
            "- NEVER assume success; read scratchpad observations to refine your next search.\n"
        )
    
    def call_llm(self, prompt, system_override=None):
        for attempt in range(3):
            try:
                logger.info(f"📡 LLM call (attempt {attempt+1})")
                config = types.GenerateContentConfig(
                    system_instruction=system_override or self.system_prompt,
                    temperature=0.1,
                )
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config
                )
                raw = response.text
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                if match:
                    return json.loads(match.group(0))
                else:
                    return {"is_task_complete": True, "final_report": raw}
            except Exception as e:
                logger.error(f"Attempt {attempt+1} error: {e}")
                if attempt == 2:
                    return {"is_task_complete": True, "final_report": f"Error: {e}"}
                time.sleep(2)
        return {"is_task_complete": True, "final_report": "Failed after retries."}
    
    def run(self):
        logger.info(f"🚀 DEEP RESEARCH START: {self.topic}")
        print("\n" + "="*80)
        print(f"📚 TOPIC: {self.topic}")
        print("="*80)
        
        start_time = time.time()
        timeout_seconds = DEEP_RESEARCH_TIMEOUT
        
        while self.step < self.max_steps:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                logger.warning("⏰ Timeout reached")
                break
                
            self.step += 1
            steps_left = self.max_steps - self.step
            print(f"\n{'='*80}")
            print(f"🔄 STEP {self.step}/{self.max_steps} | Steps left: {steps_left}")
            print(f"{'='*80}")
            
            completed_list = "\n".join(self.completed_actions) if self.completed_actions else "None"
            data_snippet = self.accumulated_data[-15000:] if self.accumulated_data else "No data yet."
            
            # 🆕 Prompt ab topic-focused hai
            prompt = f"""[USER GOAL]
{self.topic}

[COMPLETED ACTIONS]
{completed_list}

[SCRATCHPAD]
{self.scratchpad if self.scratchpad else "No observations yet."}

[DATA SO FAR (last 15000 chars)]
{data_snippet}

[STEP] {self.step}/{self.max_steps}

Decide:
- If you have enough robust data to fulfill the user's specific request for a 2000-4000 word report with citations → is_task_complete = true, write final_report.
- Else → choose specific search_actions (web + arxiv) tailored exactly to what the user asked.

Return JSON only."""
            
            decision = self.call_llm(prompt)
            
            if decision.get("is_task_complete"):
                logger.info("✅ Agent decided task complete!")
                final_report = decision.get("final_report", decision.get("response", "Report not provided."))
                print("\n" + "🌟" * 30)
                print("FINAL REPORT:")
                print("🌟" * 30)
                print(final_report)
                print("🌟" * 30)
                return final_report
            
            search_actions = decision.get("search_actions", {})
            if not search_actions:
                logger.warning("No search_actions, forcing finalize")
                break
            
            # 🆕 Koi dates inject nahi ho rahi, strictly LLM ki query use ho rahi hai
            action_key = f"search:{json.dumps(search_actions, sort_keys=True)}"
            if action_key in self.completed_actions:
                logger.info("⏭️ Skipping duplicate")
                continue
            self.completed_actions.add(action_key)
            
            reasoning = decision.get("thought", "Searching...")
            print(f"\n🧠 THOUGHT: {reasoning[:300]}")
            print(f"🔍 SEARCH: {json.dumps(search_actions, indent=2)}")
            
            results = execute_search_actions(search_actions)
            print(f"📥 RESULTS: {len(results)} characters")
            
            if len(results) < 300:
                print("⚠️ Low results, expanding search logic...")
                # Agent will realize next step that results were low and adjust its own query.
            
            obs = f"Step {self.step}: Searched {list(search_actions.keys())} -> got {len(results)} chars."
            self.scratchpad += f"\n- {obs}"
            self.accumulated_data += f"\n--- STEP {self.step} ---\n{results}\n"
            logger.info(f"Total accumulated: {len(self.accumulated_data)} chars")
            time.sleep(0.5)
        
        logger.warning("⚠️ Max steps/time reached – forcing final compilation")
        print("\n⚠️ FINALIZING WITH AVAILABLE DATA...")
        force_prompt = f"Topic: {self.topic}\nData (last 20000 chars):\n{self.accumulated_data[-20000:]}\n\nWrite a 2500+ word professional report based ON THE USER'S EXACT TOPIC. Must include: specific citations (titles/URLs) and relevant facts. Return JSON with is_task_complete=true and final_report."
        final_decision = self.call_llm(force_prompt)
        forced_report = final_decision.get("final_report", "Report generation failed.")
        print("\n" + "🌟" * 30)
        print(forced_report)
        print("🌟" * 30)
        return forced_report


def generate_filename_from_ai(topic, report_content, client, model_name):
    """AI khud se filename generate karega based on topic and report."""
    prompt = f"""
Topic: {topic}

Report content (first 2000 chars):
{report_content[:2000]}

Task: Generate a SHORT, descriptive filename for this research report.
Rules:
- Only lowercase letters, numbers, underscores (_)
- No spaces, no special characters except underscore
- Max length: 50 characters
- Must end with .md
- Example: "solid_state_batteries_analysis.md" or "financial_crisis_2008.md"

Return ONLY the filename, nothing else.
"""
    try:
        config = types.GenerateContentConfig(temperature=0.2)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        filename = response.text.strip().split("\n")[0].strip()
        filename = re.sub(r'[^a-z0-9_.]', '_', filename.lower())
        if not filename.endswith('.md'):
            filename += '.md'
        if len(filename) > 60:
            filename = filename[:55] + '.md'
        return filename
    except Exception as e:
        logger.error(f"AI filename generation failed: {e}")
        return None


def deep_research(topic, max_steps=10):
    """
    Deep research tool. Report automatically saved to:
    F:\\Jarvis\\Data\\Jarvis_Workspace\\Creations\\{ai_generated_name}.md
    """
    agent = DeepResearcher(topic, max_steps=max_steps)
    report = agent.run()
    
    ai_filename = generate_filename_from_ai(topic, report, agent.client, agent.model_name)
    
    if not ai_filename:
        safe_topic = re.sub(r'[^a-zA-Z0-9]', '_', topic.lower())[:40]
        timestamp = int(time.time())
        ai_filename = f"report_{safe_topic}_{timestamp}.md"
    
    save_dir = r"F:\Jarvis\Data\Jarvis_Workspace\Creations"
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, ai_filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(report)
    
    logger.info(f"📄 Report saved to {filepath}")
    print(f"\n💾 Report automatically saved as: {ai_filename}")
    print(f"📍 Location: {save_dir}")
    
    return report

def deep_research_as_tool(topic: str) -> str:
    try:
        report = deep_research(topic, max_steps=10)
        save_dir = r"F:\Jarvis\Data\Jarvis_Workspace\Creations"
        import glob
        pattern = os.path.join(save_dir, "*.md")
        files = glob.glob(pattern)
        latest_file = max(files, key=os.path.getctime) if files else None
        if latest_file:
            filename = os.path.basename(latest_file)
            return f"Deep research completed successfully. Report saved as '{filename}' at {save_dir}. Report length: {len(report)} characters."
        else:
            return f"Deep research completed but file not found? Report content preview: {report[:300]}..."
    except Exception as e:
        return f"Deep research failed: {str(e)}"

if __name__ == "__main__":
    query = input("🤖 Enter research topic: ")
    deep_research(query, max_steps=10)