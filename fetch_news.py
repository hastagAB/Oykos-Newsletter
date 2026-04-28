import feedparser
import requests
from bs4 import BeautifulSoup
from config import SOURCES
from database import is_article_sent

def fetch_rss_feed(source_info):
    url = source_info['url']
    feed = feedparser.parse(url)
    articles = []
    
    for entry in feed.entries[:10]: # Check the top 10 from each feed
        link = entry.get('link', '')
        title = entry.get('title', '')
        
        # Deduplication check
        if not is_article_sent(link):
            articles.append({
                'title': title,
                'link': link,
                'source': source_info['name'],
                'tier': source_info['tier'],
                'summary': entry.get('summary', '')
            })
    return articles

def gather_articles() -> list:
    all_articles = []
    
    for key, source in SOURCES.items():
        if source['type'] == 'rss':
            print(f"Fetching from {source['name']}...")
            try:
                new_articles = fetch_rss_feed(source)
                all_articles.extend(new_articles)
            except Exception as e:
                print(f"Error fetching from {source['name']}: {e}")
                
    # Sort primarily by tier (1 is most important)
    all_articles.sort(key=lambda x: x['tier'])
    
    # Take top 15 to not overwhelm the reader but provide enough variety
    return all_articles[:15]
