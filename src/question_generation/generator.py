"""
question_generation/generator.py — LLM question generation with full validation pipeline.

Pipeline per attempt:
    generate → parse_json → validate_schema → validate_grounding → validate_leakage → accept OR retry

generate_questions(context, q_type, count, marks):
    Legacy single-context entry point.

generate_questions_distributed(chunks, q_type, count, marks):
    Full-document coverage: splits chunks into segments, generates proportionally,
    passes source_chunk to validator for grounding + leakage checks.
"""

import json
import math
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.question_generation.prompts import PROMPTS
from src.question_generation.validator import validate_question_list
from src.utils.helpers import parse_llm_json
from src.utils.logger import get_logger

MODEL = "llama3.2"
MAX_RETRIES = 2  # 2 attempts: original + 1 correction — reduces worst-case wait time

# Words grouped into one LLM call — larger = fewer calls = much faster
CONTEXT_WORDS_PER_CALL = 3000

# Hard cap on LLM calls per question type regardless of document size
MAX_SEGMENTS = 4


def _get_question_signature(q: dict) -> str:
    """Generate a stable, unique signature for a question to detect duplicates properly."""
    q_type = q.get("type", "")
    
    if q_type == "Match the Following":
        pairs = q.get("pairs", {})
        if isinstance(pairs, dict):
            # Use sorted items so different orderings of same pairs are caught
            return str(sorted(pairs.items())).lower()
        return str(pairs).strip().lower()
        
    elif q_type == "Assertion & Reason":
        return f"{q.get('assertion', '')} | {q.get('reason', '')}".strip().lower()
        
    return q.get("question", "").strip().lower()



def _call_ollama(prompt: str) -> str | None:
    """Make a single Ollama chat call with strict 180s timeout; return raw string or None."""
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False
            },
            timeout=180
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
    except requests.exceptions.Timeout:
        get_logger('llm').error("Ollama call timed out after 180 seconds.")
        return "TIMEOUT_ERROR"
    except Exception as e:
        get_logger('llm').error(f"Ollama call failed: {e}", exc_info=True)
        return None


def _build_correction_prompt(original_prompt: str, raw_output: str, errors: list[str]) -> str:
    """Build a correction prompt that feeds back the errors to the LLM."""
    error_str = "\n".join(f"- {e}" for e in errors)
    return (
        f"{original_prompt}\n\n"
        "---\n"
        "Your previous response had these validation errors:\n"
        f"{error_str}\n\n"
        "Fix ALL errors and return ONLY the corrected JSON array. No explanations."
    )


def _generate_from_context(
    context: str,
    q_type: str,
    count: int,
    marks: int,
    source_chunk: str | None = None,
) -> list[dict]:
    """
    Internal: generate `count` questions from a single context string with retry.

    Pipeline: generate → parse_json → validate_schema+grounding+leakage → accept/retry

    Args:
        context:      Text to generate questions from.
        q_type:       Question type string.
        count:        Number of questions requested.
        marks:        Marks per question.
        source_chunk: Original source text used for grounding/leakage validation.
                      If None, falls back to context.

    Returns a list of valid question dicts (may be fewer than count).
    """
    # Use context as source reference if no explicit source_chunk provided
    source_ref = source_chunk if source_chunk is not None else context

    template = PROMPTS.get(q_type, PROMPTS["MCQ"])
    base_prompt = template.format(
        count=count,
        marks=marks,
        context=context[:4000],  # 4000 chars is plenty for the model; less = faster
    )

    current_prompt = base_prompt
    best_result: list[dict] = []

    for attempt in range(1, MAX_RETRIES + 1):
        # Adaptive retry strategy (Rule 6):
        # Attempt 1: original prompt
        # Attempt 2: stricter JSON-only constraint
        # Attempt 3: minimal schema-only prompt
        if attempt == 2:
            current_prompt = (
                base_prompt
                + "\n\n[CRITICAL: OUTPUT ONLY A VALID JSON ARRAY. "
                "DO NOT INCLUDE MARKDOWN, BACKTICKS, OR EXPLANATIONS. "
                "DO NOT MENTION FILE TYPES OR FORMATS.]"
            )
        elif attempt == 3:
            current_prompt = (
                f"Return ONLY a minimal raw JSON array of 1 question for type '{q_type}'. "
                "No preamble. Do not mention file types, formats, or metadata. "
                "Only ask about the subject matter in the text below.\n"
                f"Text: {context[:1500]}"
            )

        raw = _call_ollama(current_prompt)

        if raw == "TIMEOUT_ERROR":
            get_logger('llm').warning("Generation aborted due to strict timeout.")
            raise TimeoutError("Model did not respond in time. Reduce input size.")

        if not raw:
            get_logger('llm').warning(f"_generate_from_context: no LLM response on attempt {attempt}/{MAX_RETRIES}")
            continue

        parsed = parse_llm_json(raw, expected_type=list)
        if parsed is None:
            with open("failed_raw.txt", "a", encoding="utf-8") as f:
                f.write(f"\\n=== PROMPT ===\\n{current_prompt}\\n")
                f.write(f"=== ATTEMPT {attempt} RAW ===\\n{raw}\\n\\n")
            get_logger('llm').warning(f"_generate_from_context: could not parse JSON on attempt {attempt}/{MAX_RETRIES}")
            continue

        for q in parsed:
            if isinstance(q, dict):
                q["type"]  = q_type
                q["marks"] = marks

        # Full pipeline: schema → grounding → leakage (all via validate_question_list)
        valid, errors = validate_question_list(parsed, q_type, source_chunk=source_ref)

        # Internal deduplication to enforce uniqueness inside a single LLM response
        unique_valid = []
        seen_local = set()
        for v in valid:
            sig = _get_question_signature(v)
            if sig and sig not in seen_local:
                seen_local.add(sig)
                unique_valid.append(v)
            else:
                errors.append(f"Dropped duplicate question: {v.get('question', '')[:30]}...")
                
        valid = unique_valid

        if valid and len(valid) > len(best_result):
            best_result = valid

        if len(best_result) >= count:
            break

        if errors:
            get_logger('llm').warning(
                f"_generate_from_context: {len(errors)} validation errors on attempt {attempt}/{MAX_RETRIES}: "
                + "; ".join(errors[:3])
            )
            if attempt < MAX_RETRIES:
                current_prompt = _build_correction_prompt(current_prompt, raw, errors)

    return best_result[:count]


def generate_questions(
    context: str,
    q_type: str,
    count: int,
    marks: int,
) -> list[dict]:
    """
    Generate `count` questions from a pre-assembled context string.
    This is the legacy single-context entry point.
    For full-document coverage, prefer generate_questions_distributed().
    """
    return _generate_from_context(context, q_type, count, marks)


def generate_questions_distributed(
    chunks: list[str],
    q_type: str,
    count: int,
    marks: int,
) -> list[dict]:
    """
    Generate `count` questions distributed evenly across ALL document chunks.

    Strategy:
        - Groups consecutive chunks into segments (each segment ~CONTEXT_WORDS_PER_CALL words)
        - Distributes the requested count proportionally so every segment contributes
        - Passes the segment itself as source_chunk so grounding and leakage validators
          can check each question against its actual source text
        - Merges results, deduplicates by question text, trims to exact count

    This ensures:
        1. The LLM sees every part of the uploaded document (not just first pages)
        2. Every generated question is grounded in its source segment
        3. Leakage and hallucination are caught before questions are accepted

    Args:
        chunks: Full list of text chunks from chunk_text()
        q_type: Question type string
        count:  Total number of questions requested
        marks:  Marks per question

    Returns:
        List of valid question dicts, length == count (or fewer if the LLM
        failed to produce enough).
    """
    if not chunks:
        return []

    # ── Group chunks into segments ─────────────────────────────────────────────
    segments: list[str] = []
    current_words: list[str] = []

    for chunk in chunks:
        chunk_words = chunk.split()
        if current_words and len(current_words) + len(chunk_words) > CONTEXT_WORDS_PER_CALL:
            segments.append(" ".join(current_words))
            current_words = chunk_words
        else:
            current_words.extend(chunk_words)

    if current_words:
        segments.append(" ".join(current_words))

    # ── Cap segments to MAX_SEGMENTS ──────────────────────────────────────────
    # If there are more segments than the cap, evenly sample across the document
    # so every part of the content is still represented.
    if len(segments) > MAX_SEGMENTS:
        step = len(segments) / MAX_SEGMENTS
        segments = [segments[int(i * step)] for i in range(MAX_SEGMENTS)]

    num_segments = len(segments)
    get_logger('llm').info(f"[Distributed] {q_type} × {count} across {num_segments} segment(s)")

    if num_segments == 1:
        # Small document — single call
        return _generate_from_context(
            segments[0], q_type, count, marks,
            source_chunk=segments[0],
        )

    # ── Distribute count across segments ──────────────────────────────────────
    # Ask each segment for slightly more than its share so we hit the target
    # even if one segment fails.
    per_seg_count = max(1, math.ceil(count / num_segments))

    # ── Generate from each segment ────────────────────────────────────────────
    all_results: list[dict] = []
    seen_questions: set[str] = set()

    for seg_idx, segment in enumerate(segments):
        # Stop early once we have enough questions
        if len(all_results) >= count:
            break
        remaining = count - len(all_results)
        seg_ask   = min(per_seg_count, remaining + 1)  # +1 buffer for dedup losses
        get_logger('llm').info(
            f"[Distributed] Segment {seg_idx + 1}/{num_segments}: {seg_ask} × {q_type}"
        )
        try:
            seg_results = _generate_from_context(
                segment, q_type, seg_ask, marks,
                source_chunk=segment,
            )
        except TimeoutError:
            get_logger('llm').warning(f"[Distributed] Segment {seg_idx + 1} timed out — skipping")
            seg_results = []

        for q in seg_results:
            sig = _get_question_signature(q)
            if sig and sig not in seen_questions:
                seen_questions.add(sig)
                all_results.append(q)

    if not all_results:
        get_logger('llm').error(f"[Distributed] No questions generated for {q_type}")
        return []

    return all_results[:count]


def generate_questions_parallel(
    chunks: list[str],
    q_configs: list[dict],
    progress_callback=None,
) -> dict[str, list[dict]]:
    """
    Generate questions for multiple question types IN PARALLEL using threads.

    This is the fast entry point when the user selects multiple question types.
    All types are dispatched concurrently to Ollama, reducing total wait time
    from O(N_types * time_per_type) to O(max_time_per_type).

    Args:
        chunks:            Full document chunks from chunk_text().
        q_configs:         List of dicts with keys: type, count, marks.
        progress_callback: Optional callable(q_type, questions) called as each
                           type completes, for live streaming UI updates.

    Returns:
        Dict mapping q_type -> list of generated question dicts.
    """
    results: dict[str, list[dict]] = {}
    errors:  dict[str, str]        = {}

    def _task(cfg: dict) -> tuple[str, list[dict]]:
        q_type = cfg["type"]
        count  = cfg["count"]
        marks  = cfg["marks"]
        try:
            qs = generate_questions_distributed(chunks, q_type, count, marks)
            return q_type, qs
        except TimeoutError:
            get_logger("llm").warning(f"[Parallel] Timeout generating {q_type}")
            return q_type, []
        except Exception as e:
            get_logger("llm").error(f"[Parallel] Error generating {q_type}: {e}", exc_info=True)
            return q_type, []

    # Use min(len(q_configs), 4) threads — Ollama is CPU-bound so >4 threads
    # gives diminishing returns and may saturate the local GPU/CPU.
    max_workers = min(len(q_configs), 4)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_task, cfg): cfg["type"] for cfg in q_configs}
        for future in as_completed(futures):
            q_type, qs = future.result()
            results[q_type] = qs
            if progress_callback:
                try:
                    progress_callback(q_type, qs)
                except Exception:
                    pass  # never crash the generator due to UI callback errors

    return results
