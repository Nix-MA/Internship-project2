"""
Quiz-Doc-AI v2 — Production Streamlit App
Run: streamlit run src/app.py  (from the quiz-doc-ai-v2/ root)
"""

import streamlit as st
import tempfile, os, sys, json, time
from datetime import datetime

# ── Path setup ─────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import ollama

from src.ingestion.extractor  import extract_document
from src.chunking.chunker    import chunk_text, build_context
from src.validation.validator import validate_content, build_ingestion_report, INSUFFICIENT_CONTENT_MSG
from src.question_generation  import generate_questions_distributed, generate_questions_parallel
from src.evaluation           import evaluate_all, evaluate_all_answers
from src.storage.db           import init_db, save_session, get_all_sessions, get_session_answers, get_session_results, save_draft, load_draft, clear_draft
from src.rubric_engine.rubrics import get_rubric
from src.utils.exporters import build_export_schema, generate_pdf_report, generate_docx_report

# ── Page config ────────────────────────────────────────────────────────────────


# ── CSS ──




def run_ui():
    # ── Constants ──────────────────────────────────────────────────────────────────
    ALL_TYPES = {
        "MCQ":                 {"icon": "", "desc": "4-option multiple choice",        "default_marks": 2},
        "True / False":        {"icon": "", "desc": "Binary true or false",            "default_marks": 1},
        "Fill in the Blanks":  {"icon": "", "desc": "Complete the sentence",           "default_marks": 2},
        "Short Answer":        {"icon": "", "desc": "2–3 sentence response",           "default_marks": 4},
        "Long Answer":         {"icon": "", "desc": "Detailed paragraph answer",       "default_marks": 8},
        "Match the Following": {"icon": "", "desc": "Pair items from two columns",     "default_marks": 4},
        "Assertion & Reason":  {"icon": "", "desc": "Evaluate a claim and its reason", "default_marks": 3},
        "One Word Answer":     {"icon": "", "desc": "Single word or phrase",           "default_marks": 1},
    }
    
    GRADE_MSGS  = {"S": "Outstanding", "A": "Excellent", "B": "Good", "C": "Average", "D": "Needs Improvement"}
    GRADE_COLOR = {"S": "#16A34A", "A": "#059669", "B": "#2563EB", "C": "#D97706", "D": "#DC2626"}
    
    
    # ── Session state ──────────────────────────────────────────────────────────────
    def init_state():
        if "is_processing" not in st.session_state:
            st.session_state.is_processing = False
    
        draft = load_draft()
        if draft and "stage" not in st.session_state:
            for k, v in draft.items():
                # JSON keys become strings; answers dict expects integer keys
                if k == "answers":
                    v = {int(q_id): ans for q_id, ans in v.items()}
                st.session_state[k] = v
    
        defaults = {
            "stage": "config",
            "questions": [],
            "current_q": 0,
            "answers": {},
            "evaluations": [],
            "extracted_text": "",
            "uploaded_names": [],
            "q_config": [],
            "total_marks": 0,
            "session_id": None,
            "nav_target": None,       # used for results-page history redirect
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v
    
    init_state()
    
    def _sync_draft():
        """Save state subset to SQLite"""
        save_draft({
            "stage": st.session_state.stage,
            "questions": st.session_state.questions,
            "current_q": st.session_state.current_q,
            "answers": st.session_state.answers,
            "extracted_text": st.session_state.extracted_text,
            "uploaded_names": st.session_state.uploaded_names,
            "q_config": st.session_state.q_config,
            "total_marks": st.session_state.total_marks
        })
    
    
    from src.ui.layout import render_sidebar
    nav = render_sidebar()
    # ── Sidebar ────────────────────────────────────────────────────────────────────

    
    
    # ══════════════════════════════════════════════════════════════════════════════
    # HISTORY
    # ══════════════════════════════════════════════════════════════════════════════
    def _schema_from_history_rows(sid: int, rows: list, summary_data: dict) -> dict:
        """Reconstruct a normalized export schema from DB rows for history export."""
        questions_export = []
        for row in rows:
            q_num, question, q_type, correct, student, is_correct, score, max_s, feedback, hint, strengths, weaknesses, improvements = row
            questions_export.append({
                "index": q_num,
                "question": question or "",
                "type": q_type or "Unknown",
                "user_answer": student or "[No answer provided]",
                "correct_answer": correct or "N/A",
                "score": score or 0,
                "max_score": max_s or 1,
                "is_correct": bool(is_correct),
                "feedback": feedback or "",
                "hint": hint or "",
                "strengths": strengths or "",
                "weaknesses": weaknesses or "",
                "improvements": improvements or "",
                "criteria_scores": {},
            })
        return {
            "session_id": str(sid),
            "timestamp": str(summary_data.get("created", ""))[:16],
            "questions": questions_export,
            "summary": {
                "total_score": summary_data.get("total_score", 0),
                "max_score": summary_data.get("max_score", 0),
                "percentage": summary_data.get("pct", 0),
                "grade": summary_data.get("grade", "N/A"),
                "total_questions": len(rows),
                "correct_count": sum(1 for r in rows if r[5]),
                "performance_breakdown": summary_data.get("type_stats", {}),
            },
        }
    
    if nav == "History":
        # ── Top back navigation
        if st.button("<- Back to New Evaluation", key="hist_back"):
            st.session_state.nav_target = None  # clear any forced nav
            st.session_state.pop("sidebar_nav", None)
            st.rerun()
        st.markdown("---")
        st.markdown('<div class="main-header">Session History</div>', unsafe_allow_html=True)
        sessions = get_all_sessions()
        if not sessions:
            st.info("No sessions yet. Complete a quiz to see history here.")
        else:
            for s in sessions:
                sid, created, total_q, total_score, max_score, grade, pct = s
                grade = grade or "D"
                pct   = pct or 0
    
                with st.expander(f"Session #{sid} — {str(created)[:16]} — {total_score}/{max_score} marks — Grade {grade}"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Score",      f"{total_score}/{max_score}")
                    c2.metric("Percentage", f"{pct:.1f}%")
                    c3.metric("Grade",      grade)
    
                    # Per-type stats from results table
                    results = get_session_results(sid)
                    if results and results.get("type_stats"):
                        st.caption("**Performance by type:**")
                        ts = results["type_stats"]
                        tcols = st.columns(min(len(ts), 4))
                        for idx, (t, s_data) in enumerate(ts.items()):
                            tp = round((s_data["earned"] / s_data["max"]) * 100) if s_data["max"] else 0
                            tcols[idx % 4].metric(t[:12], f"{s_data['earned']}/{s_data['max']}", f"{tp}%")
    
                        if results.get("strengths"):
                            st.caption(" · ".join(results["strengths"][:3]))
                        if results.get("weaknesses"):
                            st.caption(" · ".join(results["weaknesses"][:3]))
    
                    rows = get_session_answers(sid)
                    st.caption("---")
                    for row in rows:
                        q_num, question, q_type, correct, student, is_correct, score, max_s, feedback, hint, strengths, weaknesses, improvements = row
                        icon = "[Correct]" if is_correct else "[Incorrect]"
                        st.write(f"{icon} **Q{q_num} [{q_type}]** — {score}/{max_s} — {question[:70]}...")
                        if feedback:
                            st.caption(f"  {feedback[:120]}")
    
                    # ── Export downloads ────────────────────────────────────────
                    st.markdown("---")
                    st.caption("Download this session's report:")
                    _hist_summary = {
                        "created": created,
                        "total_score": total_score,
                        "max_score": max_score,
                        "pct": pct,
                        "grade": grade,
                        "type_stats": results.get("type_stats", {}) if results else {},
                    }
                    _hist_schema  = _schema_from_history_rows(sid, rows, _hist_summary)
                    _hist_pdf     = generate_pdf_report(_hist_schema)
                    _hist_docx    = generate_docx_report(_hist_schema)
                    _hist_ts      = str(created)[:10].replace("-", "")
    
                    ex1, ex2 = st.columns(2)
                    with ex1:
                        if _hist_pdf:
                            st.download_button(
                                label="Download PDF",
                                data=_hist_pdf,
                                file_name=f"lumina_session_{sid}_{_hist_ts}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"pdf_{sid}",
                            )
                        else:
                            st.caption("PDF unavailable.")
                    with ex2:
                        if _hist_docx:
                            st.download_button(
                                label="Download DOCX",
                                data=_hist_docx,
                                file_name=f"lumina_session_{sid}_{_hist_ts}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True,
                                key=f"docx_{sid}",
                            )
                        else:
                            st.caption("DOCX unavailable.")
        st.stop()
    
    
    # ══════════════════════════════════════════════════════════════════════════════
    # CONFIG PAGE
    # ══════════════════════════════════════════════════════════════════════════════
    if st.session_state.stage == "config":
        # ── Page header ───────────────────────────────────────────────────────────
        st.markdown('<div class="main-header">Lumina Assessment</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">Upload documents, choose question types, and generate a personalized assessment.</div>', unsafe_allow_html=True)
    
        col_main, col_side = st.columns([3, 2], gap="large")
    
        with col_main:
    
            # ── Upload Card ───────────────────────────────────────────────────────
            st.markdown('<p style="font-size:16px;font-weight:600;color:#1E293B;margin-bottom:8px">Upload Documents</p>', unsafe_allow_html=True)
            with st.container(border=True):
                uploaded_files = st.file_uploader(
                    "upload_files",
                    type=["pdf","txt","png","jpg","jpeg","webp","gif","mp3","wav","mp4",
                          "mov","avi","zip","docx","csv","json","md","pptx","xlsx"],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                )
                st.caption("Supported: PDF, DOCX, TXT, Images (PNG/JPG), Audio (MP3/WAV), Video (MP4), ZIP, CSV, JSON, MD, PPTX, XLSX")
    
                if uploaded_files:
                    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
                    cols = st.columns(2)
                    for i, f in enumerate(uploaded_files):
                        size_kb = round(f.size / 1024, 1)
                        ext = f.name.split(".")[-1].upper()
                        cols[i % 2].markdown(
                            f'<div class="file-chip">📄 {f.name[:28]} <span style="color:#64748B;font-size:12px">{ext} · {size_kb} KB</span></div>',
                            unsafe_allow_html=True,
                        )
    
            # ── Video URL Card ────────────────────────────────────────────────────
            st.markdown('<p style="font-size:16px;font-weight:600;color:#1E293B;margin:16px 0 8px">Or Paste a Video URL</p>', unsafe_allow_html=True)
            with st.container(border=True):
                video_url = st.text_input(
                    "video_url",
                    placeholder="https://youtube.com/watch?v=...",
                    label_visibility="collapsed",
                )
                st.caption("YouTube and other video URLs are supported via transcript extraction.")
    
            # ── Question Types Card ───────────────────────────────────────────────
            st.markdown('<p style="font-size:16px;font-weight:600;color:#1E293B;margin:16px 0 8px">Question Types</p>', unsafe_allow_html=True)
            with st.container(border=True):
                selected_types = {}
                type_cols = st.columns(2)
                for i, (qtype, info) in enumerate(ALL_TYPES.items()):
                    with type_cols[i % 2]:
                        if st.checkbox(qtype, value=False, key=f"chk_{qtype}", help=info["desc"]):
                            selected_types[qtype] = info
    
            # ── Configure Marks Card ──────────────────────────────────────────────
            q_config = []
            if selected_types:
                st.markdown('<p style="font-size:16px;font-weight:600;color:#1E293B;margin:16px 0 8px">Configure Marks & Count</p>', unsafe_allow_html=True)
                for qtype, info in selected_types.items():
                    with st.container(border=True):
                        c_label, c1, c2 = st.columns([2, 1, 1])
                        with c_label:
                            st.markdown(f'<p style="font-weight:600;font-size:14px;margin:8px 0 0">{qtype}</p><p style="font-size:12px;color:#64748B;margin:0">{info["desc"]}</p>', unsafe_allow_html=True)
                        with c1:
                            count = st.number_input("Questions", min_value=1, max_value=20, value=None, step=1, key=f"cnt_{qtype}")
                        with c2:
                            marks = st.number_input("Marks each", min_value=1, max_value=50, value=None, step=1, key=f"mrk_{qtype}")
                        if count is not None and marks is not None:
                            q_config.append({"type": qtype, "count": count, "marks": marks})
    
        # ── Summary & Action Panel ────────────────────────────────────────────────
        with col_side:
            st.markdown('<div style="margin-top:52px"></div>', unsafe_allow_html=True)
            st.markdown('<p style="font-size:16px;font-weight:600;color:#1E293B;margin-bottom:12px">Assessment Summary</p>', unsafe_allow_html=True)
    
            with st.container(border=True):
                files_ok = bool(uploaded_files or video_url)
                types_ok = bool(selected_types)
                ready    = files_ok and types_ok
    
                file_ct   = len(uploaded_files) if uploaded_files else 0
                video_ct  = 1 if video_url else 0
                total_mrk = sum(c["count"] * c["marks"] for c in q_config) if q_config else 0
                total_q   = sum(c["count"] for c in q_config) if q_config else 0
    
                m1, m2 = st.columns(2)
                m1.metric("Files", file_ct + video_ct)
                m2.metric("Question Types", len(selected_types))
    
                if q_config:
                    m3, m4 = st.columns(2)
                    m3.metric("Questions", total_q)
                    m4.metric("Total Marks", total_mrk)
    
                st.markdown('<div style="margin-top:16px"></div>', unsafe_allow_html=True)
    
                if ready:
                    if st.button("Generate Assessment →", type="primary", use_container_width=True):
                        # ── Extract text ─────────────────────────────────────────
                        with st.spinner("Extracting text from your files..."):
                            all_text = ""
                            names = []
                            file_results = []
    
                            for f in uploaded_files:
                                names.append(f.name)
                                ext = f.name.split(".")[-1].lower()
                                with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
                                    tmp.write(f.read())
                                    tmp_path = tmp.name
                                try:
                                    doc = extract_document(tmp_path)
                                    content = doc.get("content", "")
                                    file_results.append({
                                        "filename": f.name,
                                        "content": content,
                                        "metadata": doc.get("metadata", {}),
                                    })
                                    if content.strip():
                                        all_text += f"\n\n{content}"
                                except Exception as e:
                                    file_results.append({
                                        "filename": f.name,
                                        "content": "",
                                        "metadata": {"status": "error", "error": str(e)},
                                    })
                                finally:
                                    try:
                                        os.unlink(tmp_path)
                                    except Exception:
                                        pass
    
                            ingestion_report = build_ingestion_report(file_results)
                            if ingestion_report["skipped_files"] > 0:
                                with st.expander(
                                    f"⚠️ {ingestion_report['skipped_files']} file(s) skipped — click to see details",
                                    expanded=True,
                                ):
                                    for detail in ingestion_report["file_details"]:
                                        if detail["status"] != "ok":
                                            icon = "❌" if detail["status"] == "error" else "⚠️"
                                            st.caption(f"{icon} **{detail['filename']}**: {detail['reason']}")
    
                            if video_url:
                                names.append("YouTube Video")
                                try:
                                    import re
                                    from youtube_transcript_api import YouTubeTranscriptApi
                                    match = re.search(r"(?:v=|\/|youtu\.be\/|shorts\/)([0-9A-Za-z_-]{11})", video_url)
                                    if match:
                                        vid_id = match.group(1)
                                        yt_api = YouTubeTranscriptApi()
                                        tlist = yt_api.list(vid_id)
                                        try:
                                            t = tlist.find_transcript(["en", "en-US", "en-GB", "hi"])
                                        except Exception:
                                            t = list(tlist)[0]
                                        fetched = t.fetch()
                                        transcript_text = " ".join([s.text for s in fetched.snippets])
                                        all_text += f"\n\n--- From YouTube Video ---\n{transcript_text}"
                                    else:
                                        all_text += f"\n\n--- From Video Link ---\n[Warning: Could not extract YouTube video ID from {video_url}.]"
                                except Exception as e:
                                    all_text += f"\n\n--- From Video Link ---\n[Could not get transcript for video: {e}]"
    
                        # ── Content gate ──────────────────────────────────────────
                        content_ok, content_msg = validate_content(all_text)
                        if not content_ok:
                            st.session_state.is_processing = False
                            if not (ingestion_report["skipped_files"] > 0 and ingestion_report["processed_files"] == 0):
                                st.error(content_msg)
                            st.stop()
    
                        chunks  = chunk_text(all_text, chunk_size=700, overlap=100)
                        context = build_context(chunks, max_chunks=8)
    
                        # ── Ollama check ──────────────────────────────────────────
                        try:
                            ollama.list()
                        except Exception:
                            st.session_state.is_processing = False
                            st.error("❌ Cannot connect to Ollama. Run `ollama serve` then retry.")
                            st.stop()
    
                        # ── Generate questions (parallel across all types) ────────
                        all_questions     = []
                        generation_failed = False

                        # Build a live status table — one row per question type
                        status_header = st.empty()
                        status_header.markdown(
                            "**Generating questions — all types run in parallel...**"
                        )
                        status_slots = {
                            cfg["type"]: st.empty() for cfg in q_config
                        }
                        for q_type, slot in status_slots.items():
                            slot.markdown(
                                f"⏳ &nbsp; **{q_type}** — generating…",
                                unsafe_allow_html=True,
                            )

                        progress    = st.progress(0)
                        completed   = [0]   # mutable counter for callback
                        total_types = len(q_config)

                        # Collect results in order
                        type_results: dict[str, list] = {}

                        def _on_type_done(q_type: str, qs: list):
                            """Called from generator thread as each type finishes."""
                            type_results[q_type] = qs
                            count_done = len(type_results)
                            n_got      = len(qs)
                            icon       = "✅" if n_got > 0 else "⚠️"
                            status_slots[q_type].markdown(
                                f"{icon} &nbsp; **{q_type}** — {n_got} question{'s' if n_got != 1 else ''} ready",
                                unsafe_allow_html=True,
                            )
                            progress.progress(count_done / total_types)

                        try:
                            generate_questions_parallel(
                                chunks,
                                q_config,
                                progress_callback=_on_type_done,
                            )
                        except Exception as e:
                            st.error(f"Generation error: {e}")
                            generation_failed = True

                        if not generation_failed:
                            # Merge results preserving the user's selected order
                            for cfg in q_config:
                                qs = type_results.get(cfg["type"], [])
                                if not qs:
                                    st.warning(
                                        f"⚠️ Could not generate any **{cfg['type']}** questions "
                                        "— skipping this type."
                                    )
                                all_questions.extend(qs)

                        status_header.empty()
                        progress.empty()
    
                        if generation_failed:
                            st.session_state.is_processing = False
                            st.stop()
    
                        if not all_questions:
                            st.session_state.is_processing = False
                            st.error("Could not generate questions. The document may be too short or lack sufficient text content.")
                            st.stop()
    
                        st.session_state.questions      = all_questions
                        st.session_state.q_config       = q_config
                        st.session_state.total_marks    = sum(c["count"] * c["marks"] for c in q_config)
                        st.session_state.uploaded_names = names
                        st.session_state.current_q      = 0
                        st.session_state.answers        = {}
                        st.session_state.evaluations    = []
                        st.session_state.extracted_text = context
                        st.session_state.session_id     = None
                        st.session_state.stage          = "quiz"
                        st.session_state.is_processing  = False
                        _sync_draft()
                        st.rerun()
                else:
                    st.button("Generate Assessment →", type="primary", use_container_width=True, disabled=True)
                    upload_msg = "Upload a file or paste a video URL." if not files_ok else ""
                    types_msg  = "Select at least one question type." if not types_ok else ""
                    hint = " · ".join(filter(None, [upload_msg, types_msg]))
                    if hint:
                        st.caption(f"To continue: {hint}")
    
    # ══════════════════════════════════════════════════════════════════════════════
    # QUIZ PAGE
    # ══════════════════════════════════════════════════════════════════════════════
    elif st.session_state.stage == "quiz":
        questions = st.session_state.questions
        current   = st.session_state.current_q
        total     = len(questions)
    
        col_prog, col_nav = st.columns([4, 1])
        with col_prog:
            st.progress(current / total)
            st.caption(f"Question {current + 1} of {total}")
        with col_nav:
            _has_answers = bool(st.session_state.answers)
            _back_label = "Back to Setup"
            if st.button(_back_label, disabled=st.session_state.is_processing):
                if _has_answers:
                    st.session_state._confirm_back = True
                else:
                    st.session_state.stage = "config"
                    clear_draft()
                    st.rerun()
    
        # Warn before discarding answers
        if st.session_state.get("_confirm_back"):
            st.warning("You have answered some questions. Going back to Setup will discard your progress.")
            cb1, cb2 = st.columns(2)
            if cb1.button("Yes, go back", key="_confirm_back_yes"):
                st.session_state._confirm_back = False
                st.session_state.stage = "config"
                clear_draft()
                st.rerun()
            if cb2.button("Cancel", key="_confirm_back_no"):
                st.session_state._confirm_back = False
                st.rerun()
    
        st.markdown("---")
    
        q     = questions[current]
        qtype = q.get("type", "MCQ")
        marks = q.get("marks", 1)
    
        st.markdown(
            f'<span class="type-tag">{qtype}</span>'
            f'<span class="marks-tag">{marks} mark{"s" if marks > 1 else ""}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(f"### {q['question']}")
    
        answer_key = f"ans_{current}"
    
        if qtype == "MCQ":
            opts    = q.get("options", {})
            choices = [f"{k}.  {v}" for k, v in opts.items()]
            choice  = st.radio("Select your answer:", choices, index=None, key=answer_key)
            user_answer = choice.split(".")[0].strip() if choice else None
    
        elif qtype == "True / False":
            user_answer = st.radio("Select your answer:", ["True", "False"], index=None, key=answer_key)
    
        elif qtype == "Fill in the Blanks":
            st.caption("Type the missing word or phrase.")
            user_answer = st.text_input("Your answer:", key=answer_key, placeholder="Fill in the blank...")
    
        elif qtype == "Short Answer":
            st.caption("Write a concise 2–3 sentence answer.")
            user_answer = st.text_area("Your answer:", key=answer_key, height=120,
                                       placeholder="Write your short answer here...")
    
        elif qtype == "Long Answer":
            st.caption("Write a detailed, well-structured answer.")
            user_answer = st.text_area("Your answer:", key=answer_key, height=220,
                                       placeholder="Write your detailed answer here...")
    
        elif qtype == "Match the Following":
            pairs = q.get("pairs", {})
            st.caption("Match each item on the left with the correct item on the right.")
            match_answers = {}
            right_options = list(pairs.values())
    
            for left_item in pairs:
                c_left, c_right = st.columns([1, 1])
                with c_left:
                    st.markdown(f"<div style='margin-top:10px;font-weight:600;font-size:14px;color:#1E293B;'>{left_item} →</div>", unsafe_allow_html=True)
                with c_right:
                    match_answers[left_item] = st.selectbox(
                        f"Match {left_item}",
                        options=["-- select --"] + right_options,
                        label_visibility="collapsed",
                        key=f"match_{current}_{left_item}",
                    )
            user_answer = json.dumps(match_answers)
    
        elif qtype == "Assertion & Reason":
            st.markdown("**Assertion (A):** " + q.get("assertion", ""))
            st.markdown("**Reason (R):** "    + q.get("reason", ""))
            ar_choices = [
                "A. Both A and R are true, and R is the correct explanation of A",
                "B. Both A and R are true, but R is NOT the correct explanation of A",
                "C. A is true but R is false",
                "D. A is false but R is true",
            ]
            choice = st.radio("Select the correct option:", ar_choices, index=None, key=answer_key)
            user_answer = choice[0] if choice else None
    
        elif qtype == "One Word Answer":
            user_answer = st.text_input("Your answer (one word or short phrase):", key=answer_key, placeholder="...")
    
        else:
            user_answer = st.text_input("Your answer:", key=answer_key)
    
        st.markdown("---")
    
        col_prev, col_space, col_next = st.columns([1, 4, 1])
        with col_prev:
            if current > 0 and st.button("← Prev", disabled=st.session_state.is_processing):
                if user_answer and str(user_answer).strip() not in ("", "-- select --"):
                    st.session_state.answers[current] = user_answer
                st.session_state.current_q -= 1
                _sync_draft()
                st.rerun()
    
        with col_next:
            is_last   = (current == total - 1)
            btn_label = "Submit Quiz →" if is_last else "Next →"
            if st.button(btn_label, type="primary", disabled=st.session_state.is_processing):
                if user_answer and str(user_answer).strip() not in ("", "-- select --"):
                    st.session_state.answers[current] = user_answer
                
                _sync_draft()
                
                if is_last:
                    for i in range(total):
                        if i not in st.session_state.answers:
                            st.session_state.answers[i] = "[No answer provided]"
                    st.session_state.stage = "evaluating"
                    _sync_draft()
                    st.rerun()
                else:
                    st.session_state.current_q += 1
                    st.rerun()
    
        # Question navigator
        st.markdown("---")
        with st.expander("🧭 Question Navigator", expanded=False):
            cols_nav = st.columns(min(total, 8))
            for i in range(total):
                with cols_nav[i % 8]:
                    answered = i in st.session_state.answers
                    label    = f"{'✓' if answered else str(i+1)}"
                    if st.button(label, key=f"nav_{i}", use_container_width=True, disabled=st.session_state.is_processing, help=f"Q{i+1}: {questions[i]['type']}"):
                        if user_answer and str(user_answer).strip() not in ("", "-- select --"):
                            st.session_state.answers[current] = user_answer
                        st.session_state.current_q = i
                        _sync_draft()
                        st.rerun()
    
    
    # ══════════════════════════════════════════════════════════════════════════════
    # EVALUATING PAGE
    # ══════════════════════════════════════════════════════════════════════════════
    elif st.session_state.stage == "evaluating":
        st.markdown('<div class="main-header">Evaluating Answers</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-header">The rubric engine is scoring each answer. Long-answer grading may take 30–60 seconds.</div>', unsafe_allow_html=True)
    
        progress_bar = st.progress(0)
        status_text  = st.empty()
    
        questions    = st.session_state.questions
        answers_dict = st.session_state.answers
        evaluations  = []
    
        for i, q in enumerate(questions):
            status_text.text(f"Evaluating Q{i+1}/{len(questions)}: {q['type']}...")
            student_ans = answers_dict.get(i, "[No answer provided]")
            try:
                ev = evaluate_all_answers(q, student_ans, st.session_state.extracted_text)
            except Exception as e:
                ev = {
                    "score": 0, "is_correct": False, "max_score": q.get("marks", 1),
                    "feedback": f"Evaluation error: {e}", "hint": "",
                    "criteria_scores": {}, "strengths": "", "weaknesses": str(e), "improvements": "",
                }
            evaluations.append(ev)
            progress_bar.progress((i + 1) / len(questions))
    
        # Save to DB
        try:
            sid = save_session(
                questions, answers_dict, evaluations,
                files_used=st.session_state.uploaded_names,
            )
            st.session_state.session_id = sid
        except Exception as e:
            from src.utils.logger import get_logger
            get_logger("app").warning(f"DB save failed: {e}")
    
        clear_draft()
        st.session_state.evaluations = evaluations
        st.session_state.stage       = "results"
        st.rerun()
    
    
    # ══════════════════════════════════════════════════════════════════════════════
    # RESULTS PAGE
    # ══════════════════════════════════════════════════════════════════════════════
    elif st.session_state.stage == "results":
        questions    = st.session_state.questions
        answers_dict = st.session_state.answers
        evaluations  = st.session_state.evaluations
    
        earned      = sum(e.get("score", 0) for e in evaluations)
        max_marks   = sum(q.get("marks", 1) for q in questions)
        pct         = round((earned / max_marks) * 100, 1) if max_marks else 0.0
        correct_cnt = sum(1 for e in evaluations if e.get("is_correct"))
        grade       = "S" if pct>=90 else "A" if pct>=80 else "B" if pct>=70 else "C" if pct>=50 else "D"
        grade_color = GRADE_COLOR[grade]
        grade_cls   = f"grade-{grade.lower()}"
    
        # ── Top back navigation row
        _res_b1, _res_b2, _res_spacer = st.columns([1, 1, 4])
        with _res_b1:
            if st.button("<- Back to Quiz", disabled=st.session_state.is_processing, use_container_width=True):
                st.session_state.answers     = {}
                st.session_state.evaluations = []
                st.session_state.current_q   = 0
                st.session_state.stage       = "quiz"
                _sync_draft()
                st.rerun()
        with _res_b2:
            if st.button("<- Back to Setup", disabled=st.session_state.is_processing, use_container_width=True):
                for key in ["questions","answers","evaluations","stage","current_q",
                            "q_config","uploaded_names","extracted_text","session_id","_confirm_back"]:
                    st.session_state.pop(key, None)
                st.session_state.stage = "config"
                clear_draft()
                st.rerun()
        st.markdown("---")
    
        st.markdown('<div class="main-header">Results</div>', unsafe_allow_html=True)
        st.markdown(
            f'<span class="grade-badge {grade_cls}">{grade}</span> '
            f'<span style="color:{grade_color};font-size:1.1rem;font-weight:600"> {GRADE_MSGS[grade]}</span>',
            unsafe_allow_html=True,
        )
        st.markdown("---")
    
        # ── Metric cards ──────────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        pct_color = "#16A34A" if pct >= 70 else "#D97706" if pct >= 50 else "#DC2626"
    
        c1.markdown(
            f'<div class="metric-card"><div class="metric-num">{earned}'
            f'<span style="font-size:16px;color:#94A3B8">/{max_marks}</span></div>'
            f'<div class="metric-lbl">Total Marks</div></div>', unsafe_allow_html=True)
        c2.markdown(
            f'<div class="metric-card"><div class="metric-num" style="color:{pct_color}">{pct}%</div>'
            f'<div class="metric-lbl">Percentage</div></div>', unsafe_allow_html=True)
        c3.markdown(
            f'<div class="metric-card"><div class="metric-num">{correct_cnt}'
            f'<span style="font-size:16px;color:#94A3B8">/{len(questions)}</span></div>'
            f'<div class="metric-lbl">Correct Answers</div></div>', unsafe_allow_html=True)
        c4.markdown(
            f'<div class="metric-card"><div class="metric-num" style="color:{grade_color}">{grade}</div>'
            f'<div class="metric-lbl">Grade</div></div>', unsafe_allow_html=True)
    
        st.markdown("---")
    
        # ── Per-type breakdown ────────────────────────────────────────────────────
        st.markdown("### Performance by question type")
        type_stats: dict[str, dict] = {}
        for i, q in enumerate(questions):
            t  = q.get("type", "Unknown")
            ev = evaluations[i] if i < len(evaluations) else {}
            if t not in type_stats:
                type_stats[t] = {"earned": 0, "max": 0, "count": 0, "criteria": {}}
            type_stats[t]["earned"] += ev.get("score", 0)
            type_stats[t]["max"]    += q.get("marks", 1)
            type_stats[t]["count"]  += 1
            for crit, cscore in ev.get("criteria_scores", {}).items():
                type_stats[t]["criteria"][crit] = type_stats[t]["criteria"].get(crit, 0) + cscore
    
        if type_stats:
            tcols = st.columns(min(len(type_stats), 4))
            for idx, (t, s) in enumerate(type_stats.items()):
                tp = round((s["earned"] / s["max"]) * 100) if s["max"] else 0
                tcols[idx % 4].metric(t[:14], f"{s['earned']}/{s['max']}", f"{tp}%")
    
        st.markdown("---")
    
        # ── Strengths & Weaknesses panel ─────────────────────────────────────────
        strengths_list  = []
        weaknesses_list = []
    
        for t, s in type_stats.items():
            if s["max"] == 0:
                continue
            tp = round((s["earned"] / s["max"]) * 100)
            if tp >= 80:
                strengths_list.append(f"Strong in {t} ({tp}%)")
            elif tp < 50:
                weaknesses_list.append(f"Weak in {t} ({tp}%)")
    
            # Criterion-level for LLM types
            if t in ("Short Answer", "Long Answer"):
                rubric = get_rubric(t)
                for crit_def in rubric["criteria"]:
                    cname  = crit_def["name"]
                    weight = crit_def["weight"]
                    total  = s["criteria"].get(cname, 0)
                    avg    = total / s["count"] if s["count"] else 0
                    max_c  = s["max"] / s["count"] * weight if s["count"] else 1
                    if avg < max_c * 0.4:
                        weaknesses_list.append(f"Weak in {cname.replace('_',' ').title()} ({t})")
                    elif avg >= max_c * 0.8:
                        strengths_list.append(f"Strong in {cname.replace('_',' ').title()} ({t})")
    
        has_insights = strengths_list or weaknesses_list
        if has_insights:
            st.markdown("### 📊 Performance Insights")
            col_s, col_w = st.columns(2)
            with col_s:
                st.markdown("**💪 Strengths**")
                if strengths_list:
                    chips = "".join(
                        f'<span class="insight-chip chip-strength">✓ {s}</span>'
                        for s in strengths_list
                    )
                    st.markdown(chips, unsafe_allow_html=True)
                else:
                    st.caption("No standout strengths this session.")
            with col_w:
                st.markdown("**⚠️ Areas to Improve**")
                if weaknesses_list:
                    chips = "".join(
                        f'<span class="insight-chip chip-weakness">✗ {w}</span>'
                        for w in weaknesses_list
                    )
                    st.markdown(chips, unsafe_allow_html=True)
                else:
                    st.caption("No significant weaknesses detected. Well done!")
            st.markdown("---")
    
        # ── Per-question breakdown ────────────────────────────────────────────────
        st.markdown("### Question-by-question breakdown")
    
        for i, q in enumerate(questions):
            ev        = evaluations[i] if i < len(evaluations) else {}
            score     = ev.get("score", 0)
            max_s     = q.get("marks", 1)
            is_corr   = ev.get("is_correct", False)
            partial   = (not is_corr) and score > 0
            status_cls = "correct" if is_corr else ("partial" if partial else "wrong")
            icon       = "[Correct]" if is_corr else ("[Partial]" if partial else "[Incorrect]")
            qtype      = q.get("type", "MCQ")
    
            with st.expander(
                f"{icon}  Q{i+1} [{qtype}] — {score}/{max_s} marks — {q['question'][:65]}...",
                expanded=not is_corr,
            ):
                col_q, col_s = st.columns([3, 1])
    
                with col_q:
                    st.markdown(f"**Question:** {q['question']}")
    
                    # ── Type-specific answer display ──────────────────────────────
                    if qtype == "MCQ":
                        opts = q.get("options", {})
                        for letter, text in opts.items():
                            sa = answers_dict.get(i, "")
                            ca = q.get("correct_answer", "")
                            if letter == ca:
                                st.markdown(f"[Correct] **{letter}. {text}** ← correct")
                            elif letter == (sa[0].upper() if sa else ""):
                                st.markdown(f"[Incorrect] ~~{letter}. {text}~~ ← your answer")
                            else:
                                st.markdown(f"- {letter}. {text}")
    
                    elif qtype == "Match the Following":
                        pairs = q.get("pairs", {})
                        st.markdown("**Correct matches:**")
                        for left, right in pairs.items():
                            st.markdown(f"- {left} → **{right}**")
                        raw_ans = answers_dict.get(i, "{}")
                        try:
                            student_pairs = json.loads(raw_ans) if isinstance(raw_ans, str) else raw_ans
                            st.markdown("**Your matches:**")
                            for left, right in student_pairs.items():
                                correct_right = pairs.get(left, "")
                                icon_p = "✓" if right.lower().strip() == correct_right.lower().strip() else "✗"
                                st.markdown(f"- {icon_p} {left} → {right}")
                        except Exception:
                            st.markdown(f"**Your answer:** {raw_ans}")
    
                    elif qtype == "Assertion & Reason":
                        st.markdown(f"**Assertion:** {q.get('assertion', '')}")
                        st.markdown(f"**Reason:** {q.get('reason', '')}")
                        st.markdown(f"**Correct option:** {q.get('correct_answer', '')}")
                        st.markdown(f"**Your answer:** {answers_dict.get(i, '[none]')}")
    
                    else:
                        st.markdown(f"**Your answer:** {answers_dict.get(i, '[none]')}")
                        model_ans = q.get("correct_answer", q.get("answer", ""))
                        st.markdown(f"**Model answer:** {model_ans}")
    
                    # ── Feedback & narrative ──────────────────────────────────────
                    if ev.get("feedback"):
                        st.info(ev["feedback"])
                    if ev.get("strengths"):
                        st.success(f"{ev['strengths']}")
                    if ev.get("weaknesses"):
                        st.warning(f"{ev['weaknesses']}")
                    if ev.get("improvements"):
                        st.caption(f"{ev['improvements']}")
                    if ev.get("hint"):
                        st.caption(f"{ev['hint']}")
                    if q.get("explanation"):
                        st.caption(f"{q['explanation']}")
    
                with col_s:
                    # Score circle
                    score_pct = round((score / max_s) * 100) if max_s else 0
                    s_color   = "#16A34A" if score_pct == 100 else "#D97706" if score_pct >= 50 else "#DC2626"
                    s_bg      = "#DCFCE7" if score_pct == 100 else "#FEF3C7" if score_pct >= 50 else "#FEE2E2"
                    st.markdown(
                        f'<div style="text-align:center;padding:16px;background:{s_bg};border-radius:8px;'
                        f'border:1px solid #E2E8F0">'
                        f'<div style="font-size:24px;font-weight:700;color:{s_color}">'
                        f'{score}/{max_s}</div>'
                        f'<div style="font-size:11px;color:#64748B;margin-top:4px">{score_pct}%</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    
                    # ── Rubric criterion breakdown ────────────────────────────────
                    criteria_scores = ev.get("criteria_scores", {})
                    if criteria_scores:
                        st.markdown(
                            '<div style="margin-top:12px;font-size:11px;color:#64748B;'
                            'text-transform:uppercase;letter-spacing:0.08em;font-weight:600">Rubric Breakdown</div>',
                            unsafe_allow_html=True,
                        )
                        rubric = get_rubric(qtype)
                        crit_defs = {c["name"]: c["weight"] for c in rubric["criteria"]}
    
                        for crit, cscore in criteria_scores.items():
                            weight   = crit_defs.get(crit, 0.25)
                            crit_max = max(1, round(max_s * weight))
                            fill_pct = min(100, round((cscore / crit_max) * 100)) if crit_max else 0
                            bar_color = ("#4ade80" if fill_pct >= 75
                                         else "#fbbf24" if fill_pct >= 40 else "#f87171")
                            crit_label = crit.replace("_", " ").title()
                            st.markdown(
                                f'<div class="criterion-row">'
                                f'<span class="criterion-name">{crit_label}</span>'
                                f'<div class="criterion-bar-bg">'
                                f'<div class="criterion-bar-fill" style="width:{fill_pct}%;'
                                f'background:{bar_color}"></div>'
                                f'</div>'
                                f'<span class="criterion-score">{cscore}/{crit_max}</span>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )
    
        st.markdown("---")
        st.caption("Grade scale: S ≥ 90%  ·  A ≥ 80%  ·  B ≥ 70%  ·  C ≥ 50%  ·  D < 50%")
        st.markdown("---")
    
        # ── Download Section ────────────────────────────────────────────────────────────────────
        st.markdown("### Download Report")
        with st.spinner("Preparing export..."):
            _export_schema = build_export_schema(
                st.session_state.questions,
                st.session_state.answers,
                st.session_state.evaluations,
                session_id=st.session_state.session_id,
            )
            _pdf_bytes  = generate_pdf_report(_export_schema)
            _docx_bytes = generate_docx_report(_export_schema)
    
        dl_ts = datetime.now().strftime("%Y%m%d_%H%M")
        dcol1, dcol2, dcol3 = st.columns(3)
        with dcol1:
            if _pdf_bytes:
                st.download_button(
                    label="Download PDF",
                    data=_pdf_bytes,
                    file_name=f"lumina_report_{dl_ts}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.error("PDF export unavailable. Try DOCX.")
    
        with dcol2:
            if _docx_bytes:
                st.download_button(
                    label="Download DOCX",
                    data=_docx_bytes,
                    file_name=f"lumina_report_{dl_ts}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
            else:
                st.error("DOCX export unavailable.")
    
        with dcol3:
            pass  # reserved for future format (e.g. JSON)
    
        st.markdown("---")
    
        # ── Navigation buttons ────────────────────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("Back to Quiz", use_container_width=True, disabled=st.session_state.is_processing):
                st.session_state.answers     = {}
                st.session_state.evaluations = []
                st.session_state.current_q   = 0
                st.session_state.stage       = "quiz"
                _sync_draft()
                st.rerun()
        with c2:
            if st.button("New Assessment", use_container_width=True, disabled=st.session_state.is_processing):
                for key in ["questions","answers","evaluations","stage","current_q",
                            "q_config","uploaded_names","extracted_text","session_id",
                            "_confirm_back"]:
                    st.session_state.pop(key, None)
                st.session_state.stage = "config"
                clear_draft()
                st.rerun()
        with c3:
            if st.button("Retry Same Assessment", type="primary", use_container_width=True, disabled=st.session_state.is_processing):
                st.session_state.answers     = {}
                st.session_state.evaluations = []
                st.session_state.current_q   = 0
                st.session_state.stage       = "quiz"
                _sync_draft()
                st.rerun()
        with c4:
            if st.button("View History", use_container_width=True, disabled=st.session_state.is_processing):
                st.session_state.nav_target = "history"
                st.rerun()
    
