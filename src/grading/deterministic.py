"""
grading/deterministic.py — Exact-match graders for MCQ, True/False, Assertion & Reason.

All return a rubric-compatible raw result dict:
    {score, is_correct, feedback, hint, strengths, weaknesses}

The rubric engine wraps this into the canonical format.
"""

from src.utils.helpers import normalize_answer


def grade_mcq(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade MCQ: exact letter match (A/B/C/D).
    Accepts "A", "A. Some text", or "a".
    """
    correct = question.get("correct_answer", "").strip().upper()
    student = student_answer.strip().upper()

    # Extract first letter in case full option text is passed
    student_letter = student[0] if student else ""
    is_correct = (student_letter == correct)

    if is_correct:
        feedback = f"Correct! The answer is {correct}."
        strengths = "Accurate selection — correct option identified."
        weaknesses = ""
    else:
        feedback = f"Incorrect. You chose '{student_letter}', but the correct answer is '{correct}'."
        strengths = ""
        weaknesses = f"Selected incorrect option '{student_letter}' instead of '{correct}'."

    return {
        "score":      marks if is_correct else 0,
        "is_correct": is_correct,
        "feedback":   feedback,
        "strengths":  strengths,
        "weaknesses": weaknesses,
        "improvements": "" if is_correct else f"Review the explanation: {question.get('explanation', '')}",
        "hint":       question.get("explanation", "Review the relevant section."),
    }


def grade_true_false(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade True/False: exact match ignoring case.
    """
    correct = question.get("correct_answer", "").strip().lower()
    student = student_answer.strip().lower()
    is_correct = (student == correct)

    if is_correct:
        feedback = f"Correct! The statement is {correct.title()}."
        strengths = "Correctly identified the truth value of the statement."
        weaknesses = ""
    else:
        feedback = f"Incorrect. The statement is {correct.title()}, not {student.title()}."
        strengths = ""
        weaknesses = f"Misjudged the statement as {student.title()} when it is {correct.title()}."

    return {
        "score":       marks if is_correct else 0,
        "is_correct":  is_correct,
        "feedback":    feedback,
        "strengths":   strengths,
        "weaknesses":  weaknesses,
        "improvements": "" if is_correct else f"Study: {question.get('explanation', '')}",
        "hint":        question.get("explanation", ""),
    }


def grade_assertion_reason(question: dict, student_answer: str, marks: int) -> dict:
    """
    Grade Assertion & Reason: treated identically to MCQ — single letter (A/B/C/D).
    """
    return grade_mcq(question, student_answer, marks)
