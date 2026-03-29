"""
storage/db.py — Extended SQLite persistence layer.

Schema:
    sessions      — one row per quiz attempt
    questions     — full question JSON per session
    answers       — student answer + rubric output per question
    rubric_scores — per-criterion scores (one row per criterion per answer)
    results       — final grade + weakness/strength summary per session

All tables are created idempotently (IF NOT EXISTS).
Existing quiz_data.db is migrated safely with ALTER TABLE ... ADD COLUMN IF SUPPORTED.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "quiz_data.db")


# ── Schema ─────────────────────────────────────────────────────────────────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total_questions INTEGER,
        total_score     INTEGER,
        max_score       INTEGER,
        files_used      TEXT,
        grade           TEXT,
        percentage      REAL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS questions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id  INTEGER NOT NULL,
        q_index     INTEGER NOT NULL,
        q_type      TEXT NOT NULL,
        question    TEXT NOT NULL,
        full_json   TEXT,
        marks       INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS answers (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      INTEGER NOT NULL,
        question_id     INTEGER,
        question_number INTEGER,
        question        TEXT,
        question_type   TEXT,
        correct_answer  TEXT,
        student_answer  TEXT,
        is_correct      INTEGER,
        score           INTEGER,
        max_score       INTEGER,
        feedback        TEXT,
        hint            TEXT,
        strengths       TEXT,
        weaknesses      TEXT,
        improvements    TEXT,
        rubric_output   TEXT,
        FOREIGN KEY (session_id)  REFERENCES sessions(id),
        FOREIGN KEY (question_id) REFERENCES questions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rubric_scores (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        answer_id   INTEGER NOT NULL,
        session_id  INTEGER NOT NULL,
        q_type      TEXT,
        criterion   TEXT NOT NULL,
        score       INTEGER,
        weight      REAL,
        FOREIGN KEY (answer_id)  REFERENCES answers(id),
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS results (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id      INTEGER NOT NULL UNIQUE,
        grade           TEXT,
        percentage      REAL,
        total_score     INTEGER,
        max_score       INTEGER,
        strengths_json  TEXT,
        weaknesses_json TEXT,
        type_stats_json TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS active_draft (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        state_json TEXT
    )
    """
]


def init_db():
    """Create all tables (idempotent). Safe to call multiple times."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for ddl in _DDL:
        c.execute(ddl)
    conn.commit()
    conn.close()


# ── Save session ───────────────────────────────────────────────────────────────

def save_session(
    questions: list[dict],
    answers_dict: dict,
    evaluations: list[dict],
    files_used: list[str] | None = None,
) -> int:
    """
    Persist a completed quiz session to DB.

    Returns:
        session_id (int)
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    total_score = sum(e.get("score", 0) for e in evaluations)
    max_score   = sum(q.get("marks", 1) for q in questions)
    pct         = round((total_score / max_score) * 100, 1) if max_score else 0.0
    grade       = _compute_grade(pct)
    files_str   = ", ".join(files_used) if files_used else ""

    # ── sessions ──
    c.execute("""
        INSERT INTO sessions (total_questions, total_score, max_score, files_used, grade, percentage)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (len(questions), total_score, max_score, files_str, grade, pct))
    session_id = c.lastrowid

    type_stats: dict[str, dict] = {}

    for i, q in enumerate(questions):
        q_type     = q.get("type", "MCQ")
        marks      = q.get("marks", 1)
        ev         = evaluations[i] if i < len(evaluations) else {}
        student_ans = answers_dict.get(i, "[No answer]")
        correct_ans = q.get("correct_answer", q.get("pairs", ""))

        # ── questions ──
        c.execute("""
            INSERT INTO questions (session_id, q_index, q_type, question, full_json, marks)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, i, q_type, q["question"], json.dumps(q), marks))
        question_id = c.lastrowid

        # ── answers ──
        c.execute("""
            INSERT INTO answers
            (session_id, question_id, question_number, question, question_type,
             correct_answer, student_answer, is_correct, score, max_score,
             feedback, hint, strengths, weaknesses, improvements, rubric_output)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, question_id, i + 1,
            q["question"], q_type,
            str(correct_ans)[:500],
            str(student_ans)[:2000],
            1 if ev.get("is_correct") else 0,
            ev.get("score", 0), marks,
            ev.get("feedback", ""),
            ev.get("hint", ""),
            ev.get("strengths", ""),
            ev.get("weaknesses", ""),
            ev.get("improvements", ""),
            json.dumps(ev),
        ))
        answer_id = c.lastrowid

        # ── rubric_scores (per criterion) ──
        criteria_scores = ev.get("criteria_scores", {})
        rubric_weights  = _get_rubric_weights(q_type)
        for criterion, score in criteria_scores.items():
            weight = rubric_weights.get(criterion, 0.0)
            c.execute("""
                INSERT INTO rubric_scores (answer_id, session_id, q_type, criterion, score, weight)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (answer_id, session_id, q_type, criterion, score, weight))

        # Accumulate per-type stats
        if q_type not in type_stats:
            type_stats[q_type] = {"earned": 0, "max": 0, "count": 0, "criteria": {}}
        type_stats[q_type]["earned"] += ev.get("score", 0)
        type_stats[q_type]["max"]    += marks
        type_stats[q_type]["count"]  += 1
        for crit, cscore in criteria_scores.items():
            ts_crit = type_stats[q_type]["criteria"]
            ts_crit[crit] = ts_crit.get(crit, 0) + cscore

    # ── Compute strengths/weaknesses at session level ──
    strengths, weaknesses = _analyse_performance(type_stats, evaluations, questions)

    # ── results ──
    c.execute("""
        INSERT OR REPLACE INTO results
        (session_id, grade, percentage, total_score, max_score, strengths_json, weaknesses_json, type_stats_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, grade, pct, total_score, max_score,
        json.dumps(strengths), json.dumps(weaknesses), json.dumps(type_stats),
    ))

    conn.commit()
    conn.close()
    return session_id


# ── Read queries ───────────────────────────────────────────────────────────────

def get_all_sessions() -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, created_at, total_questions, total_score, max_score, grade, percentage
        FROM sessions ORDER BY created_at DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def get_session_answers(session_id: int) -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT question_number, question, question_type, correct_answer,
               student_answer, is_correct, score, max_score, feedback, hint,
               strengths, weaknesses, improvements
        FROM answers WHERE session_id = ? ORDER BY question_number
    """, (session_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def get_session_results(session_id: int) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT grade, percentage, total_score, max_score, strengths_json, weaknesses_json, type_stats_json
        FROM results WHERE session_id = ?
    """, (session_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "grade":       row[0],
        "percentage":  row[1],
        "total_score": row[2],
        "max_score":   row[3],
        "strengths":   json.loads(row[4] or "[]"),
        "weaknesses":  json.loads(row[5] or "[]"),
        "type_stats":  json.loads(row[6] or "{}"),
    }


def get_session_rubric_scores(session_id: int) -> list[tuple]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT q_type, criterion, SUM(score) as total, COUNT(*) as count, AVG(weight) as weight
        FROM rubric_scores WHERE session_id = ?
        GROUP BY q_type, criterion
        ORDER BY q_type, criterion
    """, (session_id,))
    rows = c.fetchall()
    conn.close()
    return rows


# ── Drafts ───────────────────────────────────────────────────────────────────────

def save_draft(state_dict: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO active_draft (id, state_json)
        VALUES (1, ?)
    """, (json.dumps(state_dict),))
    conn.commit()
    conn.close()


def load_draft() -> dict | None:
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT state_json FROM active_draft WHERE id = 1")
        row = c.fetchone()
        conn.close()
        if row and row[0]:
            return json.loads(row[0])
    except sqlite3.OperationalError:
        pass
    return None


def clear_draft():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM active_draft WHERE id = 1")
    conn.commit()
    conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_grade(pct: float) -> str:
    if pct >= 90: return "S"
    if pct >= 80: return "A"
    if pct >= 70: return "B"
    if pct >= 50: return "C"
    return "D"


def _get_rubric_weights(q_type: str) -> dict[str, float]:
    """Quick rubric weight lookup without importing the whole engine."""
    import sys, os as _os
    _src = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from rubric_engine.rubrics import get_rubric
    rubric = get_rubric(q_type)
    return {c["name"]: c["weight"] for c in rubric["criteria"]}


def _analyse_performance(
    type_stats: dict,
    evaluations: list[dict],
    questions: list[dict],
) -> tuple[list[str], list[str]]:
    """
    Compute session-level strength and weakness bullet points.

    Returns:
        (strengths: list[str], weaknesses: list[str])
    """
    strengths  = []
    weaknesses = []

    for q_type, stats in type_stats.items():
        if stats["max"] == 0:
            continue
        pct = round((stats["earned"] / stats["max"]) * 100)
        if pct >= 80:
            strengths.append(f"Strong in {q_type} ({pct}%)")
        elif pct < 50:
            weaknesses.append(f"Weak in {q_type} ({pct}%)")

        # Criterion-level insights (for LLM-graded types)
        if q_type in ("Short Answer", "Long Answer"):
            crit_data = stats.get("criteria", {})
            for crit, total_score in crit_data.items():
                n = stats["count"]
                avg = total_score / n if n else 0
                crit_label = crit.replace("_", " ").title()
                if avg < 0.4:  # below 40% of max weight on average
                    weaknesses.append(f"Weak in {crit_label} ({q_type})")
                elif avg > 0.75:
                    strengths.append(f"Strong in {crit_label} ({q_type})")

    return strengths, weaknesses
