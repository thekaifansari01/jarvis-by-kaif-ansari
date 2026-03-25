from urllib.parse import urlparse
import os
from dotenv import load_dotenv
import logging
from serpapi import GoogleSearch 
import requests
from bs4 import BeautifulSoup
import re
from cachetools import TTLCache
import cloudscraper
from fake_useragent import UserAgent
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from curl_cffi import requests as curl_requests # ⚡ NEW: For Chrome Impersonation

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

# ✅ GLOBAL SESSION & PROXY SETUP (Reuse Connection = Fast)
# We keep cloudscraper as a backup, but primary will be curl_cffi
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

# 🧠 SMART STOP-WORDS (English + Hinglish)
STOP_WORDS = {
    'is', 'the', 'in', 'on', 'at', 'to', 'for', 'of', 'a', 'an', 'and', 'or',
    'ki', 'ka', 'ke', 'hai', 'aur', 'mein', 'se', 'ko', 'sabse', 'batao', 
    'kya', 'kaun', 'si', 'tha', 'thi', 'the', 'karo', 'do'
}

def sanitize_query(query):
    """Clean and optimize the search query."""
    query = re.sub(r'\s+', ' ', query.strip())
    query = re.sub(r'[^\w\s]', '', query)
    
    corrections = {
        'netowrth': 'net worth', 'prcie': 'price',
        'iphnoe': 'iphone', 'dealss': 'deals'
    }
    for typo, correct in corrections.items():
        if typo in query.lower():
            query = query.lower().replace(typo, correct)
    return query

def is_reliable_source(url):
    """Check reliability based on trusted domains."""
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
    """
    ULTRA-FAST & UNBLOCKABLE FETCHER:
    Layer 1: Impersonates real Chrome 120 (Bypasses Cloudflare/403).
    Layer 2: Fallback to Jina AI Reader for heavy JS/Strict sites.
    """
    if url in content_cache:
        return content_cache[url]

    # 🛑 Filter junk URLs early (PDFs, Images, Videos)
    if any(url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.mp4', '.zip']):
        return "Error: Unsupported file type"

    try:
        # Layer 1: The 'curl_cffi' Magic (Spoofs exact Chrome TLS fingerprint)
        # Timeout is slightly higher (8s) to allow slow servers to respond
        response = curl_requests.get(
            url, 
            impersonate="chrome120", # ⚡ Bypasses Cloudflare & WAFs
            timeout=8,
            proxies=proxies
        )
        
        # Trigger fallback if blocked or not HTML
        if response.status_code in [403, 401, 503] or 'text/html' not in response.headers.get('content-type', '').lower():
            raise Exception(f"Status {response.status_code} or non-HTML, triggering fallback")

        # HTML parsing
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Clean junk to save LLM tokens
        for elem in soup(["script", "style", "nav", "footer", "header", "iframe", "aside"]):
            elem.decompose()

        text = soup.get_text(separator=' ', strip=True)
        text = ' '.join(text.split())
        
    except Exception as e:
        # Layer 2: JINA AI READER (The Ultimate Fallback)
        logging.warning(f"Native fetch failed for {url} ({e}). Using Jina AI fallback...")
        try:
            jina_url = f"https://r.jina.ai/{url}"
            headers = {"Accept": "application/json"} 
            
            # Using standard requests here as Jina is an open API
            jina_response = requests.get(jina_url, headers=headers, timeout=10)
            
            if jina_response.status_code == 200:
                data = jina_response.json()
                text = data.get("data", {}).get("content", "")
            else:
                return f"Error: All fetch layers failed for {url}"
                
        except Exception as jina_e:
            logging.error(f"Jina fallback also failed: {jina_e}")
            return "Error: Could not retrieve content."

    # Cap at 8000 chars to save context window and tokens
    final_text = text[:8000] if text else "Error: Empty content"
    content_cache[url] = final_text
    
    return final_text

def calculate_relevance_score(content, query):
    """
    SMART SCORING: Ignores common stop words and checks for actual meaningful keywords.
    """
    query_words = set(re.findall(r'\w+', query.lower()))
    meaningful_words = query_words - STOP_WORDS
    
    if not meaningful_words:
        return 0
        
    content_lower = content.lower()
    matches = sum(1 for word in meaningful_words if word in content_lower)
    return matches / len(meaningful_words)

def process_single_result(r, query):
    """Helper function to process a single SERP result in a thread."""
    link = r.get('link', '')
    if not link:
        return None
        
    full_content = fetch_full_content(link)
    
    return {
        'title': r.get('title', 'N/A'),
        'link': link,
        'snippet': r.get('snippet', 'N/A'),
        'reliable': is_reliable_source(link),
        'full_content': full_content,
        'relevance_score': calculate_relevance_score(full_content, query)
    }

def search_serpapi(query, region="in", max_results=5):
    """
    OPTIMIZED: Uses ThreadPoolExecutor to fetch all website contents in parallel.
    """
    try:
        query = sanitize_query(query)
        if not query: return []

        api_key = os.getenv('SERPAPI_API_KEY') or os.getenv('SERP_API_KEY')
        if not api_key:
            logging.error("SERP_API_KEY not set in .env")
            return []

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
            return []

        final_results = []
        
        # ⚡ The Speed Secret: Fetching 5 websites simultaneously
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

        return final_results

    except Exception as e:
        logging.error(f"Error in search_serpapi: {e}")
        return []

def perform_search(command, return_results=False):
    """Core Entry Point for Jarvis."""
    load_dotenv()
    if not command or not command.strip():
        return [] if return_results else None
    
    results = search_serpapi(command, region="India")
    
    # We only return results back to executor (LLM will format it).
    # Removed the messy print/display logic since Jarvis speaks the output anyway.
    if return_results:
        return results
        
    return None