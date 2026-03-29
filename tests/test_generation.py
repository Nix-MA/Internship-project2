import pytest
from src.question_generation.generator import validate_question_list

def test_validate_question_list_rejects_malformed():
    raw_output = {"questions": [{"q": "?", "a": "!"}]}
    valid, res = validate_question_list(raw_output, "MCQ", 1, 1)
    assert not valid
    assert "Expected list" in res or "not proper list" in res

def test_validate_question_list_accepts_proper():
    raw_output = [
        {"question": "Q1?", "options": {"A":"1", "B":"2", "C":"3", "D":"4"}, "correct_answer": "A"}
    ]
    valid, res = validate_question_list(raw_output, "MCQ", 1, 1)
    assert valid
    assert len(res) == 1
    assert "marks" in res[0]
