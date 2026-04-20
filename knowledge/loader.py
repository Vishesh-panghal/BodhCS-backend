"""
Domain Knowledge Loader — Singleton that reads per-subject JSON/MD files at startup
and provides a clean API for the teacher and diagram nodes.
"""
import os
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Base path for knowledge modules
_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__))

# Supported subjects (must match classifier output)
_SUBJECTS = ["OS", "DSA", "CN", "DBMS", "Cyber"]

# Map classifier output to directory name
_SUBJECT_DIR_MAP = {
    "OS": "os",
    "DSA": "dsa",
    "CN": "cn",
    "DBMS": "dbms",
    "Cyber": "cyber",
}


class DomainKnowledge:
    """
    Loads and caches per-subject knowledge modules.
    Singleton — instantiated once at server startup.
    """
    _instance = None
    _loaded = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._loaded:
            self._prompt_contexts: Dict[str, str] = {}
            self._reality_mappings: Dict[str, Dict[str, str]] = {}
            self._misconceptions: Dict[str, List[Dict[str, str]]] = {}
            self._diagram_hints: Dict[str, Dict[str, str]] = {}
            self._load_all()
            DomainKnowledge._loaded = True

    def _load_all(self):
        for subject in _SUBJECTS:
            dir_name = _SUBJECT_DIR_MAP.get(subject, subject.lower())
            subject_dir = os.path.join(_KNOWLEDGE_DIR, dir_name)

            if not os.path.isdir(subject_dir):
                logger.warning(f"Knowledge directory missing for {subject}: {subject_dir}")
                continue

            # Load prompt context (markdown)
            prompt_path = os.path.join(subject_dir, "prompt_context.md")
            if os.path.exists(prompt_path):
                with open(prompt_path, "r") as f:
                    self._prompt_contexts[subject] = f.read()
                logger.info(f"Loaded prompt_context for {subject}")

            # Load reality mappings (JSON dict)
            rm_path = os.path.join(subject_dir, "reality_mappings.json")
            if os.path.exists(rm_path):
                with open(rm_path, "r") as f:
                    self._reality_mappings[subject] = json.load(f)
                logger.info(f"Loaded {len(self._reality_mappings[subject])} reality mappings for {subject}")

            # Load misconceptions (JSON array)
            mc_path = os.path.join(subject_dir, "misconceptions.json")
            if os.path.exists(mc_path):
                with open(mc_path, "r") as f:
                    self._misconceptions[subject] = json.load(f)
                logger.info(f"Loaded {len(self._misconceptions[subject])} misconceptions for {subject}")

            # Load diagram hints (JSON dict)
            dh_path = os.path.join(subject_dir, "diagram_hints.json")
            if os.path.exists(dh_path):
                with open(dh_path, "r") as f:
                    self._diagram_hints[subject] = json.load(f)
                logger.info(f"Loaded {len(self._diagram_hints[subject])} diagram hints for {subject}")

    # ── Public API ──

    def get_prompt_context(self, subject: str) -> str:
        """Returns the full prompt_context.md for a subject, or a generic fallback."""
        return self._prompt_contexts.get(subject, "You are a Computer Science tutor. Teach clearly with analogies and examples.")

    def get_reality_mappings(self, subject: str, query: str, top_k: int = 4) -> str:
        """
        Returns the most relevant reality mappings for a query via simple keyword matching.
        Returns a formatted string ready for prompt injection.
        """
        mappings = self._reality_mappings.get(subject, {})
        if not mappings:
            return "No specific real-world mappings available for this subject yet."

        query_lower = query.lower()

        # Score each mapping by keyword overlap with the query
        scored = []
        for concept, mapping_text in mappings.items():
            concept_words = set(concept.lower().split())
            query_words = set(query_lower.split())
            # Simple overlap score
            overlap = len(concept_words & query_words)
            # Also check if concept name appears as substring in query
            if concept.lower() in query_lower:
                overlap += 3  # Strong boost
            scored.append((overlap, concept, mapping_text))

        # Sort by score descending, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        top_matches = scored[:top_k]

        # Format for prompt injection
        lines = []
        for score, concept, text in top_matches:
            lines.append(f"- **{concept}**: {text}")

        return "\n".join(lines) if lines else "No closely matching real-world mappings found."

    def get_misconceptions(self, subject: str) -> str:
        """Returns formatted misconceptions for prompt injection."""
        misconceptions = self._misconceptions.get(subject, [])
        if not misconceptions:
            return "No documented misconceptions for this subject yet."

        lines = []
        for mc in misconceptions:
            lines.append(f"- ❌ MYTH: \"{mc['myth']}\" → ✅ TRUTH: {mc['truth']}")

        return "\n".join(lines)

    def get_diagram_hint(self, subject: str, query: str) -> str:
        """Returns the best diagram layout style for the concept in the query."""
        hints = self._diagram_hints.get(subject, {})
        if not hints:
            return "tree layout"  # Safe default

        query_lower = query.lower()

        for keyword, diagram_type in hints.items():
            if keyword.replace("_", " ") in query_lower or keyword in query_lower:
                # Convert old Mermaid-style hints to layout descriptions
                dt = diagram_type.lower()
                if "sequence" in dt:
                    return "linear flow (step-by-step process)"
                elif "class" in dt:
                    return "hierarchy (parent-child relationships)"
                elif "state" in dt:
                    return "state transitions (states connected by events)"
                else:
                    return "tree layout (root branching to children)"

        return "tree layout"  # Fallback
