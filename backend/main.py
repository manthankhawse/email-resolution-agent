from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import json
import base64

from fastapi import FastAPI, Request
from sqlmodel import SQLModel, Field, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from pydantic import BaseModel

# --- CUSTOM MODULE IMPORTS ---
from app.email_service import send_email
from app.services.gmail import fetch_email_content 

# 1. CONFIGURATION
DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/agent_db"

# 2. DATABASE MODELS (Updated Schema)
class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Identity
    sender_email: str = Field(index=True)
    receiver_email: str = Field(index=True)
    
    # Content
    subject: str
    description: str
    status: str = Field(default="open")
    
    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # AI Memory
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(3))) 

# 3. DB CONNECTION & LIFECYCLE
async_engine = create_async_engine(DATABASE_URL, echo=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 Starting up...")
    
    # A. Enable pgvector extension (Sync)
    sync_url = DATABASE_URL.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # B. Create Tables (Async)
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✅ Tables created successfully")
    
    yield
    print("🛑 Shutting down...")

app = FastAPI(title="Autonomous ERP Agent", lifespan=lifespan)

# 4. WEBHOOK: The Main Loop
@app.post("/webhook/email")
async def ingest_email(request: Request):
    """
    1. Receive Pub/Sub notification
    2. Fetch real email content using HistoryID
    3. Save to DB
    4. Send Auto-Reply
    """
    # A. Parse the Google Pub/Sub Payload
    try:
        payload = await request.json()
        if "message" not in payload:
            return {"status": "ignored_no_message"}
            
        encoded_data = payload["message"]["data"]
        decoded_str = base64.b64decode(encoded_data).decode("utf-8")
        data_json = json.loads(decoded_str)
        
        history_id = data_json.get("historyId")
        if not history_id:
            return {"status": "ignored_no_history_id"}
            
        print(f"🔔 NOTIFICATION: New Email Event (History ID: {history_id})")

    except Exception as e:
        print(f"❌ Error parsing Pub/Sub: {e}")
        return {"status": "error"}

    # B. Fetch Actual Email Content (Gmail API)
    email_data = fetch_email_content(history_id)
    
    if not email_data:
        print("⚠️ Could not fetch email content (maybe it was a deletion or internal update?)")
        return {"status": "skipped"}
    
    MY_BOT_EMAIL = "khawsemanthan246@gmail.com"
    
    if MY_BOT_EMAIL in email_data["sender"]:
        print(f"🛑 Ignoring outbound email from myself.")
        return {"status": "ignored_self"}

    # C. Save to Database
    async with AsyncSession(async_engine) as session:
        ticket = Ticket(
            sender_email=email_data["sender"],
            receiver_email="me@my-agent.com", # TODO: Parse from email_data later
            subject=email_data["subject"],
            description=email_data["body"],
            status="open"
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        
        print(f"💾 TICKET SAVED: #{ticket.id} from {ticket.sender_email}")

    # D. Send Auto-Reply (The "Thank You" Loop)
    # We strip "Re:" if it's already there to avoid "Re: Re: Re:"
    reply_subject = f"Re: {email_data['subject'].replace('Re: ', '')}"
    
    reply_body = f"""
Hi there,

Thank you for contacting us. We received your message regarding:
"{email_data['subject']}"

Your Ticket ID is #{ticket.id}.
Our AI Agent is reviewing your request and will get back to you shortly.

Best regards,
AI Support Team
    """

    await send_email(
        to_email=email_data["sender"],  # Reply to the person who sent it
        subject=reply_subject,
        body=reply_body
    )
    
    return {"status": "processed", "ticket_id": ticket.id}

@app.get("/")
async def health_check():
    return {"status": "running", "system": "active"}