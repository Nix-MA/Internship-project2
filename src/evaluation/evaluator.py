"""
evaluation/evaluator.py — Master evaluation router.

evaluate_answer():
    Routes to the correct grader based on question type.
    Returns a canonical rubric result (via rubric engine).

evaluate_all():
    Batch evaluates all questions in a session.
"""

from src.grading.deterministic   import grade_mcq, grade_true_false, grade_assertion_reason
from src.grading.semi_structured import grade_one_word, grade_fill_blank
from src.grading.structured      import grade_match
from src.grading.llm_grader      import grade_with_llm
from src.rubric_engine.engine    import grade_with_rubric
from src.rubric_engine.rubrics   import get_rubric
from src.utils.logger            import get_logger


_NO_ANSWER_SENTINEL = "[No answer provided]"


def evaluate_answer(question: dict, student_answer: str, context: str = "") -> dict:
    """
    Evaluate a single student answer.

    Args:
        question:       Full question dict (must have "type" and "marks").
        student_answer: The student's raw answer string.
        context:        Document context text (used by LLM graders).

    Returns:
        Canonical rubric result dict.
    """
    q_type = question.get("type", "MCQ")
    marks  = question.get("marks", 1)

    # ── Handle missing / empty answers ────────────────────────────────────────
    if (
        not student_answer
        or str(student_answer).strip() in ("", _NO_ANSWER_SENTINEL, "-- select --")
    ):
        rubric = get_rubric(q_type)
        empty_raw = {
            "score": 0, "is_correct": False,
            "feedback": "No answer was provided.",
            "strengths": "",
            "weaknesses": "Question was left unanswered.",
            "improvements": "Attempt every question — partial credit is available.",
            "hint": "Make sure to answer every question.",
        }
        return grade_with_rubric(question, empty_raw, rubric)

    # ── Route to specific grader ──────────────────────────────────────────────
    try:
        if q_type == "MCQ":
            raw = grade_mcq(question, student_answer, marks)

        elif q_type == "True / False":
            raw = grade_true_false(question, student_answer, marks)

        elif q_type == "Assertion & Reason":
            raw = grade_assertion_reason(question, student_answer, marks)

        elif q_type == "One Word Answer":
            raw = grade_one_word(question, student_answer, marks)

        elif q_type == "Fill in the Blanks":
            raw = grade_fill_blank(question, student_answer, marks)

        elif q_type == "Match the Following":
            raw = grade_match(question, student_answer, marks)

        elif q_type in ("Short Answer", "Long Answer"):
            raw = grade_with_llm(question, student_answer, marks, context)

        else:
            # Unknown type → LLM fallback
            raw = grade_with_llm(question, student_answer, marks, context)

    except Exception as e:
        get_logger('error').error(f"Evaluation error for {q_type}", exc_info=True)
        rubric = get_rubric(q_type)
        raw = {
            "score": 0, "max_score": marks, "is_correct": False,
            "feedback": "Evaluation failed.",
            "strengths": "", "weaknesses": "Could not evaluate.",
            "improvements": "Contact support.", "hint": "",
            "status": "error"
        }
        return grade_with_rubric(question, raw, rubric)

    # ── Wrap raw result in rubric engine ──────────────────────────────────────
    rubric = get_rubric(q_type)
    return grade_with_rubric(question, raw, rubric)


def evaluate_all(questions: list[dict], answers: dict, context: str = "") -> list[dict]:
    """
    Evaluate all questions in a session.

    Args:
        questions: List of question dicts (indexed 0..n-1).
        answers:   Dict mapping question index → student answer string.
        context:   Full document context string.

    Returns:
        List of canonical rubric result dicts, in same order as questions.
    """
    results = []
    for i, q in enumerate(questions):
        student_ans = answers.get(i, _NO_ANSWER_SENTINEL)
        ev = evaluate_answer(q, student_ans, context)
        results.append(ev)
    return results


# ── Legacy compatibility alias (used by old app.py import) ────────────────────
def evaluate_all_answers(question: dict, student_answer: str, context: str = "") -> dict:
    """Backward-compatible wrapper around evaluate_answer."""
    return evaluate_answer(question, student_answer, context)
