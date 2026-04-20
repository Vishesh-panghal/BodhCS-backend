from agents.state import LearningState

def route_after_classify(state: LearningState) -> str:
    """
    Complex queries go through DeepSeek first; simple ones skip to teacher.
    """
    intent = state.get("intent", "learn")
    complexity = state.get("complexity", "medium")

    if intent == "test":
        return "socratic"  # Or quiz generator
    
    if complexity == "complex":
        return "reasoner"  # Route to DeepSeek for deep logic
    
    return "teacher"  # Skip logic engine directly to explanation

def should_add_diagram(state: LearningState) -> str:
    """
    Bloom levels that benefit from visual aids get a diagram.
    """
    bloom_level = state.get("bloom_level", "understand")
    # Diagram applies to these cognitive levels
    if bloom_level in ["understand", "apply", "analyze", "create"]:
        return "diagram"
    
    return "composer"

