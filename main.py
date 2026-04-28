from database import init_db, mark_articles_as_sent
from fetch_news import gather_articles
from newsletter_builder import generate_html
from email_sender import send_email
import sys
import os
import argparse

def check_env():
    """ Verify required env variables. """
    missing = []
    if not os.getenv("GMAIL_USER"):
         missing.append("GMAIL_USER")
    if not os.getenv("GMAIL_APP_PASSWORD"):
         missing.append("GMAIL_APP_PASSWORD")
    if not os.getenv("RECIPIENT_EMAILS"):
         missing.append("RECIPIENT_EMAILS")
         
    if missing:
        print("Missing required environment variables:", ", ".join(missing))
        print("Please create a .env file based on the spec.")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Italian Pediatrics Newsletter Engine")
    parser.add_argument("--reset-db", action="store_true", help="Delete the existing database and start afresh")
    args = parser.parse_args()

    if args.reset_db:
        db_path = os.path.join(os.path.dirname(__file__), "newsletter.db")
        if os.path.exists(db_path):
            os.remove(db_path)
            print("🗑️  Database deleted successfully. Starting afresh.")
        else:
            print("Database not found, nothing to delete.")

    from config import load_dotenv
    load_dotenv()
    check_env()
    
    # 1. Initialize SQLite if not exists
    print("Database initialization...")
    init_db()
    
    # 2. Scrape and prioritize
    print("Fetching today's pediatric news...")
    top_articles = gather_articles()
    
    if not top_articles:
        print("No new articles found today. Aborting.")
        sys.exit(0)
    
    print(f"Found {len(top_articles)} highly relevant, non-duplicate articles.")
    
    # 3. Generate HTML Content
    print("Building HTML template...")
    html_content = generate_html(top_articles)
    
    # 4. Save to temp file and open in browser
    import tempfile
    import webbrowser
    import time
    
    temp_fd, temp_path = tempfile.mkstemp(suffix=".html")
    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"\n🔗 Opening preview in your browser: {temp_path}")
    webbrowser.open(f"file://{temp_path}")
    time.sleep(1) # wait briefly to ensure browser gets the command
    
    # 5. Prompt User for Approval
    approval = input("\nDo you want to send this newsletter? (y/N): ").strip().lower()
    
    if approval == 'y' or approval == 'yes':
        # 6. Attempt Sending
        print("Dispatching via Gmail...")
        success = send_email(html_content)
        
        # 7. Only mark as sent if dispatch succeeded
        if success:
             print("Marking articles as sent in local DB to avoid future duplicates.")
             mark_articles_as_sent(top_articles)
        else:
             print("Failed to dispatch email. Not saving state so they will try again.")
    else:
        print("Sending cancelled by user. Articles were NOT marked as sent in DB.")
        
    print("Cleaning up temp file...")
    try:
        os.remove(temp_path)
    except:
        pass
        
    print("Done.")