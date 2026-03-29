"""
rubric_engine/rubrics.py — Rubric definitions for all 8 question types.

Each rubric defines:
- criteria: list of {name, weight} (weights must sum to 1.0)
- strategy: "deterministic" | "semi_structured" | "structured" | "llm"
- description: human-readable explanation of grading intent
"""

from typing import TypedDict


class Criterion(TypedDict):
    name: str
    weight: float


class Rubric(TypedDict):
    criteria: list[Criterion]
    strategy: str
    description: str


RUBRICS: dict[str, Rubric] = {

    # ── Deterministic (exact match, binary) ──────────────────────────────────

    "MCQ": {
        "criteria": [
            {"name": "accuracy", "weight": 1.0},
        ],
        "strategy": "deterministic",
        "description": "Single correct letter selection. Full marks or zero.",
    },

    "True / False": {
        "criteria": [
            {"name": "accuracy", "weight": 1.0},
        ],
        "strategy": "deterministic",
        "description": "Binary true/false judgement. Full marks or zero.",
    },

    "Assertion & Reason": {
        "criteria": [
            {"name": "accuracy", "weight": 1.0},
        ],
        "strategy": "deterministic",
        "description": "Single correct option (A/B/C/D). Full marks or zero.",
    },

    # ── Semi-structured (exact + fuzzy) ──────────────────────────────────────

    "One Word Answer": {
        "criteria": [
            {"name": "accuracy",  "weight": 0.8},
            {"name": "tolerance", "weight": 0.2},
        ],
        "strategy": "semi_structured",
        "description": (
            "Exact match preferred. Fuzzy match (>= 85% similarity) accepted "
            "for minor spelling variations. Tolerance covers acceptable variants."
        ),
    },

    "Fill in the Blanks": {
        "criteria": [
            {"name": "accuracy",  "weight": 0.7},
            {"name": "tolerance", "weight": 0.3},
        ],
        "strategy": "semi_structured",
        "description": (
            "Per-blank scoring. Exact match gives full per-blank credit. "
            "Fuzzy match (>= 80% similarity) gives partial credit."
        ),
    },

    # ── Structured (per-pair) ─────────────────────────────────────────────────

    "Match the Following": {
        "criteria": [
            {"name": "pair_correctness", "weight": 0.8},
            {"name": "consistency",      "weight": 0.2},
        ],
        "strategy": "structured",
        "description": (
            "Each correct pair earns proportional marks. "
            "Consistency bonus for all-or-nothing correct sets."
        ),
    },

    # ── Full rubric (LLM) ─────────────────────────────────────────────────────

    "Short Answer": {
        "criteria": [
            {"name": "accuracy",          "weight": 0.40},
            {"name": "completeness",      "weight": 0.30},
            {"name": "conceptual_clarity","weight": 0.20},
            {"name": "expression",        "weight": 0.10},
        ],
        "strategy": "llm",
        "description": (
            "LLM evaluates each criterion independently. "
            "accuracy: factual correctness vs model answer. "
            "completeness: all key points covered. "
            "conceptual_clarity: demonstrates understanding, not just recall. "
            "expression: coherent sentence structure and appropriate terminology."
        ),
    },

    "Long Answer": {
        "criteria": [
            {"name": "accuracy",          "weight": 0.35},
            {"name": "completeness",      "weight": 0.30},
            {"name": "conceptual_clarity","weight": 0.25},
            {"name": "expression",        "weight": 0.10},
        ],
        "strategy": "llm",
        "description": (
            "LLM evaluates each criterion independently with higher completeness weight. "
            "accuracy: factual alignment with model answer and document context. "
            "completeness: all required points/sections present. "
            "conceptual_clarity: deep understanding beyond surface recall. "
            "expression: structured writing with correct terminology."
        ),
    },
}


def get_rubric(question_type: str) -> Rubric:
    """
    Return the rubric for a given question type.
    Falls back to MCQ rubric (deterministic) for unknown types.
    """
    return RUBRICS.get(question_type, RUBRICS["MCQ"])
