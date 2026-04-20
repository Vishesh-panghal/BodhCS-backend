import os
import yaml
import httpx
import logging
import fitz  # PyMuPDF
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from core.database import get_supabase_client
from core.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SourceManager:
    """Manages the source manifest and downloading of documents."""
    def __init__(self, manifest_path: str):
        self.manifest_path = manifest_path
        self.sources = self._load_manifest()

    def _load_manifest(self) -> List[Dict[str, Any]]:
        with open(self.manifest_path, 'r') as f:
            data = yaml.safe_load(f)
        return data.get('sources', [])

    async def download_source(self, source: Dict[str, Any], download_dir: str) -> Optional[str]:
        url = source['url']
        source_id = source['id']
        file_type = source['type']
        
        file_name = f"{source_id}.{file_type}"
        file_path = os.path.join(download_dir, file_name)
        
        if os.path.exists(file_path):
            logger.info(f"File already exists: {file_path}")
            return file_path

        logger.info(f"Downloading {url} to {file_path}")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            try:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                return file_path
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                return None

class DocumentProcessor:
    """Processes downloaded files into raw text chunks."""
    
    @staticmethod
    def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
        doc = fitz.open(file_path)
        pages = []
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            # CRITICAL: Remove null bytes (\u0000) which crash PostgreSQL
            text = text.replace('\u0000', '')
            if text.strip():
                pages.append({
                    "content": text,
                    "metadata": {"page_number": page_num + 1}
                })
        return pages

    @staticmethod
    def parse_html(file_path: str) -> List[Dict[str, Any]]:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # Primitive chunking for HTML: split by headers or paragraphs
        # For simplicity, we'll just take the main content
        content = soup.get_text(separator='\n')
        return [{"content": content, "metadata": {}}]

class Chunker:
    """Splits raw text into semantic chunks."""
    def __init__(self, chunk_size: int = 1000, overlap: int = 200):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str) -> List[str]:
        # Basic sliding window chunking
        # In a real app, use recursive character splitter or semantic splitting
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - self.overlap
        return chunks

class Embedder:
    """Generates vector embeddings for text chunks."""
    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def embed(self, text: str) -> List[float]:
        embedding = self.model.encode(text)
        return embedding.tolist()

class VectorStore:
    """Interfaces with Supabase to store knowledge chunks."""
    def __init__(self):
        self.supabase = get_supabase_client()

    def upsert_chunks(self, chunks: List[Dict[str, Any]]):
        if not chunks:
            return
        
        try:
            # Using bulk insert
            response = self.supabase.table("knowledge_chunks").insert(chunks).execute()
            logger.info(f"Successfully inserted {len(chunks)} chunks.")
            return response
        except Exception as e:
            logger.error(f"Failed to insert chunks: {e}")
            raise

async def main():
    # Paths
    backend_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(backend_dir, "data")
    manifest_path = os.path.join(data_dir, "sources.yaml")
    download_dir = os.path.join(data_dir, "downloads")
    
    os.makedirs(download_dir, exist_ok=True)
    
    # Initialize components
    manager = SourceManager(manifest_path)
    chunker = Chunker()
    embedder = Embedder()
    store = VectorStore()
    
    for source in manager.sources:
        logger.info(f"Processing source: {source['id']}")
        
        # 0. Check for existence (to avoid duplicates)
        try:
            # We can't use .contains on jsonb easily with supabase-py without RPC or raw SQL
            # but we can filter by the 'metadata' column if we find a match
            # Actually, let's just use a simple approach: if rows exist with this source_id in metadata
            check = store.supabase.table("knowledge_chunks")\
                .select("id")\
                .filter("metadata->>source_id", "eq", source['id'])\
                .limit(1)\
                .execute()
            
            if check.data:
                logger.info(f"Source {source['id']} already exists in database. Skipping.")
                continue
        except Exception as e:
            logger.warning(f"Existence check failed for {source['id']}: {e}. Proceeding anyway.")

        # 1. Download
        file_path = await manager.download_source(source, download_dir)
        if not file_path:
            continue
            
        # 2. Parse
        if source['type'] == 'pdf':
            raw_docs = DocumentProcessor.parse_pdf(file_path)
        elif source['type'] == 'html':
            raw_docs = DocumentProcessor.parse_html(file_path)
        else:
            logger.warning(f"Unsupported type: {source['type']}")
            continue
            
        # 3. Chunk, Embed, and Prepare for Supabase
        db_payload = []
        for doc in raw_docs:
            chunks = chunker.split(doc['content'])
            for i, chunk_text in enumerate(chunks):
                embedding = embedder.embed(chunk_text)
                
                # Build metadata
                meta = doc['metadata'].copy()
                meta.update({
                    "chunk_index": i,
                    "source_id": source['id'],
                    "source_url": source['url']
                })
                
                db_payload.append({
                    "subject": source['subject'],
                    "topic": source['title'],
                    "content": chunk_text,
                    "source": source['url'],
                    "embedding": embedding,
                    "metadata": meta
                })
        
        # 4. Upload in batches
        batch_size = 50
        for i in range(0, len(db_payload), batch_size):
            batch = db_payload[i:i+batch_size]
            store.upsert_chunks(batch)
    
    logger.info("🎉 MASSIVE DATA EXPANSION COMPLETE!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
