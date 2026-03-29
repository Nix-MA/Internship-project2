import sys
import logging
sys.path.append('src')
from utils.exporters import generate_pdf_report

out = generate_pdf_report({
    "summary": {},
    "questions": [
        {
            "index": 1,
            "type": "Short Answer",
            "score": 1,
            "max_score": 1,
            "is_correct": True,
            "question": "What is Lumina?",
            "correct_answer": "It’s a robust tool.", # \u2019
            "user_answer": "“It's a good tool”", # \u201c \u201d
            "feedback": "—" # \u2014
        }
    ]
})
if out is None:
    print("FAILED")
else:
    print("SUCCESS")
