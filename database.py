import os
import sqlite3
from typing import List

# Setup SQLite DB for deduplication
DB_PATH = os.path.join(os.path.dirname(__file__), "newsletter.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            source TEXT,
            date_sent TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_article_sent(url: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sent_articles WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_articles_as_sent(articles: List['dict']):
    if not articles:
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for article in articles:
        try:
            cursor.execute(
                "INSERT INTO sent_articles (url, title, source) VALUES (?, ?, ?)",
                (article.get('link', ''), article.get('title', ''), article.get('source', 'Unknown'))
            )
        except sqlite3.IntegrityError:
            # URL already exists
            pass
    conn.commit()
    conn.close()
