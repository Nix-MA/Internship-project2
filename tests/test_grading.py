import pytest
from src.grading.deterministic import grade_mcq, grade_true_false

def test_grade_mcq():
    assert grade_mcq("A", "A") == (True, "Correct")
    assert grade_mcq("A", "  B  ")[0] is False

def test_grade_true_false():
    assert grade_true_false("True", "true") == (True, "Correct")
    assert grade_true_false("True", "false")[0] is False
