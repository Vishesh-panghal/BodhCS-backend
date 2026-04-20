import json
import logging
from langchain_core.prompts import ChatPromptTemplate
from engines.llm_config import classifier_llm
from agents.state import LearningState

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """You are a classification engine for a Computer Science learning system.
Analyze the user's query and extract the following metadata:

1. **subject**: The primary domain. Choose from: ["OS", "DSA", "CN", "DBMS", "Cyber", "General"]
   - Paging, Process, Thread, Deadlock, Memory -> OS
   - Trees, Graphs, Sorting, Time Complexity -> DSA
   - TCP/IP, Routing, Sockets -> CN
   - SQL, Normalization, Transactions -> DBMS
   - Encryption, Firewall, XSS, SQL Injection, Authentication, Hacking, Phishing, TLS, VPN, Malware -> Cyber
2. **intent**: What does the user want? Choose from: ["learn", "revise", "test"]
   - "learn" (default) -> Explain a concept deeply
   - "revise" -> Wants short notes, summary, key points
   - "test" -> Wants to be quizzed
3. **bloom_level**: The cognitive level. Choose from: ["remember", "understand", "apply", "analyze", "evaluate", "create"]
   - "What is..." -> remember
   - "How does... work" / "Explain..." -> understand
   - "Given this scenario..." -> apply
   - "Compare a and b..." / "Why is..." -> analyze
4. **complexity**: Question difficulty. Choose from: ["simple", "medium", "complex"]
   - Definitions -> simple
   - Workings / Mechanisms -> medium
   - Math / Deep logic / Edge cases / Heavy proofs -> complex

Output EXACTLY as a JSON object with keys: "subject", "intent", "bloom_level", "complexity". No other text.
"""

def classifier_node(state: LearningState) -> LearningState:
    logger.info("Node: classifier")
    query = state["query"]
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", CLASSIFIER_SYSTEM_PROMPT),
        ("human", "{query}")
    ])
    
    # Enable JSON mode for ChatGroq
    llm_with_json = classifier_llm.bind(response_format={"type": "json_object"})
    chain = prompt | llm_with_json
    
    try:
        response = chain.invoke({"query": query})
        parsed = json.loads(response.content)
        
        # Merge parsed data into state
        state["subject"] = parsed.get("subject", "General")
        state["intent"] = parsed.get("intent", "learn")
        state["bloom_level"] = parsed.get("bloom_level", "understand")
        state["complexity"] = parsed.get("complexity", "medium")
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        # Defaults
        state["subject"] = "General"
        state["intent"] = "learn"
        state["bloom_level"] = "understand"
        state["complexity"] = "medium"
        
    return state
