import os
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

# ⚠️ REPLACE WITH YOUR PROJECT ID IF NEEDED
TOPIC_NAME = os.getenv("TOPIC_NAME")

def connect_gmail_to_pubsub():
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    
    # 1. Start Auth Flow
    # We use credentials.json from the backend folder
    creds_path = os.path.join(os.path.dirname(__file__), './credentials.json')
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    
    # ⚡ CRITICAL FIX: prompt='consent' forces a new Refresh Token
    creds = flow.run_local_server(port=8080, prompt='consent')

    # 2. Save the Token to the correct place (backend root)
    token_path = os.path.join(os.path.dirname(__file__), '../token.json')
    with open(token_path, 'w') as token:
        token.write(creds.to_json())
    print(f"💾 SUCCESS! Token saved to: {token_path}")
    
    # 3. Connect to Gmail
    service = build('gmail', 'v1', credentials=creds)
    request = {
        'labelIds': ['INBOX'],
        'topicName': TOPIC_NAME
    }
    
    print(f"🔌 Connecting Gmail to: {TOPIC_NAME}...")
    try:
        service.users().watch(userId='me', body=request).execute()
        print("✅ SUCCESS! Gmail is watching.")
    except Exception as e:
        print(f"⚠️ Watch Error (might be already set): {e}")

if __name__ == "__main__":
    connect_gmail_to_pubsub()