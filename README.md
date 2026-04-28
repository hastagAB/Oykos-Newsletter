# 🩺 Italian Pediatrics Newsletter Engine

An automated daily engine that aggregates the most relevant pediatric news, articles, and updates, formats them into a curated newsletter, and sends them via Gmail to a mailing list of Italian pediatricians.

## 🚀 Features
- **Tiered Sourcing**: Prioritizes Italian sources (Tier 1), then European (Tier 2), and Global (Tier 3).
- **Format**: Clean, mobile-responsive HTML templates.
- **Smart Deduplication**: Uses an embedded SQLite database (`newsletter.db`) to ensure the same article is never sent twice.
- **Privacy First**: Sends emails via BCC using a Gmail SMTP relay to protect recipient lists.

## 🛠️ Setup Instructions

### 1. Create and Activate a Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Variables
Create a `.env` file in the root directory (or edit the existing one) with the following exact keys:
```env
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_google_app_password
RECIPIENT_EMAILS=doctor1@example.it,doctor2@example.it
```
> **Note:** Since Google disabled standard password logins for apps, you MUST generate an "App Password" from your Google Account Security settings.

## 🖥️ Handy Commands

**Run the engine manually (tests fetching, deduplication, and sending):**
```bash
python main.py
```

**Run the engine and reset the database (starts completely fresh, wipes all memory of sent articles):**
```bash
python main.py --reset-db
```

**Check the SQLite database (if sqlite3 is installed):**
```bash
sqlite3 newsletter.db "SELECT * FROM sent_articles;"
```

**Deactivate the virtual environment:**
```bash
deactivate
```

## ⏱️ Scheduling (Cron Job)
To run this automatically every day at 8:00 AM, add this to your crontab (`crontab -e`):
```bash
0 8 * * * cd /Users/hastagab/Desktop/Oykomed/Newsletter && /Users/hastagab/Desktop/Oykomed/Newsletter/.venv/bin/python main.py >> cron.log 2>&1
```
