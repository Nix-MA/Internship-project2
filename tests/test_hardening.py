import os
import sys
import unittest
import json
import sqlite3

# Add src to path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ingestion.chunker import chunk_text
from storage.db import save_draft, load_draft, clear_draft, DB_PATH, init_db
from grading.llm_grader import _sanitize_llm_result
from evaluation.evaluator import evaluate_answer
from grading.llm_grader import _sanitize_llm_result
from evaluation.evaluator import evaluate_answer


class TestSystemHardening(unittest.TestCase):
    
    def test_chunker_maximum_limit(self):
        # Create a massive text string with 60k words
        massive_text = "word " * 60000
        chunks = chunk_text(massive_text, chunk_size=500, overlap=100)
        
        # Verify it clipped successfully (37.5k / 500 = ~75 chunks roughly, or 37.5k words max)
        total_words = sum(len(c.split()) for c in chunks)
        # We might have slight overlap duplication, so total words could be a bit over 37500,
        # but the input text was capped at 37500. So we expect exactly 37500 unique words.
        # Actually total chunked words might be more because of overlaps.
        # Let's just check length of chunks is reasonable
        self.assertTrue(len(chunks) > 0)
        self.assertTrue(total_words < 50000, f"Token limit failed; total words: {total_words}")

    def test_file_size_limit_mock(self):
        # We need to simulate a file that exceeds the size limit.
        import tempfile
        from ingestion.extractor import extract_document
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            # Write exactly 11MB of dummy data
            tmp.write(b"a" * (11 * 1024 * 1024))
            tmp_path = tmp.name
        
        try:
            res = extract_document(tmp_path)
            self.assertIn("exceeds", res["content"])
            self.assertEqual(res["type"], "text")
        finally:
            os.unlink(tmp_path)

    def test_draft_persistence(self):
        init_db()
        clear_draft()
        self.assertIsNone(load_draft())
        
        test_state = {"stage": "quiz", "current_q": 3, "answers": {0: "a", 1: "b"}}
        save_draft(test_state)
        
        loaded = load_draft()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["current_q"], 3)
        self.assertEqual(loaded["answers"]["1"], "b")  # JSON dumps int keys to strings
        
        clear_draft()
        self.assertIsNone(load_draft())

    def test_llm_grading_strict_schema(self):
        # Test the fallback parsing if LLM utterly fails
        from rubric_engine.rubrics import get_rubric
        
        question = {"type": "Short Answer", "marks": 5, "question": "Explain python."}
        student_answer = "idk"
        
        from unittest.mock import patch
        
        # We simulate the evaluator catching a total LLM failure or timeout.
        with patch('grading.llm_grader._call_ollama') as mock_llm:
            mock_llm.return_value = None
            res = evaluate_answer(question, student_answer, context="N/A")
            
            # Expect strict zero-score fallback
            self.assertEqual(res["score"], 0)
            self.assertEqual(res["max_score"], 5)
            self.assertEqual(res["status"], "error")
        # Ensure it satisfies rubric engine output structure natively
        self.assertIn("criteria_scores", res)


if __name__ == "__main__":
    unittest.main()
