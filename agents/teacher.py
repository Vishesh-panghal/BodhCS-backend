import logging
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableConfig
from engines.llm_config import explanation_llm
from agents.state import LearningState
from knowledge.loader import DomainKnowledge

logger = logging.getLogger(__name__)

# Initialize domain knowledge singleton
_domain = DomainKnowledge()

TEACHER_SYSTEM_PROMPT = """You are BodhCS, an elite Computer Science tutor. Your goal is to make learning deeply engaging, logical, and impossible to forget.
You must strictly follow the pedagogy blueprint below. Use Markdown styling heavily (bolding key terms, using quotes).

Subject: {subject}
Complexity Level: {complexity}

DOMAIN EXPERTISE:
{domain_context}

REALITY MAPPINGS (weave these into your explanation naturally — don't list them verbatim):
{reality_mappings}

COMMON MISCONCEPTIONS (proactively address if the query touches on any of these):
{misconceptions}

CONTEXT (Textbook sources):
{context}

LOGICAL REASONING (from Reasoner Node, if any):
{reasoning_output}

YOUR REQUIRED STRUCTURE (You must include all 7 parts organically, make headers bold or H3):
1. 🎯 The Hook (Real-world analogy or problem statement that makes them care).
2. 📖 The "What" (Formal definition but in plain English. Bold key terms).
3. 🤷 The "Why" (Why was this invented? What problem does it solve?).
4. 🌍 The Analogy (A highly detailed, relatable analogy mapping technical terms to real-world equivalents).
5. ⚙️ The Flow/Mechanism (Step-by-step how it works. If complexity is 'complex', dive deep mathematically/logically using the Reasoning).
6. 💼 2 Use Cases (Where is this used in standard industrial apps? Tie to the reality mappings above).
7. 🎓 Exam Point & 🤔 Socratic Question (One common misconception from the list above, and a follow up thinking question to verify understanding).

Maintain a conversational but authoritative tone. Never be boring.
"""

async def teacher_node(state: LearningState, config: RunnableConfig = None) -> LearningState:
    logger.info("Node: teacher")
    
    query = state["query"]
    context_list = state.get("rag_context", [])
    context_str = "\n".join(context_list)
    reasoning_output = state.get("reasoning_output", "")
    subject = state.get("subject", "General")
    complexity = state.get("complexity", "Medium")
    
    # Fetch domain-specific enrichment
    domain_context = _domain.get_prompt_context(subject)
    reality_mappings = _domain.get_reality_mappings(subject, query)
    misconceptions = _domain.get_misconceptions(subject)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", TEACHER_SYSTEM_PROMPT),
        ("human", "{query}")
    ])
    
    # Tag the LLM for event filtering; pass through any callbacks from config
    chain = prompt | explanation_llm.with_config({"tags": ["teacher_llm"]})
    
    try:
        response = await chain.ainvoke(
            {
                "query": query, 
                "context": context_str,
                "reasoning_output": reasoning_output,
                "subject": subject,
                "complexity": complexity,
                "domain_context": domain_context,
                "reality_mappings": reality_mappings,
                "misconceptions": misconceptions,
            },
            config=config,  # Pass through LangGraph's config (includes callbacks)
        )
        state["explanation"] = response.content
    except Exception as e:
        logger.error(f"Teacher failed: {e}")
        state["explanation"] = "I encountered an error while trying to explain this. Could you try asking again?"
        
    return state
