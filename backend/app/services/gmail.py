import os
import json
import base64
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_gmail_service():
    """Loads the saved token and returns a Gmail API client."""
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        return build("gmail", "v1", credentials=creds)
    return None

def fetch_email_content(history_id: str):
    """
    Uses the historyId to find the latest message and return its subject/body.
    """
    service = get_gmail_service()
    if not service:
        print("❌ No token.json found. Cannot fetch email.")
        return None

    try:
        # 1. Ask Gmail: "What changed at this history ID?"
        # We assume the notification is for the very latest message
        history = service.users().history().list(
            userId="me", startHistoryId=history_id
        ).execute()

        # Extract the message ID from the history records
        changes = history.get("history", [])
        if not changes:
            print("⚠️ No history found (might be an old ID). fetching latest message instead.")
            # Fallback: Get the very last message in Inbox
            results = service.users().messages().list(userId="me", maxResults=1).execute()
            messages = results.get("messages", [])
        else:
            # Grab the first message ID found in the history change
            messages = changes[0].get("messages", [])

        if not messages:
            return None

        message_id = messages[0]["id"]
        
        # 2. Fetch the actual Email Content
        msg = service.users().messages().get(userId="me", id=message_id).execute()
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        
        # Extract Subject
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")

        # Extract Body (Decode Base64)
        body = " (No text content)"
        if "body" in payload and "data" in payload["body"]:
            data = payload["body"]["data"]
            body = base64.urlsafe_b64decode(data).decode("utf-8")
        elif "parts" in payload:
            # If multipart (e.g. text + html), grab the text part
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    data = part["body"]["data"]
                    body = base64.urlsafe_b64decode(data).decode("utf-8")
                    break

        return {
            "id": message_id,
            "sender": sender,
            "subject": subject,
            "body": body
        }

    except Exception as e:
        print(f"❌ Gmail API Error: {e}")
        return None