import logging
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from core.database import get_supabase_client

logger = logging.getLogger(__name__)

class RetrievedChunk:
    def __init__(self, content: str, source: str, topic: str, similarity: float, metadata: Dict[str, Any]):
        self.content = content
        self.source = source
        self.topic = topic
        self.similarity = similarity
        self.metadata = metadata

class KnowledgeRetriever:
    """
    Handles similarity search for RAG using Supabase and pgvector.
    """
    _instance = None
    _model = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(KnowledgeRetriever, cls).__new__(cls)
        return cls._instance

    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        # Singleton pattern for the model to save memory
        if self._model is None:
            logger.info(f"Loading embedding model: {model_name}")
            self._model = SentenceTransformer(model_name)
        self.supabase = get_supabase_client()

    def get_embedding(self, text: str) -> List[float]:
        return self._model.encode(text).tolist()

    async def search(
        self, 
        query: str, 
        subject: Optional[str] = None, 
        match_threshold: float = 0.4, 
        match_count: int = 5
    ) -> List[RetrievedChunk]:
        """
        Performs vector similarity search via Supabase RPC.
        """
        try:
            query_embedding = self.get_embedding(query)
            
            rpc_params = {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_subject": subject
            }
            
            # Note: supabase-py's rpc() is sync in current version but we use it within async routes
            # We can wrap it in run_in_executor if blocking becomes an issue
            response = self.supabase.rpc("match_knowledge_chunks", rpc_params).execute()
            
            results = []
            for row in response.data:
                results.append(RetrievedChunk(
                    content=row['content'],
                    source=row['source'],
                    topic=row['topic'],
                    similarity=row['similarity'],
                    metadata=row['metadata']
                ))
            
            logger.info(f"Retrieved {len(results)} chunks for query: {query[:50]}...")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

# Usage: retriever = KnowledgeRetriever()
