
# Lumina Assessment —  Project Explanation
---

# 1. Problem Understanding

The goal was to build a system that can:

- Take any document (PDF, DOCX, etc.)
- Read and understand its content
- Create questions from it
- Let users answer those questions
- Check answers and give marks + feedback

In simple terms:

"Turn any document into a quiz and evaluate it automatically."

The difficult part was:
- Documents are messy and different
- AI is not always reliable
- The system must still work correctly every time

---

# 2. Research Findings

While building this, a few important things were discovered:

### AI is not perfect
- Sometimes gives wrong format
- Sometimes adds extra unwanted text
- Sometimes ignores instructions

### Large documents don’t work directly
- If you give a full document → AI forgets most of it
- Only focuses on first part

### Different files behave differently
- PDF, CSV, images all need different handling
- Some files don’t even contain useful text

### Using AI for everything is slow
- Even simple answers like True/False became very slow
- Not efficient

---

# 3. Approach Taken

### Step 1: Break document into parts (Chunking)

Instead of giving full document: Split into small pieces

This ensures:
- AI understands better
- No information is missed

### Step 2: Generate questions from each part

Each chunk is sent to AI separately.

So:
- All parts of document are covered
- No "first-page only" problem

### Step 3: Validate AI output

AI output is NOT trusted directly.

System checks:
- Format is correct
- Questions make sense
- No irrelevant questions


### Step 4: Smart grading system

Different types of questions use different methods:

- MCQ → exact match
- One word → similarity check
- Long answers → AI evaluation

This makes system fast + accurate


### Step 5: Save everything safely

Data is stored in database so:
- nothing is lost
- user can come back anytime

---

# 4. Alternatives Tried


## 1. Trying full document at once
❌ Failed: AI ignored most content

✔ Solution: chunking



## 2. Using AI for all grading
❌ Failed: Very slow + inconsistent

✔ Solution: mix of AI + simple logic


## 3. Using cloud AI (like OpenAI)
❌ Rejected: Privacy issues + cost

✔ Solution: local model (LLaMA)

---

# 5. Challenges Faced

### AI giving wrong format
- JSON breaking
- extra text added

Fixed using:
- validation
- retry system

### Handling many file types
- each format behaves differently

Fixed using:
- separate extractors


### Streamlit resetting data
- data lost on every click

Fixed using:
- database (SQLite)


### Large data processing
- slow and heavy

Fixed using:
- chunking
- controlled execution

---

# 6. Learnings


### 1. AI cannot be trusted directly
Always:
- validate
- retry
- control output


### 2. Simple logic is powerful
For example:
- checking "Paris == Paris" is faster than AI


### 3. Structure is more important than intelligence
A well-designed pipeline works better than random AI usage


### 4. Failure handling is necessary
System must:
- not crash
- continue working even if something fails

### 5. Hybrid approach is best
Best system is AI + traditional programming together

---

# 7. Final Summary

This project is not just a quiz system. It is A complete pipeline that turns documents into evaluated quizzes
It works because:

- Input is controlled
- AI is validated
- Errors are handled
- Output is structured

---
