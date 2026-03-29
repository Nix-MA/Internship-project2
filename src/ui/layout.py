import streamlit as st

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --clr-primary:  #1E293B;
        --clr-accent:   #2563EB;
        --clr-bg:       #F8FAFC;
        --clr-surface:  #FFFFFF;
        --clr-text:     #0F172A;
        --clr-muted:    #64748B;
        --clr-border:   #E2E8F0;
        --clr-success:  #16A34A;
        --clr-warn:     #D97706;
        --clr-error:    #DC2626;
        --shadow-sm:    0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
        --radius:       8px;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
        color: var(--clr-text);
    }

    .stApp { background-color: var(--clr-bg) !important; }

    header[data-testid="stHeader"] {
        background-color: var(--clr-bg) !important;
        border-bottom: 1px solid var(--clr-border);
    }

    [data-testid="stSidebar"] {
        background-color: var(--clr-surface) !important;
        border-right: 1px solid var(--clr-border) !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', sans-serif !important;
        color: var(--clr-primary);
        letter-spacing: -0.01em;
    }

    .main-header { font-size: 28px; font-weight: 700; color: var(--clr-primary); margin-bottom: 4px; letter-spacing: -0.02em; }
    .sub-header { font-size: 14px; color: var(--clr-muted); margin-bottom: 24px; font-weight: 400; }
    .section-label { font-size: 11px; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: var(--clr-muted); margin-bottom: 8px; }

    .metric-card { background: var(--clr-surface); border: 1px solid var(--clr-border); border-radius: var(--radius); padding: 20px 16px; text-align: center; box-shadow: var(--shadow-sm); }
    .metric-num { font-size: 28px; font-weight: 700; color: var(--clr-primary); line-height: 1.1; }
    .metric-lbl { font-size: 12px; color: var(--clr-muted); margin-top: 6px; font-weight: 500; }

    .grade-badge { display: inline-flex; align-items: center; justify-content: center; padding: 4px 14px; border-radius: 4px; font-weight: 700; font-size: 14px; letter-spacing: 0.02em; }
    .grade-s { background:#DCFCE7; color:#16A34A; border:1px solid #BBF7D0; }
    .grade-a { background:#D1FAE5; color:#059669; border:1px solid #A7F3D0; }
    .grade-b { background:#DBEAFE; color:#2563EB; border:1px solid #BFDBFE; }
    .grade-c { background:#FEF3C7; color:#D97706; border:1px solid #FDE68A; }
    .grade-d { background:#FEE2E2; color:#DC2626; border:1px solid #FECACA; }

    .question-block { background: var(--clr-surface); border: 1px solid var(--clr-border); border-radius: var(--radius); padding: 24px; margin-bottom: 12px; box-shadow: var(--shadow-sm); }
    .question-block.correct { border-left: 3px solid #16A34A; }
    .question-block.partial { border-left: 3px solid #D97706; }
    .question-block.wrong   { border-left: 3px solid #DC2626; }

    .type-tag { display: inline-block; padding: 3px 10px; border-radius: 4px; font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; background: #EFF6FF; color: var(--clr-accent); border: 1px solid #BFDBFE; margin-bottom: 12px; }
    .marks-tag { float: right; font-size: 12px; font-weight: 500; color: var(--clr-muted); padding-top: 3px; }

    .criterion-row { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 13px; }
    .criterion-name { width: 140px; color: var(--clr-muted); text-transform: capitalize; font-size: 12px; font-weight: 500; }
    .criterion-bar-bg { flex: 1; height: 5px; background: var(--clr-border); border-radius: 99px; overflow: hidden; }
    .criterion-bar-fill { height: 100%; border-radius: 99px; background: var(--clr-accent); transition: width 0.5s ease; }
    .criterion-score { width: 44px; text-align: right; font-size: 12px; color: var(--clr-primary); font-weight: 600; }

    .insight-chip { display: inline-flex; align-items: center; gap: 5px; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 500; margin: 3px; }
    .chip-strength { background:#DCFCE7; color:#16A34A; border:1px solid #BBF7D0; }
    .chip-weakness { background:#FEE2E2; color:#DC2626; border:1px solid #FECACA; }

    .file-chip { display: inline-flex; align-items: center; gap: 6px; background: #F1F5F9; border: 1px solid var(--clr-border); border-radius: 6px; padding: 6px 12px; font-size: 13px; font-weight: 500; color: var(--clr-primary); margin: 3px; }

    div.stButton > button { border-radius: 6px; font-weight: 600; font-size: 14px; transition: background 0.15s, border-color 0.15s; border: 1px solid var(--clr-border); background: var(--clr-surface); color: var(--clr-primary); }
    div.stButton > button:hover { background: #F1F5F9; border-color: #CBD5E1; }
    div.stButton > button[kind="primary"] { background: var(--clr-accent); border: 1px solid var(--clr-accent); color: #FFFFFF; }
    div.stButton > button[kind="primary"]:hover { background: #1D4ED8; border-color: #1D4ED8; box-shadow: 0 2px 8px rgba(37,99,235,0.25); }
    div.stButton > button:disabled { opacity: 0.45; }

    .stProgress > div > div > div > div { background: var(--clr-accent); border-radius: 99px; }
    [data-testid="stExpander"] { border: 1px solid var(--clr-border) !important; border-radius: var(--radius) !important; background: var(--clr-surface) !important; }
    </style>
    """, unsafe_allow_html=True)

def setup_page():
    st.set_page_config(
        page_title="Lumina Assessment",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()

def render_sidebar():
    with st.sidebar:
        st.markdown("### Lumina Assessment")
        st.markdown("---")
        _nav_default = 1 if st.session_state.get("nav_target") == "history" else 0
        if st.session_state.get("nav_target") == "history":
            st.session_state.nav_target = None
        nav = st.radio("", ["New Evaluation", "History"],
                       index=_nav_default, label_visibility="collapsed", key="sidebar_nav")
        st.markdown("---")
        st.markdown(
            "<div style='font-size:12px;color:#64748B;font-weight:500;'>"
            "Powered by Lumina Engine<br>LLaMA Evaluation</div>",
            unsafe_allow_html=True,
        )
    return nav
