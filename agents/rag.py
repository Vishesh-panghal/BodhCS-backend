import logging
from agents.state import LearningState
from rag.retriever import KnowledgeRetriever

logger = logging.getLogger(__name__)

async def rag_node(state: LearningState) -> LearningState:
    """Retrieves documents from Supabase pgvector based on the query."""
    logger.info("Node: rag")
    
    query = state["query"]
    subject = state.get("subject", None)
    
    try:
        retriever = KnowledgeRetriever()
        
        # Returns List[RetrievedChunk]
        docs = await retriever.search(query=query, subject=subject if subject and subject != "General" else None)
        
        context_chunks = [doc.content for doc in docs]
        state["rag_context"] = context_chunks
        
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        state["rag_context"] = []
        
    return state
