from langchain_groq import ChatGroq
from core.config import settings

# Explanation engine (teaching, analogies, structured output)
explanation_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3,
    max_tokens=2048,
    api_key=settings.GROQ_API_KEY,
    streaming=True,
)

# Reasoning engine (logic, math, step-by-step flows)
# Note: DeepSeek via Groq uses 'deepseek-r1-distill-llama-70b'
reasoning_llm = ChatGroq(
    model="deepseek-r1-distill-llama-70b",
    temperature=0.1,
    max_tokens=4096,
    api_key=settings.GROQ_API_KEY,
    streaming=False,  # Consumed fully before passing to teacher
)

# Classifier (fast, structured output)
classifier_llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.0,
    max_tokens=256,
    api_key=settings.GROQ_API_KEY,
    streaming=False,
)
