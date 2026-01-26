import os
import json
from typing import TypedDict, Optional, Annotated
from dotenv import load_dotenv

# LangChain Imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition

# Import our new tools
from app.services.tools import ALL_TOOLS

load_dotenv()

# 1. SETUP MODEL
# 🔴 FIX 1: Use the STABLE model. '2.5' is causing the hallucinations.
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0
)
llm_with_tools = llm.bind_tools(ALL_TOOLS)

# 2. DEFINE STATE
from langgraph.graph.message import add_messages
class AgentState(TypedDict):
    messages: Annotated[list, add_messages] 
    final_analysis: Optional[dict] 

# 3. DEFINE NODES

def reasoner_node(state: AgentState):
    """
    The Brain. Decides whether to call a tool or just answer.
    """
    # Create a COPY of messages so we can inject things without saving them to DB
    messages = list(state["messages"])
    
    # 1. SYSTEM PROMPT
    if not isinstance(messages[0], SystemMessage):
        messages.insert(0, SystemMessage(content="""
        You are the 'Ticket Resolution Engine'.
        Your job is to query tools and REPORT FACTS.
        You are NOT a conversationalist. You are a reporter.
        """))

    # 🔴 FIX 2: THE GHOST INSTRUCTION 👻
    # If the last message was a Tool Output, we inject a "Voice of God" instruction
    # that forces the AI to treat it as data, not chat.
    if isinstance(messages[-1], ToolMessage):
        messages.append(HumanMessage(content="""
        [SYSTEM INSTRUCTION]
        The data above is from the INTERNAL DATABASE, not the user.
        
        TASK:
        1. Read the database log above.
        2. Answer the user's original question using this data.
        3. Do NOT thank the database.
        4. Do NOT say "Thanks for the update."
        5. Just state the facts.
        """))

    # Call the model
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}

def analysis_extractor_node(state: AgentState):
    """
    Final step: Take the conversation history and format it into JSON for our DB.
    """
    last_message = state["messages"][-1]
    
    structure_prompt = f"""
    Analyze this conversation history and extract the final structured data as JSON.
    Last message: {last_message.content}
    
    Output keys: category, sentiment, urgency, confidence, entities, rationale, error_message, suggested_reply
    """
    
    from langchain_core.output_parsers import JsonOutputParser
    parser = JsonOutputParser()
    chain = llm | parser
    
    try:
        result = chain.invoke(structure_prompt)
        
        # Sanitizers
        result["urgency"] = int(result.get("urgency", 1)) if str(result.get("urgency", "1")).isdigit() else 1
        try: result["confidence"] = float(result.get("confidence", 0.0))
        except: result["confidence"] = 0.0
                 
        return {"final_analysis": result}

    except Exception as e:
        return {"final_analysis": {
            "category": "Error", 
            "urgency": 1,
            "suggested_reply": last_message.content
        }}

# 4. BUILD THE GRAPH
workflow = StateGraph(AgentState)

workflow.add_node("agent", reasoner_node)
workflow.add_node("tools", ToolNode(ALL_TOOLS))
workflow.add_node("finalize", analysis_extractor_node)

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    tools_condition, 
    {"tools": "tools", "__end__": "finalize"}
)

workflow.add_edge("tools", "agent")
workflow.add_edge("finalize", END)

app = workflow.compile()

# 5. PUBLIC API
def analyze_ticket(subject: str, body: str):
    """
    Entry point. Now creates a conversation history.
    """
    initial_message = f"Subject: {subject}\nBody: {body}\n\nAnalyze this request. Use tools if you see Invoice IDs or need to check Subscriptions."
    inputs = {"messages": [HumanMessage(content=initial_message)]}
    result = app.invoke(inputs, config={"recursion_limit": 10})
    return result.get("final_analysis", {})