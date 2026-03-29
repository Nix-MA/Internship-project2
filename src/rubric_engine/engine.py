"""
rubric_engine/engine.py — Core rubric-driven grading engine.

grade_with_rubric():
    Wraps any grader output into the canonical rubric result format.
    For deterministic/semi-structured/structured types, maps scalar score → criteria_scores.
    For LLM types, expects the LLM to return per-criterion scores.

Canonical result format:
    {
        "criteria_scores":   {criterion_name: int, ...},
        "weighted_scores":   {criterion_name: float, ...},
        "total_score":        int,
        "max_score":          int,
        "percentage":         float,
        "is_correct":         bool,
        "feedback":           str,
        "strengths":          str,
        "weaknesses":         str,
        "improvements":       str,
        "hint":               str,
        "rubric_applied":     str   # question type label
    }
"""

from src.rubric_engine.rubrics import get_rubric, Rubric
from src.utils.helpers import sanitize_score


def grade_with_rubric(
    question: dict,
    raw_result: dict,
    rubric: Rubric | None = None,
) -> dict:
    """
    Post-process a raw grader result into the canonical rubric result format.

    Args:
        question:   The full question dict (needs "type" and "marks").
        raw_result: Output from a deterministic/LLM grader. Must contain "score".
        rubric:     Optional explicit rubric; if None, looked up from question type.

    Returns:
        Canonical rubric result dict.
    """
    q_type = question.get("type", "MCQ")
    max_score = question.get("marks", 1)

    if rubric is None:
        rubric = get_rubric(q_type)

    criteria = rubric["criteria"]
    strategy = rubric["strategy"]

    total_score = sanitize_score(raw_result.get("score", 0), max_score)

    # ── Build per-criterion scores ────────────────────────────────────────────
    if strategy == "llm" and "criteria_scores" in raw_result:
        # LLM returned per-criterion raw integers; validate + clamp
        llm_scores = raw_result["criteria_scores"]
        criteria_scores = {}
        weighted_scores = {}

        for crit in criteria:
            name   = crit["name"]
            weight = crit["weight"]
            # Calculate max possible for this criterion
            crit_max = max_score * weight
            raw_val  = llm_scores.get(name, 0)
            clamped  = sanitize_score(raw_val, round(crit_max))
            criteria_scores[name]  = clamped
            weighted_scores[name]  = round(clamped * weight, 2)

        # Recalculate total from weighted sum to ensure consistency
        total_score = min(max_score, sum(
            sanitize_score(llm_scores.get(c["name"], 0), round(max_score * c["weight"]))
            for c in criteria
        ))

    else:
        # For non-LLM types: distribute score proportionally across criteria
        criteria_scores = {}
        weighted_scores = {}
        score_ratio = total_score / max_score if max_score else 0

        for crit in criteria:
            name   = crit["name"]
            weight = crit["weight"]
            crit_max = max_score * weight
            earned   = round(score_ratio * crit_max, 2)
            criteria_scores[name] = round(earned)
            weighted_scores[name] = round(earned * weight, 2)

    percentage = round((total_score / max_score) * 100, 1) if max_score else 0.0
    is_correct = (total_score == max_score)

    # ── Pull narrative fields ─────────────────────────────────────────────────
    feedback     = raw_result.get("feedback", "")
    strengths    = raw_result.get("strengths", _auto_strengths(criteria_scores, criteria, max_score))
    weaknesses   = raw_result.get("weaknesses", _auto_weaknesses(criteria_scores, criteria, max_score))
    improvements = raw_result.get("improvements", "")
    hint         = raw_result.get("hint", question.get("explanation", ""))

    return {
        "criteria_scores":  criteria_scores,
        "weighted_scores":  weighted_scores,
        "total_score":      total_score,
        "max_score":        max_score,
        "percentage":       percentage,
        "is_correct":       is_correct,
        "feedback":         feedback,
        "strengths":        strengths,
        "weaknesses":       weaknesses,
        "improvements":     improvements,
        "hint":             hint,
        "rubric_applied":   q_type,
        "status":           raw_result.get("status", "success"),
        # Legacy aliases (keep backward compat with app.py)
        "score":            total_score,
    }


# ── Auto-narrative for non-LLM types ──────────────────────────────────────────

def _auto_strengths(criteria_scores: dict, criteria: list, max_score: int) -> str:
    """Generate a brief strength description from criterion scores."""
    if max_score == 0:
        return ""
    strong = [
        c["name"].replace("_", " ").title()
        for c in criteria
        if criteria_scores.get(c["name"], 0) >= round(max_score * c["weight"] * 0.8)
    ]
    return f"Strong in: {', '.join(strong)}." if strong else ""


def _auto_weaknesses(criteria_scores: dict, criteria: list, max_score: int) -> str:
    """Generate a brief weakness description from criterion scores."""
    if max_score == 0:
        return ""
    weak = [
        c["name"].replace("_", " ").title()
        for c in criteria
        if criteria_scores.get(c["name"], 0) < round(max_score * c["weight"] * 0.5)
    ]
    return f"Needs improvement in: {', '.join(weak)}." if weak else ""
