import aiosmtplib
from email.message import EmailMessage
import logging
from dotenv import load_dotenv
import os
 
load_dotenv() 
SMTP_USER = os.getenv("SMTP_EMAIL")
SMTP_PASS = os.getenv("SMTP_PASSWORD")

logger = logging.getLogger("email_service")

SMTP_HOSTNAME = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = SMTP_USER
SMTP_PASSWORD = SMTP_PASS

async def send_email(to_email: str, subject: str, body: str):
    """
    Sends an outbound email. 
    If credentials aren't set, it logs to console (Mock Mode).
    """
    message = EmailMessage()
    message["From"] = SMTP_USERNAME
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)
 
    try:
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOSTNAME,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USERNAME,
            password=SMTP_PASSWORD,
        )
        logger.info(f"✅ Email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email: {e}")
        return False