from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Import all individual tools
from .web import search_web
from .reddit import search_reddit
from .arxiv_tool import search_arxiv
from .weather import get_weather

def execute_search_actions(search_actions_dict):
    """
    Jarvis ke 'search_actions' JSON dictionary ko process karta hai.
    Example Input: {"web": "RTX 4060", "reddit": "RTX 4060 reviews"}
    """
    if not search_actions_dict or not isinstance(search_actions_dict, dict):
        return ""

    combined_results = ""
    futures = {}
    
    # ⚡ Parallel Execution Start
    with ThreadPoolExecutor(max_workers=4) as executor:
        
        # 1. Check for Web Search
        if search_actions_dict.get("web"):
            futures[executor.submit(search_web, search_actions_dict["web"])] = "Web"
            
        # 2. Check for Reddit Search
        if search_actions_dict.get("reddit"):
            futures[executor.submit(search_reddit, search_actions_dict["reddit"])] = "Reddit"
            
        # 3. Check for ArXiv Search
        if search_actions_dict.get("arxiv"):
            futures[executor.submit(search_arxiv, search_actions_dict["arxiv"])] = "ArXiv"
            
        # 4. Check for Weather Search
        if search_actions_dict.get("weather"):
            # Weather can be a string or a dict based on your LLM output
            weather_data = search_actions_dict["weather"]
            if isinstance(weather_data, str):
                weather_data = {"location": weather_data, "type": "current"}
            futures[executor.submit(get_weather, weather_data)] = "Weather"

        # ⚡ Collect Results as they finish
        for future in as_completed(futures):
            source = futures[future]
            try:
                result_text = future.result()
                if result_text:
                    combined_results += f"{result_text}\n{'-'*40}\n"
            except Exception as e:
                logging.error(f"Error in {source} thread: {e}")
                
    return combined_results     