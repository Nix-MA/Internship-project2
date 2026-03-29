"""
ingestion/chunker.py — Token-aware text chunking with deduplication and noise filtering.

chunk_text():     Splits text into overlapping word-based chunks.
deduplicate_chunks(): Removes near-duplicate chunks via SHA-256 hashing.
"""

import hashlib
import re


# ── Noise filtering ────────────────────────────────────────────────────────────

_NOISE_PATTERNS = [
    re.compile(r"^\s*page\s+\d+\s*$", re.IGNORECASE),          # "Page 3"
    re.compile(r"^\s*\d+\s*$"),                                  # lone numbers
    re.compile(r"^\s*[-=_*]{3,}\s*$"),                           # divider lines
    re.compile(r"^\s*copyright.*$", re.IGNORECASE),
    re.compile(r"^\s*all rights reserved.*$", re.IGNORECASE),
    re.compile(r"^\s*\[sheet:\s*.*\]\s*$", re.IGNORECASE),      # xlsx sheet labels
    re.compile(r"^\s*\[slide\s+\d+\]\s*$", re.IGNORECASE),     # pptx slide labels
]

# Patterns that indicate a chunk is an error/metadata artefact from extraction.
# These must be rejected even if they have > MIN_WORDS tokens.
_CONTENT_REJECTION_PATTERNS = [
    re.compile(r"extraction (error|failed)", re.IGNORECASE),
    re.compile(r"\[file skipped", re.IGNORECASE),
    re.compile(r"\[archive (rejected|validated|inspection)", re.IGNORECASE),
    re.compile(r"unsupported (binary|file)", re.IGNORECASE),
    re.compile(r"could not extract", re.IGNORECASE),
    re.compile(r"note:?\s+install\s+llama", re.IGNORECASE),    # image fallback note
    re.compile(r"for richer question generation", re.IGNORECASE),
    re.compile(r"--- from:.*---", re.IGNORECASE),               # file separator headers
    re.compile(r"\[sheet:\s*", re.IGNORECASE),                  # xlsx sheet labels inline
    re.compile(r"vision feature requires", re.IGNORECASE),       # vision model text
    re.compile(r"returning empty content", re.IGNORECASE),
]

MIN_WORDS = 15          # chunks shorter than this are discarded
MIN_ALPHA_RATIO = 0.4   # at least 40% of chars must be alphabetical (screens symbol dumps)


def _is_noise(line: str) -> bool:
    """Return True if a line is purely noise/formatting."""
    return any(p.match(line.strip()) for p in _NOISE_PATTERNS)


def _filter_noise(text: str) -> str:
    """Remove noise lines from text."""
    lines = text.splitlines()
    clean = [ln for ln in lines if not _is_noise(ln)]
    return "\n".join(clean)


# ── Chunking ───────────────────────────────────────────────────────────────────

def chunk_text(
    text: str,
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[str]:
    """
    Split text into overlapping word-token chunks.
    Enforces a strict global limit equivalent to ~50,000 tokens (37,500 words).

    Args:
        text:       Input text (may be from multiple documents, concatenated).
        chunk_size: Approximate target chunk size in words.
        overlap:    Number of words to overlap between consecutive chunks.

    Returns:
        List of non-empty, deduplicated chunk strings.
    """
    from src.utils.logger import get_logger
    
    # 1. Noise filter
    text = _filter_noise(text)

    # 2. Word tokenize
    words = text.split()
    if not words:
        return []
        
    # Cap total words to roughly 50,000 tokens (* 0.75 = 37,500 words)
    MAX_WORDS = 37500
    if len(words) > MAX_WORDS:
        get_logger('ingestion').warning(f"File text exceeded 50,000 tokens. Truncating from {len(words)} to {MAX_WORDS} words.")
        words = words[:MAX_WORDS]

    # 3. Sliding window chunking with overlap
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if is_valid_chunk(chunk):
            chunks.append(chunk)
        start += chunk_size - overlap

    # 4. Deduplication
    return deduplicate_chunks(chunks)


# ── Chunk quality validation ────────────────────────────────────────────────────

def is_valid_chunk(chunk: str) -> bool:
    """
    Return True only if a chunk contains meaningful, usable semantic content.

    Rejects:
    - Chunks below MIN_WORDS word threshold
    - Chunks that are mostly symbols/numbers (low alpha ratio)
    - Chunks that are extraction error/metadata artefacts
    """
    words = chunk.split()
    if len(words) < MIN_WORDS:
        return False

    # Alpha-character ratio check: screens out hex dumps, CSV with only numbers, etc.
    alpha_chars = sum(1 for c in chunk if c.isalpha())
    total_chars = len(chunk.replace(" ", ""))
    if total_chars > 0 and (alpha_chars / total_chars) < MIN_ALPHA_RATIO:
        return False

    # Reject chunks that are extraction error or metadata artefacts
    for pattern in _CONTENT_REJECTION_PATTERNS:
        if pattern.search(chunk):
            return False

    return True


# ── Deduplication ──────────────────────────────────────────────────────────────

def _chunk_fingerprint(chunk: str) -> str:
    """SHA-256 fingerprint of a normalised chunk."""
    normalised = re.sub(r"\s+", " ", chunk.strip().lower())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def deduplicate_chunks(chunks: list[str]) -> list[str]:
    """
    Remove exact and near-duplicate chunks using content fingerprinting.
    Preserves original order, keeps first occurrence.
    """
    seen: set[str] = set()
    unique: list[str] = []
    for chunk in chunks:
        fp = _chunk_fingerprint(chunk)
        if fp not in seen:
            seen.add(fp)
            unique.append(chunk)
    return unique


# ── Context assembly ───────────────────────────────────────────────────────────

def build_context(chunks: list[str], max_chunks: int = 8) -> str:
    """
    Join the first max_chunks chunks into a single context string for LLM prompts.
    Keeps the total context under approximately 5,600 words.
    """
    selected = chunks[:max_chunks]
    return "\n\n".join(selected)
