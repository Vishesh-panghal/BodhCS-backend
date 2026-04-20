from langgraph.graph import StateGraph, END
from agents.state import LearningState
from agents.classifier import classifier_node
from agents.rag import rag_node
from agents.reasoner import reasoner_node
from agents.teacher import teacher_node
from agents.diagram import diagram_node
from agents.composer import composer_node
from agents.routing import route_after_classify, should_add_diagram

def build_learning_graph() -> StateGraph:
    """Builds and compiles the BodhCS orchestrated LangGraph."""
    workflow = StateGraph(LearningState)

    # Add Nodes
    workflow.add_node("rag", rag_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("reasoner", reasoner_node)
    workflow.add_node("teacher", teacher_node)
    workflow.add_node("diagram", diagram_node)
    workflow.add_node("composer", composer_node)

    # Set Entry Point
    workflow.set_entry_point("rag")

    # Flow
    # 1. RAG -> Classifier
    workflow.add_edge("rag", "classifier")
    
    # 2. Classifier -> Conditional Route
    workflow.add_conditional_edges(
        "classifier",
        route_after_classify,
        {
            "socratic": "teacher", # For test intent we map to teacher for now, since we haven't built explicit socratic quiz generator
            "reasoner": "reasoner",
            "teacher": "teacher"
        }
    )
    
    # 3. Reasoner -> Teacher
    workflow.add_edge("reasoner", "teacher")
    
    # 4. Teacher -> Conditional Route for Diagram
    workflow.add_conditional_edges(
        "teacher",
        should_add_diagram,
        {
            "diagram": "diagram",
            "composer": "composer"
        }
    )
    
    # 5. Diagram -> Composer
    workflow.add_edge("diagram", "composer")
    
    # 6. Composer -> END
    workflow.add_edge("composer", END)

    # Compile the graph
    app = workflow.compile()
    return app
