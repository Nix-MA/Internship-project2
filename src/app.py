"""
Quiz-Doc-AI v2 — Production Streamlit App Entrypoint
Run: streamlit run src/app.py
"""
import sys
import os
from pathlib import Path

# Add project root to sys.path securely
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from src.ui.layout import setup_page
from src.storage.init_db import initialize_database
from src.utils.logger import get_logger

logger = get_logger("app")

# Ensure DB is created if missing
initialize_database()

# Set up page configurations and styles
setup_page()

# Load the monolithic routing pages logic
# (To preserve the exact user flow without complex state loss)
from src.ui.pages import run_ui

try:
    run_ui()
except Exception as e:
    logger.error(f"Application crash: {e}", exc_info=True)
    st.error("An unexpected error occurred. Please contact an administrator or check the logs.")
