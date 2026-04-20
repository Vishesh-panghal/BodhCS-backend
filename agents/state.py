from typing import TypedDict, Optional, List, Dict
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

class LearningState(TypedDict):
    """
    The shared state dictionary updated by each node in the LangGraph orchestrator.
    """
    # --- Input ---
    query: str                          # Raw user question
    history: List[BaseMessage]          # Conversation history
    
    # --- Classification ---
    subject: str                        # OS | DSA | CN | DBMS | Cyber | General
    intent: str                         # learn | revise | test
    bloom_level: str                    # remember | understand | apply | analyze | evaluate | create
    complexity: str                     # simple | medium | complex
    
    # --- Processing ---
    rag_context: List[str]              # Retrieved chunk strings
    reasoning_output: str               # DeepSeek's logical analysis
    
    # --- Output ---
    explanation: str                    # Teacher's pedagogical response
    diagram_source: str                 # JSON diagram structure: {nodes, edges, direction}
    response: Dict                      # Final composed response payload for SSE

def convert_history(history_data: List[Dict[str, str]]) -> List[BaseMessage]:
    """Helper to parse API history payload into Langchain Messages."""
    messages = []
    for msg in history_data:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                messages.append(AIMessage(content=msg["content"]))
    return messages
