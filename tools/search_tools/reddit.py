import os
import praw
import logging

def search_reddit(query, limit=3):
    """Reddit se real user opinions fetch karta hai"""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return "Error: Reddit API keys missing in .env"

    try:
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="JarvisAI/1.0"
        )
        
        results_text = f"👽 REDDIT OPINIONS FOR '{query}':\n"
        
        # Subreddits search karna
        for submission in reddit.subreddit("all").search(query, limit=limit):
            results_text += f"Title: {submission.title} (r/{submission.subreddit})\n"
            
            # Top 2 comments nikalna
            submission.comments.replace_more(limit=0)
            comments = submission.comments.list()
            if comments:
                results_text += f"Top Comment 1: {comments[0].body[:200]}...\n"
                if len(comments) > 1:
                    results_text += f"Top Comment 2: {comments[1].body[:200]}...\n"
            results_text += "\n"
            
        return results_text if "Title:" in results_text else "No relevant Reddit discussions found."
    
    except Exception as e:
        logging.error(f"Reddit Search Error: {e}")
        return "Reddit API error."