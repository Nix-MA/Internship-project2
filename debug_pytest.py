import traceback
import sys

try:
    from src.grading.deterministic import grade_mcq, grade_true_false
    print("Deterministics imported fine.")
except Exception as e:
    with open("import_error.txt", "w") as f:
        traceback.print_exc(file=f)

try:
    from tests.test_grading import *
    print("test_grading imported fine.")
except Exception as e:
    with open("import_error_test.txt", "w") as f:
        traceback.print_exc(file=f)
