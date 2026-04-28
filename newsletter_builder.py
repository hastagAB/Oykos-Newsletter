import os
import openai
from config import NEWSLETTER_TITLE

def summarize_with_llm(title: str, summary: str) -> tuple:
    """Uses OpenAI to re-write the title to be engaging and professional, and makes the summary concise and elegant."""
    if not os.getenv("OPENAI_API_KEY"):
        return title, summary
    
    try:
        # Check for custom base_url in case of region-specific endpoints (like EU) or Azure
        base_url = os.getenv("OPENAI_BASE_URL")
        
        if base_url:
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base_url)
        else:
            client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
        model_name = os.getenv("OPENAI_MODEL", "gpt-4o") # Allows flexibility
        
        prompt = f"Sei un editore medico esperto per pediatri italiani. \n\nTitolo Originale: {title}\nRiassunto Originale: {summary}\n\nRiscrivi il titolo in modo che sia estremamente elegante, professionale, ma accattivante (max 10 parole). Poi riscrivi il riassunto in 2-3 frasi chiare, interessanti e scientificamente accurate.\n\nRestituisci il risultato strettamente in questo formato:\nTITOLO: [Inserisci Titolo]\nRIASSUNTO: [Inserisci Riassunto]"
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=250,
            temperature=0.7
        )
        
        result = response.choices[0].message.content
        new_title = title
        new_summary = summary
        
        for line in result.split("\n"):
            if line.startswith("TITOLO:"):
                new_title = line.replace("TITOLO:", "").strip()
            elif line.startswith("RIASSUNTO:"):
                new_summary = line.replace("RIASSUNTO:", "").strip()
                
        return new_title.strip() or title, new_summary.strip() or summary
    except Exception as e:
        print(f"LLM Error: {e}")
        return title, summary

def generate_html(articles: list) -> str:
    """ Generates a highly professional, Substack-style responsive HTML email layout. """
    html = f"""
    <!DOCTYPE html>
    <html lang="it">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen-Sans, Ubuntu, Cantarell, "Helvetica Neue", sans-serif;
                    background-color: #f4f5f7;
                    margin: 0;
                    padding: 40px 0;
                    color: #1a1a1a;
                    line-height: 1.6;
                    -webkit-font-smoothing: antialiased;
                }}
                .container {{
                    max-width: 680px;
                    margin: 0 auto;
                    background: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
                    overflow: hidden;
                }}
                .header {{
                    text-align: center;
                    padding: 50px 40px;
                    background-color: #ffffff;
                    border-bottom: 1px solid #eaeaea;
                }}
                h1 {{
                    color: #0f172a;
                    font-family: 'Georgia', serif;
                    font-size: 38px;
                    font-weight: normal;
                    margin: 0 0 10px 0;
                    letter-spacing: -0.5px;
                }}
                .intro {{
                    font-size: 17px;
                    color: #64748b;
                    margin: 0;
                }}
                .content {{
                    padding: 40px;
                }}
                .article {{
                    margin-bottom: 45px;
                }}
                .article:last-child {{
                    margin-bottom: 0;
                }}
                .article h2 {{
                    font-family: 'Georgia', serif;
                    font-size: 24px;
                    font-weight: bold;
                    margin: 0 0 12px 0;
                    line-height: 1.35;
                }}
                .article a.title-link {{
                    color: #1e293b;
                    text-decoration: none;
                }}
                .article a.title-link:hover {{
                    color: #2563eb;
                    text-decoration: underline;
                }}
                .meta {{
                    font-size: 13px;
                    color: #94a3b8;
                    display: flex;
                    align-items: center;
                    margin-bottom: 16px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .badge {{
                    color: #ffffff;
                    padding: 3px 8px;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 700;
                    margin-right: 12px;
                }}
                .badge.it {{ background-color: #059669; }}
                .badge.eu {{ background-color: #2563eb; }}
                .badge.global {{ background-color: #6366f1; }}
                .source-text {{
                    font-weight: 500;
                    color: #64748b;
                }}
                .summary {{
                    color: #334155;
                    font-size: 16px;
                    line-height: 1.7;
                    margin: 0;
                }}
                .read-more-wrapper {{
                    margin-top: 15px;
                }}
                .read-more {{
                    display: inline-block;
                    color: #2563eb;
                    font-weight: 600;
                    text-decoration: none;
                    font-size: 15px;
                }}
                .read-more:hover {{
                    text-decoration: underline;
                    color: #1d4ed8;
                }}
                .divider {{
                    border: 0;
                    height: 1px;
                    background-color: #f1f5f9;
                    margin: 45px 0;
                }}
                .footer {{
                    background-color: #f8fafc;
                    text-align: center;
                    padding: 30px 40px;
                    color: #94a3b8;
                    font-size: 13px;
                    border-top: 1px solid #f1f5f9;
                }}
                @media only screen and (max-width: 600px) {{
                    .container {{ border-radius: 0; }}
                    .content {{ padding: 25px; }}
                    .header {{ padding: 40px 20px; }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{NEWSLETTER_TITLE}</h1>
                    <p class="intro">L'eccellenza pediatrica, selezionata per te.</p>
                </div>
                <div class="content">
    """
    
    print("Enhancing articles with AI...")
    for act_idx, article in enumerate(articles):
        print(f"Processing article {act_idx + 1}/{len(articles)} with LLM...")
        
        tier_label = "Italia" if article['tier'] == 1 else "Europa" if article['tier'] == 2 else "Global"
        badge_class = "it" if article['tier'] == 1 else "eu" if article['tier'] == 2 else "global"
        
        # Process with LLM
        enhanced_title, enhanced_summary = summarize_with_llm(article['title'], article.get('summary', ''))
            
        html += f"""
                <div class="article">
                    <h2><a href="{article['link']}" class="title-link">{enhanced_title}</a></h2>
                    <div class="meta">
                        <span class="badge {badge_class}">{tier_label}</span>
                        <span class="source-text">{article['source']}</span>
                    </div>
                    <p class="summary">{enhanced_summary}</p>
                    <div class="read-more-wrapper">
                        <a href="{article['link']}" class="read-more">Leggi l'articolo completo &rarr;</a>
                    </div>
                </div>
        """
        if act_idx < len(articles) - 1:
            html += """<hr class="divider" />"""
        
    html += """
                </div>
                <div class="footer">
                    <p>Motore Newsletter Oykomed &copy; 2026</p>
                    <p>Ricevi questa email perché sei iscritto alla nostra lista per medici pediatri.</p>
                </div>
            </div>
        </body>
    </html>
    """
    return html
