from contextlib import asynccontextmanager
from typing import Optional, List
from datetime import datetime
import json
import base64
from fastapi import FastAPI, Request
from sqlmodel import SQLModel, Field, create_engine, text, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.models import Ticket, Customer, TicketMessage, TicketClassification, Platform
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column
from pydantic import BaseModel
from app.email_service import send_email
from app.services.gmail import fetch_email_content 
from dotenv import load_dotenv
from datetime import datetime, timezone
from google.cloud import pubsub_v1
import os
from app.services.ai_service import analyze_ticket

load_dotenv()

SMTP_USER = os.getenv("SMTP_EMAIL")

SERVER_START_TIME = datetime.now(timezone.utc)
 
DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/agent_db"
 

async_engine = create_async_engine(DATABASE_URL, 
                                   echo=False,           
                                   pool_size=20,       
                                   max_overflow=40)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 Starting up...")
    global SERVER_START_TIME
    SERVER_START_TIME = datetime.now(timezone.utc) # Set time when app starts
    print(f"🔄 Server started at: {SERVER_START_TIME}")
    
    sync_url = DATABASE_URL.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
     
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✅ Tables created successfully")
    
    yield
    print("🛑 Shutting down...")

app = FastAPI(title="Autonomous ERP Agent", lifespan=lifespan)
 
@app.post("/webhook/email")
async def ingest_email(request: Request):
    """
    1. Receive Pub/Sub notification
    2. Fetch real email content using HistoryID
    3. Save to DB
    4. Send Auto-Reply
    """ 
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
 
    email_data = fetch_email_content(history_id)
    
    if not email_data:
        print("⚠️ Could not fetch email content (maybe it was a deletion or internal update?)")
        return {"status": "skipped"}

    email_timestamp = email_data.get("timestamp") # We need to add this to gmail.py
    
    if email_timestamp:
        email_dt = datetime.fromtimestamp(email_timestamp / 1000, tz=timezone.utc)
        
        if email_dt < SERVER_START_TIME:
            print(f"⏳ Skipping OLD email from {email_dt} (Server started {SERVER_START_TIME})")
            return {"status": "skipped_old"}
    
    
    if SMTP_USER in email_data["sender"]:
        print(f"🛑 Ignoring outbound email from myself.")
        return {"status": "ignored_self"}
 
    async with AsyncSession(async_engine, expire_on_commit=False) as session:
        q = select(TicketMessage).where(TicketMessage.gmail_message_id == email_data["id"])
        result = await session.execute(q)
        if result.scalars().first():
            print(f"🛑 SKIPPING DUPLICATE: Message {email_data['id']} already processed.")
            return {"status": "ignored_duplicate"}
        # Check if customer exists
        platform_email = email_data["receiver"]
        
        statement = select(Platform).where(Platform.email == platform_email)
        results = await session.execute(statement)
        platform = results.scalars().first()
        
        if not platform:
            # Auto-create for Dev convenience
            print(f"🏢 UNKNOWN PLATFORM '{platform_email}'. creating new tenant...")
            platform = Platform(
                name=f"Platform {platform_email.split('@')[0]}", # "support"
                email=platform_email,
                auth_config={},
                integrations_config={}
            )
            session.add(platform)
            await session.commit()
            await session.refresh(platform)

        statement = select(Customer).where(Customer.email == email_data["sender"])
        results = await session.execute(statement)
        customer = results.scalars().first()
        
        if not customer:
            # Extract name from "Manthan <email>" format if possible
            name_part = email_data["sender"].split("<")[0].strip()
            customer = Customer(email=email_data["sender"], name=name_part)
            session.add(customer)
            await session.commit()
            await session.refresh(customer)
            print(f"👤 NEW CUSTOMER CREATED: {customer.name}")

        ticket = Ticket(
            customer_id=customer.id,
            platform_id=platform.id,
            subject=email_data["subject"],
            status="open"
        )
        session.add(ticket)
        await session.commit()
        await session.refresh(ticket)
        
        # 3. Save the Message (The Email Body)
        message = TicketMessage(
            ticket_id=ticket.id,
            sender_type="customer",
            sender_email=customer.email,
            body=email_data["body"],
            gmail_message_id=email_data["id"]
        )
        session.add(message)
        await session.commit()
        
        print(f"💾 TICKET #{ticket.id} & MESSAGE SAVED.")
 

    print(f"🤖 AI Analyzing Ticket #{ticket.id}...")
    ai_result = analyze_ticket(ticket.subject, message.body)

    # 5. SAVE CLASSIFICATION
    classification = TicketClassification(
        ticket_id=ticket.id,
        category=ai_result.get("category", "Other"),
        sentiment=ai_result.get("sentiment", "Neutral"),
        urgency=ai_result.get("urgency", 1),
        confidence_score=ai_result.get("confidence", 0.0),
        reasoning=json.dumps(ai_result) # Store the whole blob for debug
    )
    session.add(classification)
    await session.commit()

    print(f"✅ AI Result: {classification.category} | Urgency: {classification.urgency}")

    # 6. SEND THE AI REPLY (Instead of the hardcoded one)
    reply_subject = f"Re: {email_data['subject']}"
    reply_body = ai_result.get("suggested_reply")

    await send_email(
        to_email=email_data["sender"],
        subject=reply_subject,
        body=reply_body
    )
    
    return {"status": "processed", "ticket_id": ticket.id}

@app.get("/")
async def health_check():
    return {"status": "running", "system": "active"}