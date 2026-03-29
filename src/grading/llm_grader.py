"""
grading/llm_grader.py — LLM-based rubric grader for Short Answer and Long Answer.

grade_with_llm():
    Sends a structured rubric prompt to the LLM.
    Expects strict JSON with per-criterion scores.
    Retries up to 3 times with correction prompts.
    Falls back to proportional score estimate on persistent failure.
"""

import requests
from src.utils.helpers import parse_llm_json, sanitize_score
from src.rubric_engine.rubrics import get_rubric
from src.utils.logger import get_logger

MODEL = "llama3.2"
MAX_RETRIES = 3


def grade_with_llm(question: dict, student_answer: str, marks: int, context: str = "") -> dict:
    """
    Grade an open-ended answer using the LLM with an explicit rubric prompt.

    Returns:
        Raw result dict with "criteria_scores" for rubric engine to process.
    """
    rubric   = get_rubric(question.get("type", "Short Answer"))
    criteria = rubric["criteria"]

    criteria_desc = "\n".join(
        f'  - {c["name"]} (weight {int(c["weight"]*100)}%): '
        + _criterion_desc(c["name"])
        for c in criteria
    )

    # Max per criterion (rounded)
    crit_maxes = {
        c["name"]: max(1, round(marks * c["weight"]))
        for c in criteria
    }
    crit_max_str = ", ".join(f'"{k}": 0–{v}' for k, v in crit_maxes.items())

    grading_points = question.get("grading_points", [])
    points_str = ""
    if grading_points:
        points_str = "\nKey grading points (must cover):\n" + "\n".join(f"  - {p}" for p in grading_points)

    base_prompt = f"""\
You are an expert teacher grading a student's answer using a structured rubric.

QUESTION TYPE: {question.get("type", "Short Answer")}
QUESTION: {question["question"]}
MODEL ANSWER: {question.get("correct_answer", "N/A")}
{points_str}
MAXIMUM TOTAL MARKS: {marks}

RUBRIC CRITERIA:
{criteria_desc}

STUDENT'S ANSWER:
{student_answer}

DOCUMENT CONTEXT (for grounding):
{context[:1500]}

GRADING INSTRUCTIONS:
- Score EACH criterion independently based on the rubric definition
- Do NOT let one dimension inflate another
- Be strict but fair; award partial credit where merited
- total_score must equal the SUM of all criteria_scores

Return ONLY this exact JSON (no extra text, no markdown fences):
{{
  "criteria_scores": {{
    {crit_max_str.replace('0–', '"0 to ')}
  }},
  "total_score": <integer 0–{marks}>,
  "max_score": {marks},
  "feedback": "<2–3 sentences on what was right and wrong>",
  "strengths": "<one sentence on what was done well>",
  "weaknesses": "<one sentence on the key gap>",
  "improvements": "<one concrete action to improve>"
}}

Criteria score ranges: {crit_max_str}
"""

    # Clean prompt (no f-string confusion from above)
    prompt = base_prompt

    for attempt in range(1, MAX_RETRIES + 1):
        if attempt == 2:
            prompt = base_prompt + "\n\n[CRITICAL: OUTPUT ONLY VALID JSON. DO NOT EXPLAIN. STRICT SCHEMA.]"
        elif attempt == 3:
            prompt = base_prompt + "\n\n[FINAL ATTEMPT: JUST RETURN THE RAW JSON MAP OF CRITERIA SCORES.]"

        raw = _call_ollama(prompt)
        
        if raw == "TIMEOUT_ERROR":
            get_logger('llm').warning("Grading aborted due to strict timeout.")
            raise TimeoutError("Model did not respond in time.")
            
        if not raw:
            get_logger('llm').warning(f"grade_with_llm: no response on attempt {attempt}")
            continue

        result = parse_llm_json(raw, expected_type=dict)
        if result and "criteria_scores" in result:
            return _sanitize_llm_result(result, marks, criteria)
            
        get_logger('llm').warning(f"grade_with_llm: invalid JSON or missing 'criteria_scores' on attempt {attempt}")

    # All retries failed — fallback
    get_logger('llm').error(f"LLM grading failed after {MAX_RETRIES} attempts for: {question.get('question', '')[:60]}")
    return _fallback_result(marks, criteria)


def _call_ollama(prompt: str) -> str | None:
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=45
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.Timeout:
        get_logger('llm').error("Ollama grading timed out after 45 seconds.")
        return "TIMEOUT_ERROR"
    except Exception as e:
        get_logger('llm').error(f"Ollama grading call failed: {e}", exc_info=True)
        return None


def _sanitize_llm_result(result: dict, marks: int, criteria: list) -> dict:
    """Clamp all criterion scores and recalculate total."""
    crit_scores_raw = result.get("criteria_scores", {})
    criteria_scores = {}
    for c in criteria:
        name    = c["name"]
        c_max   = max(1, round(marks * c["weight"]))
        raw_val = crit_scores_raw.get(name, 0)
        criteria_scores[name] = sanitize_score(raw_val, c_max)

    total = sanitize_score(
        result.get("total_score", sum(criteria_scores.values())),
        marks,
    )

    return {
        "criteria_scores": criteria_scores,
        "score":           total,
        "is_correct":      total == marks,
        "feedback":        str(result.get("feedback", "No feedback provided.")),
        "strengths":       str(result.get("strengths", "")),
        "weaknesses":      str(result.get("weaknesses", "")),
        "improvements":    str(result.get("improvements", "")),
        "hint":            str(result.get("improvements", "Review the model answer.")),
    }


def _fallback_result(marks: int, criteria: list) -> dict:
    """Return a safe zero-score fallback when LLM grading fails completely."""
    return {
        "criteria_scores": {c["name"]: 0 for c in criteria},
        "score":           0,
        "is_correct":      False,
        "feedback":        "Automatic evaluation could not be completed. Please review manually.",
        "strengths":       "",
        "weaknesses":      "Could not evaluate — automatic grading failed.",
        "improvements":    "Re-submit or ask your instructor to review.",
        "hint":            "Ensure Ollama is running and the model is available.",
        "status":          "error",
    }


def _criterion_desc(name: str) -> str:
    """Human-readable description for each rubric criterion."""
    descs = {
        "accuracy":           "factual correctness compared to the model answer",
        "completeness":       "all key points and grading criteria covered",
        "conceptual_clarity": "demonstrates genuine understanding, not just recall",
        "expression":         "clear sentence structure and appropriate terminology",
        "tolerance":          "minor variations acceptable",
        "pair_correctness":   "number of correctly matched pairs",
        "consistency":        "logical consistency across all matches",
    }
    return descs.get(name, "assessed based on answer quality")
