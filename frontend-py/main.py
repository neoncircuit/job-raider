"""
Job Raider - Streamlit Dashboard.

Web dashboard for the Job Raider automated job application pipeline.
Provides a visual interface for pipeline management, job browsing,
profile management, and metrics monitoring.

Usage:
    streamlit run main.py --server.port 8501 --server.headless true
"""

import streamlit as st

from src.components.sidebar import render_sidebar
from src.pages.dashboard import render as render_dashboard
from src.pages.pipeline import render as render_pipeline
from src.pages.jobs import render as render_jobs
from src.pages.profile import render as render_profile
from src.pages.resume_analysis import render as render_resume_analysis
from src.pages.metrics import render as render_metrics
from src.pages.settings import render as render_settings
from src.pages.applications import render as render_applications
from src.utils.session_state import get_selected_page

st.set_page_config(
    page_title="Job Raider",
    page_icon="JR",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Global CSS for pill badges, card hover effects, and consistent spacing.
st.markdown(
    """
    <style>
    /* Smooth card hover transitions */
    div[data-testid="stVerticalBlock"] > div[style*="border-radius: 8px"] {
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    /* Tighter spacing between job cards */
    div[data-testid="stVerticalBlock"] > div[style*="border-left: 3px"] {
        margin-bottom: 2px !important;
    }
    /* Pill badge line-height fix */
    span[style*="border-radius:12px"] {
        line-height: 1.6;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

PAGES = {
    "dashboard": ("Dashboard", render_dashboard),
    "pipeline": ("Pipeline", render_pipeline),
    "jobs": ("Jobs", render_jobs),
    "applications": ("Applications", render_applications),
    "profile": ("Profile", render_profile),
    "resume_analysis": ("Resume Analysis", render_resume_analysis),
    "metrics": ("Metrics", render_metrics),
    "settings": ("Settings", render_settings),
}

render_sidebar(PAGES)

page_key = get_selected_page()
if page_key in PAGES:
    _, render_fn = PAGES[page_key]
    render_fn()
else:
    st.error(f"Unknown page: {page_key}")
