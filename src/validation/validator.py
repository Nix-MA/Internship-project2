"""
ingestion/content_validator.py — Pre-generation content quality gate.

Enforces Rule 2 (minimum content threshold) and Rule 9 (ingestion status tracking).

validate_content(text):
    Checks that extracted text contains enough meaningful tokens before question generation.
    Returns (is_valid: bool, reason: str).

build_ingestion_report(file_results):
    Summarises per-file processing outcomes for logging and UI display.
"""

import re
from src.utils.logger import get_logger

# ── Thresholds ─────────────────────────────────────────────────────────────────

# Minimum number of meaningful words (alpha-heavy tokens) required
# before we allow question generation to start.
MIN_MEANINGFUL_WORDS = 15

# Minimum ratio of alphabetical characters in the whole text
MIN_ALPHA_RATIO = 0.35

# UI message shown when content is insufficient
INSUFFICIENT_CONTENT_MSG = (
    "This document does not contain enough meaningful content to generate questions. "
    "Please upload a document with readable text (PDF, DOCX, TXT, PPTX, etc.), "
    "or paste a YouTube link with captions."
)


# ── Validators ─────────────────────────────────────────────────────────────────

def _count_meaningful_words(text: str) -> int:
    """Count words that are mostly alphabetical (length >= 2, not purely numeric)."""
    tokens = text.split()
    return sum(
        1 for t in tokens
        if len(t) >= 2 and sum(c.isalpha() for c in t) / len(t) >= 0.5
    )


def validate_content(text: str) -> tuple[bool, str]:
    """
    Validate that extracted text is sufficient for question generation.

    Args:
        text: Combined extracted text from all uploaded files.

    Returns:
        (True, "ok") if content is sufficient.
        (False, reason_message) if content is too weak.
    """
    if not text or not text.strip():
        get_logger('ingestion').warning("Content validation FAILED: empty text.")
        return False, "No text could be extracted from the uploaded documents."

    meaningful_words = _count_meaningful_words(text)

    if meaningful_words < MIN_MEANINGFUL_WORDS:
        msg = (
            f"Content validation FAILED: only {meaningful_words} meaningful words "
            f"(threshold: {MIN_MEANINGFUL_WORDS})."
        )
        get_logger('ingestion').warning(msg)
        return False, INSUFFICIENT_CONTENT_MSG

    # Alpha-ratio check on the overall text
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_non_space = len(text.replace(" ", "").replace("\n", ""))
    if total_non_space > 0:
        ratio = alpha_chars / total_non_space
        if ratio < MIN_ALPHA_RATIO:
            msg = (
                f"Content validation FAILED: alpha ratio {ratio:.2f} is below "
                f"threshold {MIN_ALPHA_RATIO}. Text may be numeric/symbolic only."
            )
            get_logger('ingestion').warning(msg)
            return False, INSUFFICIENT_CONTENT_MSG

    get_logger('ingestion').info(
        f"Content validation PASSED: {meaningful_words} meaningful words "
        f"across {len(text)} chars."
    )
    return True, "ok"


# ── Ingestion Status Tracking ──────────────────────────────────────────────────

def build_ingestion_report(file_results: list[dict]) -> dict:
    """
    Build a structured ingestion report from per-file extraction results.

    Each entry in file_results should be:
        {
            "filename": str,
            "content": str,          # extracted content (may be empty)
            "metadata": dict,        # extra from extractor
            "status": "ok" | "skipped" | "error"  (optional override)
        }

    Returns:
        {
            "processed_files": int,
            "skipped_files": int,
            "reasons": [str, ...],
            "file_details": [{"filename": str, "status": str, "reason": str}, ...]
        }
    """
    processed = 0
    skipped = 0
    reasons: list[str] = []
    details: list[dict] = []

    for r in file_results:
        fname = r.get("filename", "unknown")
        content = r.get("content", "")
        meta = r.get("metadata", {})
        meta_status = meta.get("status", "")

        if meta_status in ("insufficient_content",) or not content.strip():
            reason = _skip_reason(fname, meta_status, content)
            skipped += 1
            reasons.append(f"{fname}: {reason}")
            details.append({"filename": fname, "status": "skipped", "reason": reason})
            get_logger('ingestion').info(f"File skipped — {fname}: {reason}")
        elif meta_status == "error":
            reason = meta.get("error", "extraction error")
            skipped += 1
            reasons.append(f"{fname}: {reason}")
            details.append({"filename": fname, "status": "error", "reason": reason})
            get_logger('ingestion').warning(f"File error — {fname}: {reason}")
        else:
            word_count = _count_meaningful_words(content)
            processed += 1
            details.append({
                "filename": fname,
                "status": "ok",
                "reason": f"{word_count} meaningful words extracted",
            })

    report = {
        "processed_files": processed,
        "skipped_files": skipped,
        "reasons": reasons,
        "file_details": details,
    }
    get_logger('ingestion').info(
        f"Ingestion report: {processed} processed, {skipped} skipped. "
        f"Reasons: {reasons}"
    )
    return report


def _skip_reason(filename: str, meta_status: str, content: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if not content.strip():
        if ext in ("mp3", "wav"):
            return "Audio file — no transcript available. Upload a text transcript to generate questions."
        if ext in ("mp4", "mov", "avi", "mkv"):
            return "Video file — no transcript available. Upload a text transcript or paste a YouTube link."
        if ext in ("png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff"):
            return "Image file — vision model unavailable. Install 'llama3.2-vision' or 'moondream' in Ollama for content extraction."
        if ext == "zip":
            return "Archive file — cannot extract semantic content from compressed archives directly."
        return "No text could be extracted."
    if meta_status == "insufficient_content":
        return "Insufficient meaningful content."
    return "Skipped."
