import os
import logging
from tavily import TavilyClient
from dotenv import load_dotenv

logging.basicConfig(
    filename='Data/tavily_search.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

load_dotenv()

def search_web(query, max_results=3):
    """Tavily API ka use karke direct web search aur content extraction."""
    try:
        if not query: return "Empty search query."

        api_key = os.getenv('TAVILY_API_KEY')
        if not api_key:
            logging.error("TAVILY_API_KEY not set in .env")
            return "Error: TAVILY_API_KEY missing."

        client = TavilyClient(api_key=api_key)
        
        # Tavily automatically searches and extracts relevant content
        response = client.search(
            query=query,
            search_depth="advanced", # "advanced" gives deeper content, "basic" is faster
            max_results=max_results
        )
        
        results = response.get("results", [])
        if not results:
            return "No web results found."

        final_text = f"WEB SEARCH RESULTS FOR '{query}':\n\n"
        for r in results:
            final_text += f"Title: {r.get('title', 'N/A')}\n"
            final_text += f"Link: {r.get('url', 'N/A')}\n"
            # Tavily provides a clean summary/content chunk directly
            final_text += f"Content: {r.get('content', 'N/A')}...\n\n"
            
        return final_text

    except Exception as e:
        logging.error(f"Error in Tavily search_web: {e}")
        return f"Web search failed: {e}"
    
