import asyncio
import logging
from core.database import get_supabase_client

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify():
    supabase = get_supabase_client()
    
    # Get total count
    response = supabase.table("knowledge_chunks").select("id", count="exact").limit(1).execute()
    total_chunks = response.count
    
    # Get count by subject
    subjects = ["OS", "DSA"]
    stats = {}
    for sub in subjects:
        resp = supabase.table("knowledge_chunks").select("id", count="exact").eq("subject", sub).limit(1).execute()
        stats[sub] = resp.count

    print("\n" + "="*50)
    print("📊 BODHCS KNOWLEDGE BASE STATS")
    print("="*50)
    print(f"Total Chunks: {total_chunks}")
    for sub, count in stats.items():
        print(f" - {sub}: {count} chunks")
    print("="*50)
    
    # Check for recent additions
    print("\nRecent Sources Processed:")
    resp = supabase.table("knowledge_chunks").select("metadata->>source_id, topic").limit(10).order("id", desc=True).execute()
    seen = set()
    for row in resp.data:
        sid = row.get('source_id', 'Unknown')
        topic = row.get('topic', 'Unknown')
        if sid not in seen:
            print(f" ✅ {sid}: {topic}")
            seen.add(sid)
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(verify())
