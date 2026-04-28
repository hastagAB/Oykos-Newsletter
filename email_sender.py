import smtplib
from smtplib import SMTPAuthenticationError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAILS, NEWSLETTER_TITLE

def send_email(html_content: str) -> bool:
    if not SENDER_PASSWORD or not SENDER_EMAIL:
        print("Missing Gmail credentials in .env")
        return False
        
    if not RECIPIENT_EMAILS:
        print("Missing RECIPIENT_EMAILS in .env")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = NEWSLETTER_TITLE
    msg['From'] = f"Oykomed Bot <{SENDER_EMAIL}>"
    msg['To'] = SENDER_EMAIL # Send to self
    msg['Bcc'] = ", ".join(RECIPIENT_EMAILS) # BCC everyone else

    part2 = MIMEText(html_content, 'html')
    msg.attach(part2)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAILS, msg.as_string())
        server.quit()
        print(f"Newsletter sent successfully to {len(RECIPIENT_EMAILS)} recipients!")
        return True
    except SMTPAuthenticationError as e:
        print("SMTP Authentication Error. Did you use an App Password?")
        print(e)
        return False
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
