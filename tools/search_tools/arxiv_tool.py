import arxiv
import logging

def search_arxiv(query, max_results=3):
    """ArXiv se scientific aur research papers fetch karta hai"""
    if not query: return ""
    
    try:
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance
        )
        
        results_text = f"📚 ARXIV RESEARCH PAPERS FOR '{query}':\n"
        papers_found = False
        
        for result in search.results():
            papers_found = True
            results_text += f"- Title: {result.title}\n"
            results_text += f"  Authors: {', '.join([a.name for a in result.authors])}\n"
            results_text += f"  Summary: {result.summary[:300]}...\n\n"
            
        return results_text if papers_found else "No research papers found on ArXiv."
        
    except Exception as e:
        logging.error(f"ArXiv Error: {e}")
        return "ArXiv search failed."