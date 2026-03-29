"""
grading/semi_structured.py — Fuzzy graders for One Word Answer and Fill in the Blanks.

Uses rapidfuzz for similarity scoring when exact match fails.
Falls back to substring containment if rapidfuzz is unavailable.
"""

from src.utils.helpers import normalize_answer

try:
    from rapidfuzz import fuzz as _fuzz
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False
    from src.utils.logger import get_logger
    get_logger("grading").warning("rapidfuzz not installed — falling back to substring matching. Run: pip install rapidfuzz")


def _similarity(a: str, b: str) -> float:
    """Return similarity ratio [0–100] between two strings."""
    if _HAS_RAPIDFUZZ:
        return _fuzz.ratio(a, b)
    # Fallback: substring containment → 100 if either contains the other
    if a in b or b in a:
        return 90.0
    return 0.0


# ── One Word Answer ────────────────────────────────────────────────────────────

ONE_WORD_EXACT_THRESHOLD  = 100  # perfect match
ONE_WORD_FUZZY_THRESHOLD  = 82   # accept near-match (e.g. spelling variance)


def grade_one_word(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade One Word Answer with exact + fuzzy match.

    Scoring:
    - Exact match (case-insensitive, normalised): full marks
    - Fuzzy similarity >= 82%: full marks (minor spelling)
    - Below threshold: 0 marks
    """
    correct = normalize_answer(question.get("correct_answer", ""))
    student = normalize_answer(student_answer)

    sim = _similarity(correct, student)

    if sim >= ONE_WORD_EXACT_THRESHOLD:
        return _make_ow(marks, marks, True,
                        f"Correct! '{student_answer}' matches the expected answer.",
                        "Accurate single-word recall.", "")

    if sim >= ONE_WORD_FUZZY_THRESHOLD:
        return _make_ow(marks, marks, True,
                        f"Accepted. '{student_answer}' is close enough to '{question.get('correct_answer', '')}'.",
                        f"Good recall (similarity: {sim:.0f}%).", "")

    return _make_ow(0, marks, False,
                    f"Incorrect. Expected '{question.get('correct_answer', '')}', "
                    f"you wrote '{student_answer}' (similarity: {sim:.0f}%).",
                    "",
                    f"Review: {question.get('explanation', 'Study the related concept.')}")


def _make_ow(score, max_score, is_correct, feedback, strengths, improvements):
    return {
        "score": score, "is_correct": is_correct,
        "feedback": feedback, "strengths": strengths,
        "weaknesses": "" if is_correct else "Incorrect term used.",
        "improvements": improvements,
        "hint": "",
    }


# ── Fill in the Blanks ─────────────────────────────────────────────────────────

FILL_EXACT_THRESHOLD = 100
FILL_FUZZY_THRESHOLD = 78    # slightly more lenient for phrases


def grade_fill_blank(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade Fill in the Blanks.

    Supports single-blank questions.
    Scoring:
    - Exact match (normalised): full marks
    - Fuzzy >= 78%: marks * 0.7  (partial credit)
    - Below: 0
    """
    correct = normalize_answer(question.get("correct_answer", ""))
    student = normalize_answer(student_answer)

    sim = _similarity(correct, student)
    model_ans = question.get("correct_answer", correct)

    if sim >= FILL_EXACT_THRESHOLD:
        score = marks
        is_correct = True
        feedback = f"Correct! The answer is '{model_ans}'."
        strengths = "Exact match — precise recall demonstrated."
        weaknesses = ""
        improvements = ""

    elif sim >= FILL_FUZZY_THRESHOLD:
        score = max(1, round(marks * 0.7))
        is_correct = False
        feedback = (
            f"Partially correct. You wrote '{student_answer}'; expected '{model_ans}'. "
            f"Similarity: {sim:.0f}%."
        )
        strengths = "Approximately correct — close to the expected answer."
        weaknesses = "Minor inaccuracy in phrasing or spelling."
        improvements = f"The precise answer is: '{model_ans}'."

    else:
        score = 0
        is_correct = False
        feedback = f"Incorrect. Expected '{model_ans}', you wrote '{student_answer}'."
        strengths = ""
        weaknesses = "Incorrect answer — did not match the expected term."
        improvements = question.get("explanation", f"Study the concept related to: '{model_ans}'.")

    return {
        "score": score, "is_correct": is_correct,
        "feedback": feedback, "strengths": strengths,
        "weaknesses": weaknesses, "improvements": improvements,
        "hint": question.get("explanation", ""),
    }
