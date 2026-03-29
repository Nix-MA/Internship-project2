"""
question_generation/prompts.py — Prompt templates for all 8 question types.

Each template uses {count}, {marks}, and {context} placeholders.
Prompts instruct the LLM to return ONLY a JSON array with the exact schema.

ANTI-LEAKAGE RULE (enforced in every prompt):
  - Generate questions ONLY from the semantic content of the text.
  - DO NOT generate questions about file types, formats, metadata, or upload process.
  - If the text does not contain enough meaningful subject matter, RETURN an empty list [].
  - Do NOT infer or hallucinate missing information.
"""

# Mandatory anti-leakage + anti-hallucination block injected into every prompt.
_ANTI_LEAKAGE = """\
CRITICAL CONTENT RULES (MUST FOLLOW):
- Generate questions ONLY from the semantic content of the text provided below.
- ALL generated questions MUST BE COMPLETELY UNIQUE. Do not repeat the same question, concept, or answer.
- DO NOT generate questions about file types, formats, metadata, or how the content was uploaded.
- DO NOT mention words like "PDF", "DOCX", "CSV", "file", "image", "picture", "photo", "worksheet", "format", or "document type" in any question or answer.
- DO NOT infer or hallucinate information that is not explicitly present in the text.
- If the text does not contain enough meaningful subject matter to form {count} questions, return as many as you can. If there is no meaningful content at all, return an empty JSON array: []
"""

PROMPTS: dict[str, str] = {

    "MCQ": """\
You are an expert quiz designer. Generate exactly {count} multiple-choice questions based ONLY on the text below.

STRICT RULES:
- Each question must have exactly 4 options: A, B, C, D
- Only ONE option is correct
- Include a brief explanation (≤2 sentences)
- All content must come from the provided text
- If there's not enough info for {count} questions, generate as many as you can safely.
- Return ONLY a valid JSON array. No extra text, no markdown prose.

""" + _ANTI_LEAKAGE + """
JSON schema (follow exactly):
[
  {{
    "type": "MCQ",
    "question": "<clear, unambiguous question about the content>",
    "options": {{
      "A": "<option text>",
      "B": "<option text>",
      "C": "<option text>",
      "D": "<option text>"
    }},
    "correct_answer": "<single letter: A, B, C, or D>",
    "explanation": "<why this answer is correct, referencing the content>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "True / False": """\
You are an expert quiz designer. Generate exactly {count} True/False questions based ONLY on the text below.

STRICT RULES:
- Each question must be a clear factual statement (not a question sentence) derived strictly from the text
- Include a brief explanation of why it is true or false
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array. No extra text.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "True / False",
    "question": "<declarative statement about the content to judge as true or false>",
    "correct_answer": "<True or False>",
    "explanation": "<one sentence justification referencing the content>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "Fill in the Blanks": """\
You are an expert quiz designer. Generate exactly {count} fill-in-the-blank questions based ONLY on the text below.

STRICT RULES:
- Use exactly _____ (5 underscores) for each blank
- The blank must replace a key term or concept from the text
- correct_answer must be the exact word/phrase for the blank as found in the text
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "Fill in the Blanks",
    "question": "<sentence from the content with _____ marking the blank>",
    "correct_answer": "<exact answer for the blank, taken from the content>",
    "explanation": "<one sentence context from the text>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "Short Answer": """\
You are an expert quiz designer. Generate exactly {count} short-answer questions based ONLY on the text below.

STRICT RULES:
- Questions must require a 2–3 sentence answer answerable from the text
- Provide a model answer and at least 3 specific grading points drawn from the text
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "Short Answer",
    "question": "<question requiring 2–3 sentences, answerable from the content>",
    "correct_answer": "<model answer in 2–3 sentences based on the content>",
    "grading_points": [
      "<key point 1 from the content>",
      "<key point 2 from the content>",
      "<key point 3 from the content>"
    ],
    "explanation": "<what topics in the text to study>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "Long Answer": """\
You are an expert quiz designer. Generate exactly {count} long-answer questions based ONLY on the text below.

STRICT RULES:
- Questions must require a detailed, structured paragraph answer based on the text
- Provide a comprehensive model answer and at least 5 grading points from the text
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "Long Answer",
    "question": "<comprehensive question requiring a detailed answer, based on the content>",
    "correct_answer": "<detailed model answer covering all key aspects found in the text>",
    "grading_points": [
      "<key point 1>",
      "<key point 2>",
      "<key point 3>",
      "<key point 4>",
      "<key point 5>"
    ],
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "Match the Following": """\
You are an expert quiz designer. Generate exactly {count} match-the-following questions based ONLY on the text below.

STRICT RULES:
- Each question must have exactly 4 pairs to match
- Left column: terms/concepts from the text. Right column: definitions/matches from the text
- All items must come from the document content, not generic knowledge
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "Match the Following",
    "question": "Match each item in Column A with the correct item in Column B.",
    "pairs": {{
      "<term 1 from content>": "<match 1 from content>",
      "<term 2 from content>": "<match 2 from content>",
      "<term 3 from content>": "<match 3 from content>",
      "<term 4 from content>": "<match 4 from content>"
    }},
    "explanation": "<brief explanation of the relationships as found in the text>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "Assertion & Reason": """\
You are an expert quiz designer. Generate exactly {count} assertion-reason questions based ONLY on the text below.

STRICT RULES:
- Assertion (A) must be a factual statement verifiable in the text
- Reason (R) must be an explanatory statement related to A, also from the text
- correct_answer must be exactly one of: A, B, C, or D
- Options are ALWAYS:
  A. Both A and R are true, and R is the correct explanation of A
  B. Both A and R are true, but R is NOT the correct explanation of A
  C. A is true but R is false
  D. A is false but R is true
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "Assertion & Reason",
    "question": "Choose the correct option for the assertion and reason below.",
    "assertion": "<factual assertion statement from the content>",
    "reason": "<explanatory reason statement from the content>",
    "correct_answer": "<A, B, C, or D>",
    "explanation": "<explanation of why this option is correct, referencing the content>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",

    "One Word Answer": """\
You are an expert quiz designer. Generate exactly {count} one-word or one-phrase answer questions based ONLY on the text below.

STRICT RULES:
- The answer must be a single word or very short phrase (≤4 words) found in the text
- Question must be specific enough to have only one correct answer derivable from the text
- If there's not enough info for {count} questions, generate as many as you can.
- Return ONLY a valid JSON array.

""" + _ANTI_LEAKAGE + """
JSON schema:
[
  {{
    "type": "One Word Answer",
    "question": "<specific question with a single-word/phrase answer from the content>",
    "correct_answer": "<single word or short phrase from the content>",
    "explanation": "<one sentence context from the text>",
    "marks": {marks}
  }}
]

TEXT:
{context}""",
}
