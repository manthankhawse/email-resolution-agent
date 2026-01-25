import os
import json
import base64
import re
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        return build("gmail", "v1", credentials=creds)
    return None

def fetch_email_content(history_id: str):
    """
    Ignores history_id (which requires state) and purely fetches the latest
    received email from the Inbox. Relies on DB de-duplication to be safe.
    """
    service = get_gmail_service()
    if not service:
        return None

    try:
        # 1. Just get the latest email in the INBOX (Ignore Sent items)
        results = service.users().messages().list(
            userId="me", 
            labelIds=["INBOX"], # 👈 Only look at received mail
            maxResults=1
        ).execute()
        
        messages = results.get("messages", [])
        if not messages:
            print("⚠️ Inbox is empty.")
            return None

        message_id = messages[0]["id"]
        
        # 2. Fetch the full content
        msg = service.users().messages().get(userId="me", id=message_id).execute()
        internal_date = int(msg.get("internalDate", 0))
        
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        
        # 3. Extract Headers
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender_header = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        to_header = next((h["value"] for h in headers if h["name"] == "To"), "")
        
        # 4. Extract Platform
        platform_email = to_header
        if "<" in to_header:
            platform_email = to_header.split("<")[1].strip(">")

        # 5. Decode Body
        body = " (No text content)"
        if "body" in payload and "data" in payload["body"]:
            data = payload["body"]["data"]
            body = base64.urlsafe_b64decode(data).decode("utf-8")
        elif "parts" in payload: 
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    data = part["body"]["data"]
                    body = base64.urlsafe_b64decode(data).decode("utf-8")
                    break

        # 6. Smart Sender Logic (Manual Forwards)
        real_sender = sender_header
        if platform_email in sender_header:
            print(f"⚠️ Manual Forward detected. Scanning body...")
            # Simple regex to find the original sender in the forwarded body
            match = re.search(r"From:.*[\r\n]+.*<([^>]+)>|From:\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", body)
            if match:
                extracted = match.group(1) or match.group(2)
                print(f"🕵️ Extracted Original Sender: {extracted}")
                real_sender = extracted

        return {
            "id": message_id,
            "sender": real_sender,      
            "receiver": platform_email,  
            "subject": subject,
            "body": body,
            "timestamp": internal_date
        }

    except Exception as e:
        print(f"❌ Gmail API Error: {e}")
        return None