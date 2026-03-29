"""
question_generation/validator.py — JSON schema validation + content-grounding validation.

validate_question(q, q_type, source_chunk=None):
    - Validates schema (required fields, value ranges)
    - Validates content-grounding (question references real content)
    - Detects file-type leakage (context-aware, not a static blocklist)

validate_question_list(questions, q_type, source_chunk=None):
    - Validates a list of questions, returns (valid, errors)
"""

import re
from typing import Tuple, Optional

# Required fields per question type
REQUIRED_FIELDS: dict[str, list[str]] = {
    "MCQ":                 ["question", "options", "correct_answer"],
    "True / False":        ["question", "correct_answer"],
    "Fill in the Blanks":  ["question", "correct_answer"],
    "Short Answer":        ["question", "correct_answer"],
    "Long Answer":         ["question", "correct_answer"],
    "Match the Following": ["question", "pairs"],
    "Assertion & Reason":  ["question", "assertion", "reason", "correct_answer"],
    "One Word Answer":     ["question", "correct_answer"],
}

VALID_LETTERS = {"A", "B", "C", "D"}

# ── Leakage detection ──────────────────────────────────────────────────────────

# Terms that indicate a question is about a file format or medium rather than content.
# These are matched case-insensitively against the question text.
_FILETYPE_TERMS = re.compile(
    r"\b(pdf|docx|csv|xlsx|pptx|json|xml|txt|mp3|wav|mp4|mov|avi|zip|format|"
    r"file type|image|photo|picture|worksheet|audio file|video file|audio recording|"
    r"video recording|upload(?:ed)?|file extension|file format|document type)\b",
    re.IGNORECASE,
)


def _is_leakage_question(question_text: str, source_chunk: Optional[str]) -> bool:
    """
    Context-aware leakage check (Rule 3).

    Returns True (leakage detected) only when a file-type term appears in the
    question AND that same term does NOT appear in the source chunk.

    This allows legitimate questions like "What does CSV contain?" when the
    source document is literally about CSV format conventions, while blocking
    hallucinated "What is a PDF file?" questions.
    """
    matches = _FILETYPE_TERMS.findall(question_text)
    if not matches:
        return False  # no filetype terms → definitely not leakage

    if source_chunk is None:
        # No source available for comparison — reject conservatively
        return True

    source_lower = source_chunk.lower()
    for term in matches:
        term_lower = term.lower().strip()
        if term_lower not in source_lower:
            # The term is in the question but NOT in the source — leakage
            return True

    return False


# ── Grounding check ────────────────────────────────────────────────────────────

# Stopwords to exclude from grounding key-term extraction
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "and", "or", "but", "not", "no",
    "it", "its", "this", "that", "with", "by", "from", "which", "what",
    "who", "how", "when", "where", "why", "do", "does", "did", "have",
    "has", "had", "will", "would", "can", "could", "should", "may", "might",
    "each", "every", "all", "some", "any", "both", "either", "than",
    "as", "if", "then", "so", "about", "into", "over", "after", "before",
})

# Minimum number of key terms that must overlap between question and source
_MIN_GROUNDING_OVERLAP = 1


def _extract_key_terms(text: str, min_length: int = 4) -> set[str]:
    """Extract meaningful alphabetic tokens from text as lowercase."""
    tokens = re.findall(r"\b[a-zA-Z]{%d,}\b" % min_length, text)
    return {t.lower() for t in tokens if t.lower() not in _STOPWORDS}


def _is_grounded(question_text: str, source_chunk: Optional[str]) -> bool:
    """
    Grounding check (Rule 4): verify the question references terms found
    in the source chunk.

    Returns True if the question is grounded, False if it appears hallucinated.
    Skips check when no source_chunk is provided (to avoid blocking single-chunk
    legacy calls that don't pass a source).
    """
    if source_chunk is None or not source_chunk.strip():
        return True  # can't check without source — give benefit of doubt

    q_terms = _extract_key_terms(question_text)
    if not q_terms:
        return True  # too short to extract terms — defer to schema check

    src_terms = _extract_key_terms(source_chunk)
    overlap = q_terms & src_terms

    return len(overlap) >= _MIN_GROUNDING_OVERLAP


# ── Schema validation ──────────────────────────────────────────────────────────

def validate_question(
    q: dict,
    q_type: str,
    source_chunk: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validate a single question dict against schema + grounding + leakage rules.

    Args:
        q:            Question dict from LLM.
        q_type:       Expected question type string.
        source_chunk: The source text chunk the question was generated from.
                      Used for grounding and leakage checks.

    Returns:
        (True, "") on success.
        (False, "error description") on any failure.
    """
    if not isinstance(q, dict):
        return False, "Question is not a dict."

    required = REQUIRED_FIELDS.get(q_type, ["question"])
    for field in required:
        if field not in q or q[field] is None:
            return False, f"Missing required field: '{field}'."

    # ── Type-specific deep checks ──────────────────────────────────────────────
    if q_type == "MCQ":
        opts = q.get("options", {})
        if not isinstance(opts, dict) or len(opts) < 4:
            return False, "MCQ must have exactly 4 options {A, B, C, D}."
        if q.get("correct_answer", "").strip().upper() not in VALID_LETTERS:
            return False, "MCQ correct_answer must be A, B, C, or D."

    elif q_type == "True / False":
        ans = str(q.get("correct_answer", "")).strip().lower()
        if ans not in ("true", "false"):
            return False, "True/False correct_answer must be 'True' or 'False'."

    elif q_type == "Fill in the Blanks":
        if "_____" not in str(q.get("question", "")):
            return False, "Fill in the Blanks question must contain '_____'."

    elif q_type == "Match the Following":
        pairs = q.get("pairs", {})
        if not isinstance(pairs, dict) or len(pairs) < 2:
            return False, "Match the Following must have at least 2 pairs."

    elif q_type == "Assertion & Reason":
        if not q.get("assertion") or not q.get("reason"):
            return False, "Assertion & Reason must have non-empty 'assertion' and 'reason'."
        if q.get("correct_answer", "").strip().upper() not in VALID_LETTERS:
            return False, "Assertion & Reason correct_answer must be A, B, C, or D."

    # ── Minimum question text length ───────────────────────────────────────────
    question_text = str(q.get("question", "")).strip()
    if len(question_text) < 10:
        return False, "Question text is too short."

    # ── File-type leakage check (Rule 3 — context-aware) ──────────────────────
    if _is_leakage_question(question_text, source_chunk):
        return False, (
            f"Leakage detected: question references file-type terms not present "
            f"in source content. Question: '{question_text[:80]}'"
        )

    # ── Grounding check (Rule 4) ───────────────────────────────────────────────
    if not _is_grounded(question_text, source_chunk):
        return False, (
            f"Grounding check failed: question terms have no overlap with source chunk. "
            f"Question: '{question_text[:80]}'"
        )

    return True, ""


def validate_question_list(
    questions: list,
    q_type: str,
    source_chunk: Optional[str] = None,
) -> Tuple[list, list]:
    """
    Validate a list of questions.

    Returns:
        (valid_questions, error_messages)
    """
    valid = []
    errors = []
    for i, q in enumerate(questions):
        ok, msg = validate_question(q, q_type, source_chunk=source_chunk)
        if ok:
            valid.append(q)
        else:
            errors.append(f"Q{i+1}: {msg}")
    return valid, errors
