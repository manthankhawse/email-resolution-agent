import aiosmtplib
from email.message import EmailMessage
import logging

logger = logging.getLogger("email_service")

SMTP_HOSTNAME = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = "khawsemanthan246@gmail.com" 
SMTP_PASSWORD = "hbja dhap eqjk cscj" 

async def send_email(to_email: str, subject: str, body: str):
    """
    Sends an outbound email. 
    If credentials aren't set, it logs to console (Mock Mode).
    """
    message = EmailMessage()
    message["From"] = "khawsemanthan246@gmail.com"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    # MOCK MODE: If no password, just print it (Safety for Dev)
    if SMTP_PASSWORD == "your-password":
        print(f"\n📨 [MOCK EMAIL SENT] ------------------")
        print(f"To: {to_email}")
        print(f"Subject: {subject}")
        print(f"Body: {body}")
        print(f"----------------------------------------\n")
        return True

    # REAL MODE: Send via SMTP
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