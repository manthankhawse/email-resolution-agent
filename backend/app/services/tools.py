from langchain_core.tools import tool
from typing import Dict

# --- MOCK DATABASE (Simulating QuickBooks/Stripe) ---
MOCK_INVOICES = {
    "INV-2024-001": {"status": "PAID", "amount": 50.00, "date": "2024-01-15"},
    "INV-2024-002": {"status": "UNPAID", "amount": 120.50, "date": "2024-02-01"},
    "INV-99": {"status": "OVERDUE", "amount": 999.00, "date": "2023-12-01"},
}

MOCK_SUBSCRIPTIONS = {
    "sub_123": {"plan": "Pro", "status": "active", "renewal_date": "2024-03-01"},
    "sub_456": {"plan": "Starter", "status": "canceled", "renewal_date": "2023-01-01"},
}

# --- THE TOOLS ---

@tool
def fetch_invoice(invoice_id: str) -> Dict:
    """
    Looks up invoice details from the billing system.
    
    Args:
        invoice_id: The invoice identifier (e.g., "INV-2024-001")
    
    Returns:
        Dictionary containing:
        - invoice_id: The invoice number
        - status: Payment status (PAID, UNPAID, OVERDUE)
        - amount: Invoice amount in USD
        - date: Invoice date (YYYY-MM-DD)
        
        Or {"error": "Invoice not found"} if not found.
    
    Use this when the customer asks about a specific invoice.
    """
    print(f"🔧 TOOL CALL: Fetching Invoice {invoice_id}...")
    result = MOCK_INVOICES.get(invoice_id)
    
    if result:
        return {"invoice_id": invoice_id, **result}
    else:
        return {"error": "Invoice not found"}


@tool
def fetch_subscription(email: str) -> Dict:
    """
    Looks up subscription details from the subscription management system.
    
    Args:
        email: Customer's email address
    
    Returns:
        Dictionary containing:
        - plan: Subscription plan name
        - status: active, canceled, or expired
        - renewal_date: Next renewal date (YYYY-MM-DD)
        
        Or {"error": "No active subscription found"} if not found.
    
    Use this when the customer asks about their subscription, plan, or renewal.
    """
    print(f"🔧 TOOL CALL: Fetching Subscription for {email}...")
    # Mock logic: hash email to pick a sub
    if "manthan" in email.lower():
        return MOCK_SUBSCRIPTIONS["sub_123"]
    else:
        return {"error": "No active subscription found"}


# Export the list so we can pass it to the Agent
ALL_TOOLS = [fetch_invoice, fetch_subscription]