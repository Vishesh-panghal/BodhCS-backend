import json
import asyncio
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from api.auth import get_current_user
from agents.graph import build_learning_graph
from agents.state import convert_history

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

# Initialize the graph once
graph_app = build_learning_graph()


class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


def _sse(event_type: str, data=None) -> str:
    """Format an SSE event."""
    payload = {"type": event_type}
    if data is not None:
        payload["data"] = data
    return f"data: {json.dumps(payload)}\n\n"


class TeacherTokenStreamer(AsyncCallbackHandler):
    """
    Intercepts streaming tokens from the teacher LLM (tagged 'teacher_llm')
    and pushes them into an asyncio.Queue for the SSE generator.
    Ignores tokens from all other LLMs (classifier, diagram, reasoner).
    """
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self._active_teacher_runs = set()
    
    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], *, 
                           run_id=None, tags=None, **kwargs) -> None:
        """Track which runs are from the teacher LLM."""
        if tags and "teacher_llm" in tags:
            self._active_teacher_runs.add(run_id)
    
    async def on_llm_new_token(self, token: str, *, run_id=None, **kwargs) -> None:
        """Only stream tokens from teacher runs."""
        if run_id in self._active_teacher_runs and token:
            await self.queue.put(token)
    
    async def on_llm_end(self, response: LLMResult, *, run_id=None, **kwargs) -> None:
        """Clean up when teacher LLM finishes."""
        if run_id in self._active_teacher_runs:
            self._active_teacher_runs.discard(run_id)
            await self.queue.put(None)  # Sentinel: teacher stream done


# Status messages for each node
NODE_STATUS = {
    "rag": "Searching knowledge base...",
    "classifier": "Analyzing your question...",
    "reasoner": "Deep reasoning (DeepSeek R1)...",
    "teacher": "Crafting explanation...",
    "diagram": "Drawing diagram...",
}


@router.post("")
async def chat_stream(request: ChatRequest, _current_user=Depends(get_current_user)):
    """
    Streaming chat endpoint using SSE.
    
    Architecture:
    1. LangGraph runs via astream(stream_mode='updates') in a background task
    2. A TeacherTokenStreamer callback intercepts only teacher LLM tokens
    3. The SSE generator interleaves token events with node-level status events
    4. Falls back to full_text if no tokens were streamed
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def event_generator():
        history_messages = convert_history(request.history)
        initial_state = {
            "query": request.message,
            "history": history_messages,
        }
        
        token_queue: asyncio.Queue = asyncio.Queue()
        event_queue: asyncio.Queue = asyncio.Queue()
        streamer = TeacherTokenStreamer(token_queue)
        
        async def run_graph():
            try:
                async for chunk in graph_app.astream(
                    initial_state,
                    stream_mode="updates",
                    config={"callbacks": [streamer]},
                ):
                    for node_name, node_output in chunk.items():
                        # Push status events
                        if node_name in NODE_STATUS:
                            await event_queue.put(("status", NODE_STATUS[node_name]))
                        
                        # Push diagram
                        if node_name == "diagram":
                            diagram = node_output.get("diagram_source", "")
                            if diagram:
                                await event_queue.put(("diagram", diagram))
                        
                        # Push full text from composer as fallback
                        if node_name == "composer":
                            resp = node_output.get("response", {})
                            text = resp.get("text", "") if isinstance(resp, dict) else ""
                            if text:
                                await event_queue.put(("full_text", text))
                
                await event_queue.put(("graph_done", None))
            except Exception as e:
                logger.error(f"Graph failed: {e}", exc_info=True)
                await event_queue.put(("error", str(e)))
        
        graph_task = asyncio.create_task(run_graph())
        
        token_count = 0
        graph_done = False
        
        try:
            while not graph_done:
                # Drain event queue
                while True:
                    try:
                        etype, edata = event_queue.get_nowait()
                        if etype == "status":
                            yield _sse("status", edata)
                        elif etype == "diagram":
                            yield _sse("diagram", edata)
                        elif etype == "full_text":
                            if token_count == 0:
                                yield _sse("full_text", edata)
                        elif etype == "graph_done":
                            graph_done = True
                            break
                        elif etype == "error":
                            yield _sse("error", edata)
                            graph_done = True
                            break
                    except asyncio.QueueEmpty:
                        break
                
                if graph_done:
                    break
                
                # Drain token queue
                while True:
                    try:
                        token = token_queue.get_nowait()
                        if token is None:
                            break  # Teacher stream sentinel
                        token_count += 1
                        yield _sse("token", token)
                    except asyncio.QueueEmpty:
                        break
                
                await asyncio.sleep(0.015)
            
            # Final drain
            while not token_queue.empty():
                token = token_queue.get_nowait()
                if token is not None:
                    token_count += 1
                    yield _sse("token", token)
            
            yield _sse("done")
            
        finally:
            if not graph_task.done():
                await graph_task

    return StreamingResponse(event_generator(), media_type="text/event-stream")
