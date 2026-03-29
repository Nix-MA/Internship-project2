import streamlit as st

def render_header(title: str, subtitle: str = ""):
    st.markdown(f'<div class="main-header">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="sub-header">{subtitle}</div>', unsafe_allow_html=True)

def render_metric_card(label: str, value: str):
    st.markdown(
        f'<div class="metric-card"><div class="metric-num">{value}</div><div class="metric-lbl">{label}</div></div>',
        unsafe_allow_html=True
    )

def render_file_chip(name: str, ext: str, size_kb: float):
    return f'<div class="file-chip">📄 {name[:28]} <span style="color:#64748B;font-size:12px">{ext} · {size_kb} KB</span></div>'

def render_grade_badge(grade: str):
    grade_class = grade.lower() if grade else "d"
    return f'<span class="grade-badge grade-{grade_class}">{grade}</span>'

def render_type_tag(qtype: str):
    return f'<span class="type-tag">{qtype}</span>'

def render_marks_tag(marks: int):
    return f'<span class="marks-tag">{marks} mark{"s" if marks > 1 else ""}</span>'
