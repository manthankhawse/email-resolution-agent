import os
from typing import TypedDict, Optional
from dotenv import load_dotenv

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END

load_dotenv()
 
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0   
)
 
class AgentState(TypedDict):
    subject: str
    body: str
    analysis: Optional[dict]  

 
def analyzer_node(state: AgentState):
    """
    Takes the raw email and uses LLM to classify and draft a reply.
    """
    print("🤖 Agent Node: Analyzing Ticket...")
     
    parser = JsonOutputParser()
    
    # Create the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an advanced Support AI. Analyze the email and output strictly valid JSON."),
        ("user", """
        Subject: {subject}
        Body: {body}
        
        Format instructions:
        {format_instructions}
        
        Extract:
        1. category (Billing, Tech, Feature, Spam, Grievance, Report, Subscription)
        2. sentiment (Positive, Neutral, Angry)
        3. urgency (1-5)
        4. confidence (0.0-1.0)
        5. suggested_reply (Polite, helpful response)
        """)
    ])
    
    # Chain it: Prompt -> LLM -> JSON Parser
    chain = prompt | llm | parser
    
    try:
        result = chain.invoke({
            "subject": state["subject"], 
            "body": state["body"],
            "format_instructions": parser.get_format_instructions()
        })
        # Update the state with the result
        return {"analysis": result}
        
    except Exception as e:
        print(f"❌ LangChain Error: {e}")
        # Fallback state on error
        return {"analysis": {
            "category": "Error", 
            "sentiment": "Neutral", 
            "urgency": 1,
            "suggested_reply": "We received your request and will review it manually."
        }}

# 4. BUILD THE GRAPH
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("analyze", analyzer_node)

# Add edges (The flow logic)
# Start -> Analyze -> End
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", END)

# Compile the graph into a runnable application
app = workflow.compile()

# 5. PUBLIC API FUNCTION
def analyze_ticket(subject: str, body: str):
    """
    The entry point called by main.py
    """
    inputs = {"subject": subject, "body": body}
    
    # Run the graph
    # We use invoke() to run it synchronously (or use ainvoke for async)
    result_state = app.invoke(inputs)
    
    return result_state["analysis"]