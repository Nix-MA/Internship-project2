"""
tests/test_content_grounding.py — Content-grounding and leakage validation tests.

Tests per the mandatory matrix (Rule 10) covering:
  A. Adversarial input ("This is a PDF file. Explain what a PDF is.")
  B. Weak placeholder case (image/audio without content)
  C. Mixed input (valid file + empty/corrupt file)
  D. Metadata-only input

Also covers:
  - validate_question() leakage detection (context-aware)
  - validate_question() grounding check
  - is_valid_chunk() quality filter
  - validate_content() minimum threshold
  - build_ingestion_report() status tracking
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from question_generation.validator import (
    validate_question,
    validate_question_list,
    _is_leakage_question,
    _is_grounded,
)
from ingestion.chunker import is_valid_chunk, chunk_text
from ingestion.content_validator import (
    validate_content,
    build_ingestion_report,
    INSUFFICIENT_CONTENT_MSG,
    MIN_MEANINGFUL_WORDS,
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a minimal valid MCQ question dict
# ─────────────────────────────────────────────────────────────────────────────

def _make_mcq(question: str, source: str | None = None) -> tuple[dict, str | None]:
    q = {
        "type": "MCQ",
        "question": question,
        "options": {"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
        "correct_answer": "A",
        "explanation": "some explanation",
        "marks": 2,
    }
    return q, source


# ═════════════════════════════════════════════════════════════════════════════
# A. ADVERSARIAL INPUT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestAdversarialInput(unittest.TestCase):
    """
    Rule 10A: Input that contains file-type text should only produce
    questions about actual content, not about the file format itself.
    """

    def test_filetype_question_rejected_when_not_in_source(self):
        """
        Question about 'PDF' is rejected when source chunk does not contain 'PDF'.
        """
        q, _ = _make_mcq("What is a PDF file used for?")
        source = "The water cycle involves evaporation, condensation, and precipitation."
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertFalse(ok, "Should reject file-type question not grounded in source.")
        self.assertIn("Leakage", msg)

    def test_filetype_question_allowed_when_in_source(self):
        """
        Question about 'PDF' is ALLOWED when source chunk explicitly discusses PDFs.
        """
        q, _ = _make_mcq("What is a PDF format primarily used for?")
        source = (
            "The PDF (Portable Document Format) is a file format developed by Adobe "
            "to present documents independently of application software, hardware, and "
            "operating system. PDF files can contain text, images, and interactive forms."
        )
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertTrue(ok, f"Should allow PDF question when source is about PDFs. Got: {msg}")

    def test_generic_file_question_rejected(self):
        """'What does this file contain?' should be rejected."""
        q, _ = _make_mcq("What does this file contain and explain the file format?")
        source = "Photosynthesis converts light energy into chemical energy stored in glucose."
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertFalse(ok, "Should reject generic 'file' question.")

    def test_content_question_passes(self):
        """A properly grounded content question must pass."""
        q, _ = _make_mcq(
            "What process do plants use to convert light energy into glucose?"
        )
        source = (
            "Photosynthesis is the process by which plants use sunlight, water, and "
            "carbon dioxide to produce oxygen and energy in the form of glucose. "
            "Chlorophyll in plant cells absorbs light energy."
        )
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertTrue(ok, f"Content-grounded question must pass. Got: {msg}")

    def test_csv_question_rejected_when_not_in_source(self):
        """Question about 'CSV file' when source discusses thermodynamics."""
        q, _ = _make_mcq("What does a CSV file contain?")
        source = (
            "Entropy is a measure of disorder in thermodynamic systems. "
            "The second law of thermodynamics states that entropy always increases."
        )
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertFalse(ok, "Should reject CSV question when source is about thermodynamics.")

    def test_audio_file_question_rejected(self):
        """Question about 'audio file' when source is about biology."""
        q, _ = _make_mcq("What is this audio file about?")
        source = "The human heart has four chambers: right atrium, left atrium, right ventricle, left ventricle."
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertFalse(ok)

    def test_format_question_rejected(self):
        """Question about 'format' when source has no format discussion."""
        q, _ = _make_mcq("Describe the format used to store this data.")
        source = "Newton's three laws of motion describe force, mass, and acceleration relationships."
        ok, msg = validate_question(q, "MCQ", source_chunk=source)
        self.assertFalse(ok)


# ═════════════════════════════════════════════════════════════════════════════
# B. WEAK PLACEHOLDER CASE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestWeakPlaceholderCase(unittest.TestCase):
    """
    Rule 10B: Image/audio/video with no OCR/transcript should produce 0 questions.
    Tests the content_validator threshold gate.
    """

    def test_empty_content_fails_validation(self):
        """Empty string from image with no vision model."""
        ok, msg = validate_content("")
        self.assertFalse(ok)
        self.assertTrue(len(msg) > 0, "Must return a non-empty failure reason.")

    def test_whitespace_only_fails_validation(self):
        """Whitespace-only content (e.g. blank PDF page)."""
        ok, msg = validate_content("   \n\t  \n  ")
        self.assertFalse(ok)

    def test_below_threshold_fails_validation(self):
        """Content with fewer words than MIN_MEANINGFUL_WORDS."""
        short_text = "image file uploaded"
        ok, msg = validate_content(short_text)
        self.assertFalse(ok, f"Very short text should fail. MIN={MIN_MEANINGFUL_WORDS}")

    def test_numeric_only_fails_validation(self):
        """Pure numeric content (e.g. a CSV with only numbers, no headers)."""
        numeric = "\n".join([", ".join([str(i * j) for j in range(5)]) for i in range(20)])
        ok, msg = validate_content(numeric)
        self.assertFalse(ok, "Numeric-only content should fail alpha ratio check.")

    def test_sufficient_content_passes(self):
        """Enough real text passes the content gate."""
        text = " ".join(["Photosynthesis converts sunlight into glucose in plant cells"] * 10)
        ok, msg = validate_content(text)
        self.assertTrue(ok, f"Sufficient content should pass. Got: {msg}")


# ═════════════════════════════════════════════════════════════════════════════
# C. MIXED INPUT CASE TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestMixedInputCase(unittest.TestCase):
    """
    Rule 10C: One valid file + one empty/corrupt file.
    Valid file must be processed; invalid file must be skipped gracefully.
    """

    def _make_report(self, valid_content: str, invalid_content: str, invalid_meta: dict) -> dict:
        file_results = [
            {"filename": "valid_doc.txt",   "content": valid_content,   "metadata": {}},
            {"filename": "empty_image.png", "content": invalid_content, "metadata": invalid_meta},
        ]
        return build_ingestion_report(file_results)

    def test_valid_file_counted_processed(self):
        valid_text = " ".join(["The mitochondria is the powerhouse of the cell"] * 20)
        report = self._make_report(valid_text, "", {"status": "insufficient_content"})
        self.assertEqual(report["processed_files"], 1)
        self.assertEqual(report["skipped_files"],   1)

    def test_invalid_file_has_skip_reason(self):
        valid_text = " ".join(["The mitochondria is the powerhouse of the cell"] * 20)
        report = self._make_report(valid_text, "", {"status": "insufficient_content"})
        reasons = report["reasons"]
        self.assertTrue(len(reasons) >= 1, "Should have at least one skip reason.")
        self.assertIn("empty_image.png", reasons[0])

    def test_error_file_counted_as_skipped(self):
        valid_text = " ".join(["The mitochondria is the powerhouse of the cell"] * 20)
        report = self._make_report(valid_text, "", {"status": "error", "error": "decode failed"})
        self.assertEqual(report["skipped_files"], 1)

    def test_combined_text_from_valid_file_passes_content_gate(self):
        valid_text = " ".join(["The mitochondria is the powerhouse of the cell"] * 20)
        # Simulate what app.py does: only concatenate non-empty content
        all_text = valid_text  # empty file contributes nothing
        ok, _ = validate_content(all_text)
        self.assertTrue(ok, "Combined text from valid file should pass content gate.")

    def test_all_empty_files_fails_content_gate(self):
        """If all files are empty/skip, the content gate should block generation."""
        all_text = ""
        ok, msg = validate_content(all_text)
        self.assertFalse(ok)


# ═════════════════════════════════════════════════════════════════════════════
# D. METADATA-ONLY INPUT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestMetadataOnlyInput(unittest.TestCase):
    """
    Rule 10D: Content that is purely metadata/formatting should produce no questions.
    """

    def test_metadata_string_fails_content_gate(self):
        """Old-style metadata strings (like extractor used to return) must be rejected."""
        metadata_strings = [
            "[DOCX extraction failed: missing library]",
            "[Extraction error for report.pdf: unable to parse]",
            "[File skipped: exceeds 10MB strict limit]",
            "[Archive validated. Contains 5 files.]",
            "Image: Report.\n[File: report.png, Size: 120.1 KB]\nNote: Install llama3.2-vision",
        ]
        for text in metadata_strings:
            ok, _ = validate_content(text)
            self.assertFalse(ok, f"Metadata string should fail gate: '{text[:60]}'")

    def test_chunk_with_error_message_is_invalid(self):
        """is_valid_chunk() must reject extraction error strings."""
        error_chunks = [
            # Matches r"extraction (error|failed)"
            "[Extraction error for report.pdf: unable to parse] and some extra words here to exceed MIN_WORDS threshold",
            # Matches r"could not extract"
            "Could not extract text from this document so we cannot proceed with question generation",
            # Matches r"note:?\s+install\s+llama"
            "Note: install llama model for this image file because the vision feature requires setup",
            # Matches r"\[sheet:\s*"
            "[Sheet: Revenue] data including quarterly figures for the current fiscal year period",
        ]
        for chunk in error_chunks:
            self.assertFalse(
                is_valid_chunk(chunk),
                f"Error-message chunk should be rejected: '{chunk[:60]}'"
            )

    def test_xlsx_sheet_label_only_chunk_is_invalid(self):
        """A chunk composed only of [Sheet: X] labels (inline) is metadata noise."""
        # This matches the _CONTENT_REJECTION_PATTERNS rule for r"\[sheet:\s*"
        sheet_chunk = (
            "[Sheet: Summary] and various data columns including revenue expenses profit "
            "[Sheet: Data] quarterly results [Sheet: Overview] annual summary totals here"
        )
        self.assertFalse(
            is_valid_chunk(sheet_chunk),
            "Chunk containing [Sheet:] labels should be rejected as metadata artefact."
        )

    def test_real_content_chunk_is_valid(self):
        """A genuine content chunk from a science textbook must be valid."""
        good_chunk = (
            "The process of cellular respiration involves breaking down glucose molecules "
            "to release energy in the form of ATP. This occurs in three main stages: "
            "glycolysis, the Krebs cycle, and the electron transport chain. "
            "Mitochondria are the primary site of aerobic respiration in eukaryotic cells."
        )
        self.assertTrue(is_valid_chunk(good_chunk))


# ═════════════════════════════════════════════════════════════════════════════
# LEAKAGE DETECTION UNIT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestLeakageDetection(unittest.TestCase):

    def test_no_filetype_term_no_leakage(self):
        q = "What is the role of ATP in cellular respiration?"
        src = "ATP is the energy currency of the cell produced during respiration."
        self.assertFalse(_is_leakage_question(q, src))

    def test_filetype_in_question_not_in_source_is_leakage(self):
        q = "What information is stored in a CSV file?"
        src = "The human digestive system breaks down food into nutrients."
        self.assertTrue(_is_leakage_question(q, src))

    def test_filetype_in_question_and_in_source_is_not_leakage(self):
        q = "What is the primary purpose of a CSV file format?"
        src = "CSV (Comma-Separated Values) is a file format used to store tabular data."
        self.assertFalse(_is_leakage_question(q, src))

    def test_no_source_is_conservative_leakage(self):
        q = "What does this PDF document contain?"
        self.assertTrue(_is_leakage_question(q, None))


# ═════════════════════════════════════════════════════════════════════════════
# GROUNDING UNIT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestGroundingCheck(unittest.TestCase):

    def test_overlapping_terms_are_grounded(self):
        q = "What process converts glucose into ATP during respiration?"
        src = "Cellular respiration converts glucose molecules into ATP through glycolysis."
        self.assertTrue(_is_grounded(q, src))

    def test_no_overlapping_terms_is_ungrounded(self):
        q = "Explain the theory of relativity and time dilation effects."
        src = "Photosynthesis uses chlorophyll to absorb sunlight and produce glucose."
        self.assertFalse(_is_grounded(q, src))

    def test_no_source_skips_grounding_check(self):
        q = "What is the speed of light?"
        self.assertTrue(_is_grounded(q, None))  # can't check without source

    def test_short_question_skips_grounding_check(self):
        """Very short questions that produce no key terms are not rejected."""
        q = "Why?"
        src = "Some content about photosynthesis."
        self.assertTrue(_is_grounded(q, src))


# ═════════════════════════════════════════════════════════════════════════════
# CHUNK QUALITY TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestChunkQuality(unittest.TestCase):

    def test_too_short_chunk_invalid(self):
        self.assertFalse(is_valid_chunk("short text"))

    def test_symbol_heavy_chunk_invalid(self):
        symbol_chunk = "!@#$%^&*() 12345 67890 !@#$%^&*() " * 10
        self.assertFalse(is_valid_chunk(symbol_chunk))

    def test_real_content_valid(self):
        good = (
            "Newton's first law of motion states that an object will remain at rest "
            "or in uniform motion unless acted upon by an external force. This principle "
            "is also known as the law of inertia and forms the foundation of classical mechanics."
        )
        self.assertTrue(is_valid_chunk(good))

    def test_chunk_text_returns_only_valid_chunks(self):
        """chunk_text() must filter out noise/error content."""
        mixed_text = (
            "--- From: example.jpg ---\n"  # separator header → noise
            "Note: Install llama3.2-vision in Ollama for content-aware question generation.\n"
            "\n\n"
            "The respiratory system consists of the lungs, trachea, bronchi, and diaphragm. "
            "Oxygen is transported to cells through the bloodstream via red blood cells. "
            "Carbon dioxide is expelled during exhalation as a waste product of cellular respiration. "
            "The rate of breathing is controlled by the medulla oblongata in the brainstem. "
            "Homeostasis requires careful regulation of blood oxygen and carbon dioxide levels."
        )
        chunks = chunk_text(mixed_text, chunk_size=60, overlap=10)
        for chunk in chunks:
            self.assertTrue(
                is_valid_chunk(chunk),
                f"chunk_text() returned an invalid chunk: '{chunk[:80]}'"
            )


# ═════════════════════════════════════════════════════════════════════════════
# INGESTION REPORT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestIngestionReport(unittest.TestCase):

    def test_all_ok(self):
        results = [
            {"filename": "doc.pdf", "content": "Real content about biology " * 20, "metadata": {}},
            {"filename": "notes.txt", "content": "Thermodynamics entropy energy " * 20, "metadata": {}},
        ]
        report = build_ingestion_report(results)
        self.assertEqual(report["processed_files"], 2)
        self.assertEqual(report["skipped_files"],   0)

    def test_mixed_skips(self):
        results = [
            {"filename": "doc.pdf",   "content": "Real content " * 30, "metadata": {}},
            {"filename": "audio.mp3", "content": "", "metadata": {"status": "insufficient_content"}},
            {"filename": "video.mp4", "content": "", "metadata": {"status": "insufficient_content"}},
        ]
        report = build_ingestion_report(results)
        self.assertEqual(report["processed_files"], 1)
        self.assertEqual(report["skipped_files"],   2)
        self.assertEqual(len(report["reasons"]),    2)

    def test_error_file_counted(self):
        results = [
            {"filename": "corrupt.docx", "content": "", "metadata": {"status": "error", "error": "bad zip"}},
        ]
        report = build_ingestion_report(results)
        self.assertEqual(report["skipped_files"], 1)
        self.assertIn("corrupt.docx", report["reasons"][0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
