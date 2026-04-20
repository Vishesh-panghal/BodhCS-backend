import logging
from langchain_core.prompts import ChatPromptTemplate
from engines.llm_config import reasoning_llm
from agents.state import LearningState

logger = logging.getLogger(__name__)

REASONER_SYSTEM_PROMPT = """You are the internal logical reasoning engine for BodhCS.
Your task is to analyze the user's query and the provided context from textbooks.

Do NOT attempt to have a conversation. 
Do NOT try to be friendly or use catchy hooks.
Your PURPOSE is to establish the "Technical Truth" and step-by-step logic that the Teaching Engine will later wrap into a lesson.

If mathematical or systematic flows are involved, break them down rigorously.
Output your structured reasoning clearly.

Context:
{context}
"""

async def reasoner_node(state: LearningState) -> LearningState:
    logger.info("Node: reasoner")
    
    query = state["query"]
    context_list = state.get("rag_context", [])
    context_str = "\n".join(context_list)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", REASONER_SYSTEM_PROMPT),
        ("human", "{query}")
    ])
    
    chain = prompt | reasoning_llm
    
    try:
        response = await chain.ainvoke({"query": query, "context": context_str})
        state["reasoning_output"] = response.content
    except Exception as e:
        logger.error(f"Reasoning failed: {e}")
        state["reasoning_output"] = ""
        
    return state
