import logging
from typing import List, Dict, Any, AsyncGenerator
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langfuse.langchain import CallbackHandler

from core.config import settings
from rag.retriever import KnowledgeRetriever, RetrievedChunk

logger = logging.getLogger(__name__)

# --- TUTOR PERSONA PROMPT ---
SYSTEM_PROMPT = """You are **BodhCS** 🧠, a brilliant and charismatic AI Study Buddy for Computer Science students. You make complex topics feel simple and exciting.

## YOUR PERSONALITY:
- You are warm, encouraging, and a little witty — like the best TA a student ever had.
- You genuinely love CS and your enthusiasm shows in every answer.
- You use the Socratic method: don't just dump information — guide the student to "aha!" moments.

## RESPONSE FORMAT (CRITICAL — follow this every time):
1. **Start with a one-line hook** — a bold, catchy statement or real-world analogy that instantly grabs attention.
2. **Use clear structure** with Markdown:
   - Use `##` headings to break content into digestible sections.
   - Use **bold** for key terms when first introduced.
   - Use bullet points (`-`) and numbered lists for steps or comparisons.
   - Use `code blocks` for any code, pseudocode, or terminal commands.
   - Use > blockquotes for important takeaways or "remember this" nuggets.
3. **Include a real-world analogy** 🌍 — e.g., "Think of virtual memory like a library's index card system..."
4. **End with a Socratic question** 🤔 — ask the student a thought-provoking follow-up to keep them thinking.

## CONTENT RULES:
- **Authoritative Citations**: Cite your sources like [OSTEP Ch. 31] or [Erickson §5.4].
- **Cross-Subject Insights**: If an OS concept relates to DSA (or vice versa), mention it briefly.
- **Context Boundary**: If the provided context doesn't contain the answer, be honest and suggest what the student should explore.
- Keep responses **concise but complete** — aim for quality over quantity. No rambling.

## EXAMPLE RESPONSE STYLE:
> **Deadlocks are like a 4-way traffic jam where every car is waiting for the other to move first.** 🚗

## 🔍 What is a Deadlock?
A **deadlock** occurs when two or more processes are stuck forever, each waiting for a resource held by the other.

### The 4 Necessary Conditions (Coffman Conditions):
1. **Mutual Exclusion** — Only one process can use a resource at a time
2. **Hold & Wait** — A process holds one resource while waiting for another
3. **No Preemption** — Resources can't be forcibly taken away
4. **Circular Wait** — A circular chain of processes exists

> 💡 **Remember**: If you break *any one* of these four conditions, deadlocks become impossible! [OSTEP Ch. 32]

🤔 **Think about this**: If your OS uses a "resource ordering" strategy, which condition does it break and why?

---

## Context from Textbooks:
{context}
"""

class ChatBrain:
    def __init__(self):
        self.llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0.3, # Lower temperature for factual accuracy
            streaming=True
        )
        self.retriever = KnowledgeRetriever()
        self.langfuse_handler = CallbackHandler(
            public_key=settings.LANGFUSE_PUBLIC_KEY
        )

    def _format_docs(self, docs: List[RetrievedChunk]) -> str:
        formatted = []
        for doc in docs:
            formatted.append(f"Source: {doc.topic} ({doc.source})\nContent: {doc.content}\n---\n")
        return "\n".join(formatted)

    def _determine_subject(self, docs: List[RetrievedChunk]) -> str:
        """Auto-detect subject based on retrieval metadata."""
        if not docs:
            return "General CS"
        
        subjects = [doc.metadata.get('subject', 'General') for doc in docs]
        # Simplistic majority vote
        os_count = subjects.count('OS')
        dsa_count = subjects.count('DSA')
        
        if os_count > dsa_count:
            return "Operating Systems"
        elif dsa_count > os_count:
            return "Data Structures & Algorithms"
        return "Computer Science"

    async def answer(self, question: str, history: List[BaseMessage] = []) -> AsyncGenerator[str, None]:
        """
        Main RAG pipeline: 
        1. Contextualize question based on history.
        2. Retrieve chunks.
        3. Stream response with citations.
        """
        try:
            # 1. Retrieval
            # In a full LangChain implementation, we would use a 'condense_question_chain' here.
            # For efficiency, we search using the raw question or a lightly processed version.
            retrieved_docs = await self.retriever.search(question)
            context_text = self._format_docs(retrieved_docs)
            subject = self._determine_subject(retrieved_docs)
            
            # 2. Build Prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
            ])
            
            # 3. Chain logic
            chain = prompt | self.llm | StrOutputParser()
            
            # 4. Stream response
            logger.info(f"Generating response for detected subject: {subject}")
            
            # Inject metadata into Langfuse
            config = {
                "callbacks": [self.langfuse_handler],
                "metadata": {
                    "subject": subject,
                    "query": question,
                    "chunks_retrieved": len(retrieved_docs)
                }
            }
            
            # Stream the response
            async for chunk in chain.astream(
                {"context": context_text, "question": question, "history": history},
                config=config
            ):
                yield chunk

        except Exception as e:
            logger.error(f"Brain failure: {e}")
            yield "I encountered an error while processing your request. Please try again."

# Helper to convert list of dicts to LangChain messages
def convert_history(history_data: List[Dict[str, str]]) -> List[BaseMessage]:
    messages = []
    for msg in history_data:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    return messages
