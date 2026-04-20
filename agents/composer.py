import logging
from agents.state import LearningState

logger = logging.getLogger(__name__)

def composer_node(state: LearningState) -> LearningState:
    """
    Finalizes the payload so that it aligns closely with the expected API response.
    This node doesn't run LLMs; it just shapes the Dictionary.
    """
    logger.info("Node: composer")
    
    final_response = {
        "text": state.get("explanation", ""),
        "diagram": state.get("diagram_source", ""),
        "metadata": {
            "subject": state.get("subject", ""),
            "complexity": state.get("complexity", ""),
            "bloom_level": state.get("bloom_level", ""),
        }
    }
    
    state["response"] = final_response
    return state
