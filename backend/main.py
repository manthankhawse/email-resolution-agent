from contextlib import asynccontextmanager
from typing import Optional, List
from fastapi import FastAPI
from sqlmodel import SQLModel, Field, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column

# 1. CONFIGURATION
DATABASE_URL = "postgresql+asyncpg://admin:admin@localhost:5432/agent_db"

# 2. DATABASE MODELS (The Schema)
class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    subject: str
    description: str
    status: str = Field(default="open")
    # This vector column is for the AI memory later
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(3))) 

# 3. DB CONNECTION & LIFECYCLE
async_engine = create_async_engine(DATABASE_URL, echo=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 Starting up...")
    
    # A. Enable pgvector extension (Needs sync connection)
    sync_url = DATABASE_URL.replace("+asyncpg", "")
    sync_engine = create_engine(sync_url)
    with sync_engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    
    # B. Create Tables (This is the missing part!)
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✅ Tables created successfully")
    
    yield
    print("🛑 Shutting down...")

app = FastAPI(title="Autonomous ERP Agent", lifespan=lifespan)

@app.get("/")
async def health_check():
    return {"status": "running", "db": "tables_ready"}