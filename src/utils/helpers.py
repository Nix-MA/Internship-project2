"""
utils/helpers.py — Shared utilities used across all modules.

Provides:
- parse_llm_json(): robust JSON extraction from LLM output with fence stripping
- retry_llm_call(): decorator/function for retry with correction prompt
- safe_int(): safe integer cast with default
- sanitize_score(): clamp score to [0, max_score]
"""

import json
import re
import time
from typing import Any, Callable, Optional


# ── JSON Parsing ───────────────────────────────────────────────────────────────

def parse_llm_json(raw: str, expected_type: type = dict) -> Optional[Any]:
    """
    Robustly extract a JSON object or array from LLM raw output.

    Strategies (in order):
    1. Strip ```json ... ``` or ``` ... ``` fences, parse each block
    2. Parse the full string directly
    3. Regex extract first {...} or [...] block

    Returns the parsed Python object, or None on failure.
    """
    if not raw:
        return None

    clean = raw.strip()

    # Strategy 1: strip markdown code fences
    if "```" in clean:
        parts = re.split(r"```(?:json)?", clean)
        for part in parts:
            part = part.strip().rstrip("`").strip()
            if not part:
                continue
            try:
                result = json.loads(part)
                if isinstance(result, expected_type):
                    return result
                # Also accept if a list was expected but single dict found
                if expected_type is list and isinstance(result, dict):
                    return [result]
            except json.JSONDecodeError:
                continue

    # Strategy 2: parse full output
    try:
        result = json.loads(clean)
        if isinstance(result, expected_type):
            return result
        if expected_type is list and isinstance(result, dict):
            return [result]
    except json.JSONDecodeError:
        pass

    # Strategy 3: extract first JSON block via regex
    if expected_type is list:
        pattern = r'\[\s*\{.*?\}\s*\]'
    else:
        pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}'

    match = re.search(pattern, clean, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, expected_type):
                return result
        except json.JSONDecodeError:
            pass

    return None


# ── Retry Logic ─────────────────────────────────────────────────────────────────

def retry_llm_call(
    fn: Callable,
    args: tuple = (),
    kwargs: dict = None,
    max_retries: int = 3,
    delay: float = 1.0,
    correction_fn: Optional[Callable] = None,
) -> Optional[Any]:
    """
    Call fn(*args, **kwargs) up to max_retries times.
    On failure, optionally call correction_fn(attempt) to get new kwargs.

    Returns result on success, None on all failures.
    """
    if kwargs is None:
        kwargs = {}

    for attempt in range(1, max_retries + 1):
        try:
            result = fn(*args, **kwargs)
            if result is not None:
                return result
        except Exception as e:
            from src.utils.logger import get_logger
            get_logger("llm.retry").warning(f"retry_llm_call attempt {attempt}/{max_retries} failed: {e}")

        if attempt < max_retries:
            if correction_fn:
                kwargs = correction_fn(attempt, kwargs)
            time.sleep(delay)

    return None


# ── Numeric helpers ────────────────────────────────────────────────────────────

def safe_int(value: Any, default: int = 0) -> int:
    """Safely cast value to int, return default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def sanitize_score(score: Any, max_score: int) -> int:
    """Clamp score to [0, max_score]."""
    return max(0, min(max_score, safe_int(score)))


# ── String Normalization ───────────────────────────────────────────────────────

def normalize_answer(text: str) -> str:
    """Lowercase, strip whitespace, remove punctuation for comparison."""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
