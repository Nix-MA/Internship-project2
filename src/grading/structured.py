"""
grading/structured.py — Per-pair grader for Match the Following.

grade_match():
    Evaluates each pair independently using fuzzy match.
    Awards proportional marks per correct pair.
    Consistency bonus: +extra if all pairs correct.
"""

import json
from src.utils.helpers import normalize_answer

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False


def _sim(a: str, b: str) -> float:
    if _HAS_RAPIDFUZZ:
        return _fuzz.ratio(a, b)
    return 100.0 if a in b or b in a else 0.0


PAIR_THRESHOLD = 75  # minimum similarity to count a pair as correct


def grade_match(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade Match the Following by evaluating each pair.

    Args:
        question:       Question dict with "pairs": {left: right, ...}
        student_answer: JSON string {"left_item": "student_right", ...}
        marks:          Total marks for the question.

    Returns:
        Raw rubric-compatible result dict.
    """
    correct_pairs: dict = question.get("pairs", {})
    if not correct_pairs:
        return _fail(marks, "No pairs found in question definition.")

    # Parse student match answers
    try:
        if isinstance(student_answer, str):
            student_pairs = json.loads(student_answer)
        elif isinstance(student_answer, dict):
            student_pairs = student_answer
        else:
            student_pairs = {}
    except (json.JSONDecodeError, TypeError):
        return _fail(marks, "Could not parse your match answers.")

    if not student_pairs:
        return _fail(marks, "No match answers provided.")

    # Evaluate each pair
    total_pairs = len(correct_pairs)
    correct_count = 0
    feedback_lines = []

    for left, correct_right in correct_pairs.items():
        student_right = str(student_pairs.get(left, "")).strip()
        sim = _sim(
            normalize_answer(correct_right),
            normalize_answer(student_right),
        )
        if sim >= PAIR_THRESHOLD:
            correct_count += 1
            feedback_lines.append(f"✓ {left} → {correct_right}")
        else:
            feedback_lines.append(
                f"✗ {left} → you answered '{student_right}', correct is '{correct_right}'"
            )

    # Proportional score from pair_correctness (80% of marks)
    pair_score = round((correct_count / total_pairs) * marks * 0.8) if total_pairs else 0

    # Consistency bonus (20% of marks) — only if all pairs correct
    consistency_bonus = round(marks * 0.2) if correct_count == total_pairs else 0
    total_score = min(marks, pair_score + consistency_bonus)

    is_correct = (correct_count == total_pairs)
    pct = round((correct_count / total_pairs) * 100) if total_pairs else 0

    feedback = (
        f"{correct_count}/{total_pairs} pairs correct ({pct}%).\n"
        + "\n".join(feedback_lines)
    )

    if is_correct:
        strengths = "All pairs correctly matched — excellent recall of associations."
        weaknesses = ""
        improvements = ""
    else:
        incorrect = [l for l in feedback_lines if l.startswith("✗")]
        strengths = f"{correct_count} pair(s) correct." if correct_count > 0 else ""
        weaknesses = f"{total_pairs - correct_count} pair(s) incorrect."
        improvements = (
            "Review: " + "; ".join(
                f"{l.split('→')[0].strip()[2:]} → {correct_pairs.get(l.split('→')[0].strip()[2:], '')}"
                for l in incorrect
            )[:200]
        )

    return {
        "score":        total_score,
        "is_correct":   is_correct,
        "feedback":     feedback,
        "strengths":    strengths,
        "weaknesses":   weaknesses,
        "improvements": improvements,
        "hint":         question.get("explanation", "Review all pairs from the document."),
        "pair_correctness": correct_count,
        "pair_total":       total_pairs,
    }


def _fail(marks: int, reason: str) -> dict:
    return {
        "score": 0, "is_correct": False,
        "feedback": reason, "strengths": "", "weaknesses": reason,
        "improvements": "Ensure all pairs are answered.", "hint": "",
        "pair_correctness": 0, "pair_total": 0,
    }
