import os
import re
import logging
from urllib.parse import urlparse
from dotenv import load_dotenv
from serpapi import GoogleSearch 
import requests
from bs4 import BeautifulSoup
from cachetools import TTLCache
import cloudscraper
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests as curl_requests

# Set up logging
logging.basicConfig(
    filename='Data/serp_api_search.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Ensure the Data directory exists
os.makedirs('Data', exist_ok=True)

# Cache for fetched content (TTL: 1 hour)
content_cache = TTLCache(maxsize=1000, ttl=3600)

# Initialize User-Agent rotator
ua = UserAgent()
load_dotenv()

# ✅ GLOBAL SESSION & PROXY SETUP
scraper = cloudscraper.create_scraper()
retries = Retry(
    total=2, 
    backoff_factor=0.5,
    status_forcelist=[429, 500, 502, 503, 504]
)
scraper.mount('http://', HTTPAdapter(max_retries=retries))
scraper.mount('https://', HTTPAdapter(max_retries=retries))

proxies = os.getenv('SCRAPER_PROXIES', None)
if proxies:
    proxies = {'http': proxies, 'https': proxies}

# 🧠 SMART STOP-WORDS
STOP_WORDS = {
    'is', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'a', 'an', 'and', 'or',
    'ki', 'ka', 'ke', 'hai', 'aur', 'mein', 'se', 'ko', 'sabse', 'batao', 
    'kya', 'kaun', 'si', 'tha', 'thi', 'the', 'karo', 'do'
}

def sanitize_query(query):
    query = re.sub(r'\s+', ' ', query.strip())
    query = re.sub(r'[^\w\s]', '', query)
    corrections = {'netowrth': 'net worth', 'prcie': 'price', 'iphnoe': 'iphone', 'dealss': 'deals'}
    for typo, correct in corrections.items():
        if typo in query.lower():
            query = query.lower().replace(typo, correct)
    return query

def is_reliable_source(url):
    reliable_domains = [
        '.org', '.edu', '.gov', 'wikipedia.org', 'python.org',
        'timesofindia.indiatimes.com', 'hindustantimes.com',
        'indianexpress.com', 'forbes.com', 'bloomberg.com',
        'apple.com', 'flipkart.com', 'amazon.in'
    ]
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    return any(domain.endswith(d) or domain == d for d in reliable_domains)

def fetch_full_content(url):
    """ULTRA-FAST & UNBLOCKABLE FETCHER"""
    if url in content_cache:
        return content_cache[url]

    if any(url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.mp4', '.zip']):
        return "Error: Unsupported file type"

    try:
        # Layer 1: curl_cffi Magic
        response = curl_requests.get(url, impersonate="chrome120", timeout=8, proxies=proxies)
        if response.status_code in [403, 401, 503] or 'text/html' not in response.headers.get('content-type', '').lower():
            raise Exception(f"Status {response.status_code} or non-HTML, triggering fallback")

        soup = BeautifulSoup(response.text, 'html.parser')
        for elem in soup(["script", "style", "nav", "footer", "header", "iframe", "aside"]):
            elem.decompose()

        text = soup.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())
        
    except Exception as e:
        # Layer 2: JINA AI READER
        logging.warning(f"Native fetch failed for {url} ({e}). Using Jina AI fallback...")
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {"Accept": "application/json"} 
            jina_response = requests.get(jina_url, headers=headers, timeout=10)
            
            if jina_response.status_code == 200:
                data = jina_response.json()
                text = data.get("data", {}).get("content", "")
            else:
                return f"Error: All fetch layers failed for {url}"
                
        except Exception as jina_e:
            logging.error(f"Jina fallback also failed: {jina_e}")
            return "Error: Could not retrieve content."

    final_text = text[:8000] if text else "Error: Empty content"
    content_cache[url] = final_text
    return final_text

def calculate_relevance_score(content, query):
    query_words = set(re.findall(r'\w+', query.lower()))
    meaningful_words = query_words - STOP_WORDS
    if not meaningful_words: return 0
    content_lower = content.lower()
    matches = sum(1 for word in meaningful_words if word in content_lower)
    return matches / len(meaningful_words)

def process_single_result(r, query):
    link = r.get('link', '')
    if not link: return None
    full_content = fetch_full_content(link)
    return {
        'title': r.get('title', 'N/A'),
        'link': link,
        'snippet': r.get('snippet', 'N/A'),
        'reliable': is_reliable_source(link),
        'full_content': full_content,
        'relevance_score': calculate_relevance_score(full_content, query)
    }

def search_web(query, max_results=3):
    """
    Core Web Search tool for Jarvis.
    Returns a clean string formatted for the LLM.
    """
    try:
        query = sanitize_query(query)
        if not query: return "Empty search query."

        api_key = os.getenv('SERPAPI_API_KEY') or os.getenv('SERP_API_KEY')
        if not api_key:
            logging.error("SERP_API_KEY not set in .env")
            return "Error: SERP_API_KEY missing."

        params = {
            'q': query,
            'location': 'India',
            'gl': 'in',
            'hl': 'en',
            'api_key': api_key,
            'num': max_results,
            'tbm': 'nws' if 'news' in query.lower() else None
        }

        search = GoogleSearch(params)
        response = search.get_dict()
        
        organic_results = response.get('organic_results', [])
        if not organic_results and 'news_results' in response:
            organic_results = response.get('news_results', [])
            
        if not organic_results:
            return "No web results found."

        final_results = []
        
        # ⚡ Fetching websites simultaneously
        with ThreadPoolExecutor(max_workers=max_results) as executor:
            future_to_result = {
                executor.submit(process_single_result, r, query): r 
                for r in organic_results[:max_results]
            }
            
            for future in as_completed(future_to_result):
                try:
                    res = future.result()
                    if res:
                        final_results.append(res)
                except Exception as e:
                    logging.error(f"Thread error: {e}")

        # Sort by reliability first, then by meaningful keyword relevance
        final_results = sorted(
            final_results,
            key=lambda x: (x['reliable'], x['relevance_score']),
            reverse=True
        )

        # 🛠️ NAYA LOGIC: Formatting for Jarvis Brain
        final_text = f"🌐 WEB SEARCH RESULTS FOR '{query}':\n\n"
        for r in final_results:
            final_text += f"🔹 Title: {r['title']}\n"
            final_text += f"🔗 Source: {r['link']}\n"
            # Extract pehle 1500 characters taaki LLM ka context window overfill na ho
            content_snippet = r['full_content'][:1500].replace('\n', ' ') 
            final_text += f"📄 Content: {content_snippet}...\n\n"
            
        return final_text

    except Exception as e:
        logging.error(f"Error in search_web: {e}")
        return f"Web search failed: {e}"