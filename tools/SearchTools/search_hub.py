from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Import only the required tools
from .web import search_web
from .arxiv_tool import search_arxiv

def execute_search_actions(search_actions_dict):
    """
    Processes search actions dictionary.
    Routes only to Web (Tavily) and ArXiv.
    """
    if not search_actions_dict or not isinstance(search_actions_dict, dict):
        return ""

    combined_results = ""
    futures = {}
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        
        # 1. Web Search
        if search_actions_dict.get("web"):
            futures[executor.submit(search_web, search_actions_dict["web"])] = "Web"
            
        # 2. ArXiv Search
        if search_actions_dict.get("arxiv"):
            futures[executor.submit(search_arxiv, search_actions_dict["arxiv"])] = "ArXiv"
            
        # Collect Results
        for future in as_completed(futures):
            source = futures[future]
            try:
                result_text = future.result()
                if result_text:
                    combined_results += f"--- {source} Results ---\n{result_text}\n"
            except Exception as e:
                logging.error(f"Error in {source} thread: {e}")
                
    return combined_results