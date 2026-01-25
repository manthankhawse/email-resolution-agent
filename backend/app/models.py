from typing import Optional, List, Dict
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, JSON


class Platform(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
     
    name: str      
    email: str = Field(unique=True, index=True)  
     
    auth_config: Dict = Field(default_factory=dict, sa_column=Column(JSON)) 
    integrations_config: Dict = Field(default_factory=dict, sa_column=Column(JSON))
     
    tickets: List["Ticket"] = Relationship(back_populates="platform")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 1. CUSTOMER (The "Who")
class Customer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: Optional[str] = None
    phone: Optional[str] = None
    
    # Relationship: One Customer has many Tickets
    tickets: List["Ticket"] = Relationship(back_populates="customer")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# 2. TICKET (The "Issue")
class Ticket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Link to Customer
    customer_id: Optional[int] = Field(default=None, foreign_key="customer.id")
    customer: Optional[Customer] = Relationship(back_populates="tickets")

    platform_id: Optional[int] = Field(default=None, foreign_key="platform.id")
    platform: Optional[Platform] = Relationship(back_populates="tickets")
    
    # Core Data
    subject: str
    status: str = Field(default="open") # open, in_progress, resolved, closed
    priority: str = Field(default="medium")
    
    # Relationship: One Ticket has many Messages
    messages: List["TicketMessage"] = Relationship(back_populates="ticket")
    
    # Relationship: One Ticket has one Classification (The AI Analysis)
    classification: Optional["TicketClassification"] = Relationship(back_populates="ticket")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# 3. TICKET MESSAGE (The "Chat History")
class TicketMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    ticket_id: int = Field(foreign_key="ticket.id")
    ticket: Optional[Ticket] = Relationship(back_populates="messages")
    
    sender_type: str # "customer" or "agent"
    sender_email: str
    body: str

    gmail_message_id: Optional[str] = Field(default=None, index=True, unique=True)
    
    # AI Embedding for this specific message (for semantic search later)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(1536))) # OpenAI uses 1536 dims
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# 4. TICKET CLASSIFICATION (The "AI Brain Dump")
class TicketClassification(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    ticket_id: int = Field(foreign_key="ticket.id", unique=True)
    ticket: Optional[Ticket] = Relationship(back_populates="classification")
    
    category: str = Field(default="uncategorized") # e.g., "Billing", "Tech Support"
    sentiment: str = Field(default="neutral")      # e.g., "Angry", "Happy"
    urgency: int = Field(default=1)                # 1-5 scale
    confidence_score: float = Field(default=0.0)
    
    # Store raw AI reasoning (Why did it choose this category?)
    reasoning: Optional[str] = None