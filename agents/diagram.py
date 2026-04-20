import re
import json
import logging
from langchain_core.prompts import ChatPromptTemplate
from engines.llm_config import explanation_llm
from agents.state import LearningState
from knowledge.loader import DomainKnowledge

logger = logging.getLogger(__name__)

# Initialize domain knowledge singleton
_domain = DomainKnowledge()

DIAGRAM_SYSTEM_PROMPT = """You are a diagram structure generator for CS education.
Layout hint: {diagram_hint}

Your job: read the explanation and create a structured JSON diagram that ACCURATELY
represents the concepts described.

STEP 1 - Analyze the concept type:
- CATEGORIZATION (types, kinds, classes) → tree: one root branching to categories
- PROCESS (steps, flow, lifecycle) → flow: sequential chain of steps
- COMPARISON (vs, differences) → parallel branches from a common root
- RELATIONSHIP (components, architecture) → connected nodes showing how parts relate

STEP 2 - Extract REAL entities from the explanation. Do NOT invent generic filler.

OUTPUT FORMAT: Return ONLY valid JSON with this exact structure (do NOT use markdown formatting).
{{
  "nodes": [
    {{"id": "A", "label": "Operating Systems", "color": "blue"}},
    {{"id": "B", "label": "Batch OS", "color": "green"}},
    {{"id": "C", "label": "Time-Sharing", "color": "green"}}
  ],
  "edges": [
    {{"from": "A", "to": "B", "label": "type"}},
    {{"from": "A", "to": "C"}}
  ],
  "direction": "TB"
}}

RULES:
1. Output ONLY raw JSON. No markdown fences, no explanation, no extra text.
2. 3-7 nodes maximum. Keep it focused and easy to read.
3. Valid colors: blue, green, purple, orange, teal, pink, slate
4. Every edge "from" and "to" must reference existing node "id" values.
5. Node labels should be 1-4 words. Keep them concise.
6. Edge "label" is optional. Use only when it adds clarity.
7. Use "id" values like A, B, C, D... (single uppercase letters).
8. "direction" is always "TB" (top to bottom).
9. The root/main concept should use color "blue".
10. Keep structure hierarchical and clean: avoid cross-links and avoid multiple parents for the same node.
11. Keep edge labels very short (1-2 words) and only when necessary.

Explanation:
{explanation}
"""


# Valid colors for node rendering
_VALID_COLORS = {"blue", "green", "purple", "orange", "teal", "pink", "slate"}


def _parse_diagram_json(raw: str) -> str:
    """Parse and validate LLM-generated diagram JSON. Returns clean JSON or empty string."""
    code = raw.strip()

    # Strip markdown fences if present
    code = code.replace("```json", "").replace("```", "").strip()

    # Try to extract JSON object if there's surrounding text
    match = re.search(r'\{[\s\S]*\}', code)
    if match:
        code = match.group(0)

    try:
        data = json.loads(code)
    except json.JSONDecodeError as e:
        logger.warning(f"Diagram JSON parse failed: {e}\nRaw output: {raw}")
        return ""

    # Validate required fields
    if not isinstance(data, dict):
        logger.warning("Diagram data is not a dict")
        return ""

    nodes = data.get("nodes", [])
    edges = data.get("edges", [])

    if not isinstance(nodes, list) or len(nodes) == 0:
        logger.warning("Diagram has no nodes")
        return ""

    if not isinstance(edges, list):
        edges = []

    # Validate and clean nodes
    valid_ids = set()
    clean_nodes = []
    for node in nodes[:8]:  # Cap nodes for readability
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id", "")).strip()
        label = str(node.get("label", "")).strip()
        color = str(node.get("color", "slate")).strip().lower()

        if not node_id or not label:
            continue

        if color not in _VALID_COLORS:
            color = "slate"

        # Truncate long labels
        if len(label) > 28:
            label = label[:25] + "..."

        valid_ids.add(node_id)
        clean_nodes.append({"id": node_id, "label": label, "color": color})

    if len(clean_nodes) < 2:
        logger.warning("Diagram has fewer than 2 valid nodes")
        return ""

    # Validate and clean edges
    # Keep the structure simple: de-duplicate edges and allow only one parent per node.
    clean_edges = []
    parent_of = {}
    seen_pairs = set()
    max_edges = max(1, len(clean_nodes) - 1)
    for edge in edges[:24]:
        if not isinstance(edge, dict):
            continue
        from_id = str(edge.get("from", "")).strip()
        to_id = str(edge.get("to", "")).strip()

        if from_id not in valid_ids or to_id not in valid_ids:
            continue
        if from_id == to_id:
            continue
        pair = (from_id, to_id)
        if pair in seen_pairs:
            continue
        if to_id in parent_of:
            continue

        clean_edge = {"from": from_id, "to": to_id}
        label = edge.get("label")
        if label and isinstance(label, str) and label.strip():
            clean_label = label.strip()
            if len(clean_label) > 14:
                clean_label = clean_label[:11] + "..."
            clean_edge["label"] = clean_label

        clean_edges.append(clean_edge)
        parent_of[to_id] = from_id
        seen_pairs.add(pair)
        if len(clean_edges) >= max_edges:
            break

    # Fallback to a simple chain if model output had no usable edges.
    if not clean_edges and len(clean_nodes) >= 2:
        for index in range(len(clean_nodes) - 1):
            clean_edges.append({
                "from": clean_nodes[index]["id"],
                "to": clean_nodes[index + 1]["id"],
            })

    # Connect orphan nodes directly to root to avoid disconnected clutter.
    if clean_nodes and len(clean_edges) < max_edges:
        root_id = clean_nodes[0]["id"]
        attached = {edge["to"] for edge in clean_edges}
        attached.add(root_id)
        for node in clean_nodes:
            node_id = node["id"]
            if node_id in attached:
                continue
            clean_edges.append({"from": root_id, "to": node_id})
            if len(clean_edges) >= max_edges:
                break

    result = {
        "nodes": clean_nodes,
        "edges": clean_edges,
        "direction": data.get("direction", "TB"),
    }

    return json.dumps(result, ensure_ascii=False)


async def diagram_node(state: LearningState) -> LearningState:
    logger.info("Node: diagram")

    explanation = state.get("explanation", "")
    if not explanation:
        return state

    subject = state.get("subject", "General")
    query = state.get("query", "")

    # Get domain-specific diagram hint
    diagram_hint = _domain.get_diagram_hint(subject, query)

    prompt = ChatPromptTemplate.from_messages([
        ("system", DIAGRAM_SYSTEM_PROMPT),
        ("human", "Create a diagram for the above explanation.")
    ])

    # Use explanation_llm which has a higher token limit (2048) and support for JSON output
    # Llama 3.1 8b supports JSON mode
    diagram_llm = explanation_llm.bind(response_format={"type": "json_object"})
    chain = prompt | diagram_llm

    try:
        response = await chain.ainvoke({
            "explanation": explanation,
            "diagram_hint": diagram_hint,
        })
        clean_json = _parse_diagram_json(response.content)
        if clean_json:
            logger.info(f"Parsed diagram JSON ({len(json.loads(clean_json)['nodes'])} nodes)")
        else:
            logger.warning("Diagram JSON parsing produced empty result")
        state["diagram_source"] = clean_json
    except Exception as e:
        logger.error(f"Diagram generation failed: {e}")
        state["diagram_source"] = ""

    return state
