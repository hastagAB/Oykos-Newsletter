import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Gmail SMTP Settings
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("GMAIL_USER")
SENDER_PASSWORD = os.getenv("GMAIL_APP_PASSWORD") # App Password
RECIPIENT_EMAILS = os.getenv("RECIPIENT_EMAILS", "").split(',')

# Sources to fetch (Strictly Pediatrics)
SOURCES = {
    # Tier 1 - Italy
    "sip": {
        "type": "rss",
        "name": "Società Italiana di Pediatria (SIP)",
        "url": "https://sip.it/feed/",
        "tier": 1
    },
    "medico_bambino": {
        "type": "rss",
        "name": "Medico e Bambino",
        "url": "https://www.medicoebambino.com/rss.php",
        "tier": 1
    },
    "bambino_gesu": {
        "type": "rss",
        "name": "Ospedale Pediatrico Bambino Gesù",
        "url": "https://www.ospedalebambinogesu.it/rss",
        "tier": 1
    },
    "meyer": {
        "type": "rss",
        "name": "Ospedale Meyer News",
        "url": "https://www.meyer.it/index.php?format=feed&type=rss",
        "tier": 1
    },
    "sin_neonatologia": {
        "type": "rss",
        "name": "Società Italiana di Neonatologia (SIN)",
        "url": "https://www.neonatologia.it/feed/",
        "tier": 1
    },
    "gaslini": {
        "type": "rss",
        "name": "Ospedale Gaslini",
        "url": "https://www.gaslini.org/feed/",
        "tier": 1
    },
    "uppa": {
        "type": "rss",
        "name": "UPPA (Un Pediatra Per Amico)",
        "url": "https://www.uppa.it/feed/",
        "tier": 1
    },
    "fimp": {
        "type": "rss",
        "name": "FIMP Nazionale",
        "url": "https://www.fimp.pro/feed/",
        "tier": 1
    },
    
    # Tier 2 - Europe
    "ejped": {
        "type": "rss",
        "name": "European Journal of Pediatrics",
        "url": "https://link.springer.com/search.rss?facet-journal-id=431&facet-content-type=Article",
        "tier": 2
    },
    "adc_bmj": {
        "type": "rss",
        "name": "Archives of Disease in Childhood (BMJ)",
        "url": "https://adc.bmj.com/rss/current.xml",
        "tier": 2
    },
    "eap": {
        "type": "rss",
        "name": "European Academy of Paediatrics",
        "url": "https://www.eapaediatrics.eu/feed/",
        "tier": 2
    },
    "frontiers_pediatrics": {
        "type": "rss",
        "name": "Frontiers in Pediatrics",
        "url": "https://www.frontiersin.org/journals/pediatrics/rss",
        "tier": 2
    },
    "acta_paediatrica": {
        "type": "rss",
        "name": "Acta Paediatrica",
        "url": "https://rss.onlinelibrary.wiley.com/feed/16512227/most-recent",
        "tier": 2
    },
    
    # Tier 3 - Global
    "aap_news": {
        "type": "rss",
        "name": "AAP News",
        "url": "https://publications.aap.org/rss/site_154/48.xml",
        "tier": 3
    },
    "jama_pediatrics": {
        "type": "rss",
        "name": "JAMA Pediatrics",
        "url": "https://jamanetwork.com/rss/site_16/116.xml",
        "tier": 3
    },
    "pediatrics_journal": {
        "type": "rss",
        "name": "Pediatrics (AAP Journal)",
        "url": "https://publications.aap.org/rss/site_114/71.xml",
        "tier": 3
    },
    "lancet_child": {
        "type": "rss",
        "name": "The Lancet Child & Adolescent Health",
        "url": "https://www.thelancet.com/rssfeed/lanchi_current.xml",
        "tier": 3
    },
    "bmc_pediatrics": {
        "type": "rss",
        "name": "BMC Pediatrics",
        "url": "https://bmcpediatr.biomedcentral.com/articles/most-recent/rss.xml",
        "tier": 3
    },
    "pediatric_research": {
        "type": "rss",
        "name": "Pediatric Research",
        "url": "https://www.nature.com/pr.rss",
        "tier": 3
    }
}

NEWSLETTER_TITLE = "L'Essenziale in Pediatria"
