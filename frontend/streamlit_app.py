"""ClothesSpot Streamlit frontend for the support dashboard."""

import json
import os
from pathlib import Path
import re
import sys

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from backend.app.config import settings


def run_standalone_fallback():
    """Fallback runner if user executes 'python app.py' directly without streamlit installed."""
    import uvicorn
    print("\n[ClothesSpot] Launching interactive web interface via FastAPI on http://127.0.0.1:8000 ...")
    uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8000, reload=False)


if not STREAMLIT_AVAILABLE:
    if __name__ == "__main__" or "app" in sys.modules:
        run_standalone_fallback()
else:
    st.set_page_config(
        page_title="ClothesSpot – AI Customer Support Automation Desk",
        page_icon="👗",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Keep the HTML dashboard full-width inside the Streamlit shell.
    st.markdown(
        """
        <style>
            #MainMenu {visibility: hidden !important;}
            footer {visibility: hidden !important;}
            header {visibility: hidden !important;}
            [data-testid="stSidebar"] {display: none !important;}
            [data-testid="stHeader"] {display: none !important;}
            [data-testid="stToolbar"] {display: none !important;}
            .block-container {
                padding: 0 !important;
                margin: 0 !important;
                max-width: 100% !important;
            }
            div[data-testid="stAppViewBlockContainer"] {
                padding: 0 !important;
            }
            body, .stApp {
                background: #EBEEF4 !important;
                margin: 0 !important;
                padding: 0 !important;
                overflow: hidden !important;
            }
            iframe {
                border: none !important;
                width: 100% !important;
                height: 98vh !important;
                display: block !important;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Read the template HTML
    html_file = Path(__file__).resolve().parent / "index.html"
    if html_file.is_file():
        with open(html_file, "r", encoding="utf-8") as f:
            template_html = f.read()
    else:
        raise FileNotFoundError(f"Dashboard template not found: {html_file}")

    css_file = html_file.with_name("dashboard.css")
    js_file = html_file.with_name("dashboard.js")
    css = css_file.read_text(encoding="utf-8")
    javascript = js_file.read_text(encoding="utf-8")
    template_html = template_html.replace(
        '<link rel="stylesheet" href="/static/dashboard.css">',
        f"<style>\n{css}\n</style>",
        1,
    )
    api_base_url = json.dumps(settings.BACKEND_BASE_URL.rstrip("/"))
    javascript = re.sub(
        r'const API_BASE_URL = "";',
        f"const API_BASE_URL = {api_base_url};",
        javascript,
        count=1,
    )
    template_html = template_html.replace(
        '<script src="/static/dashboard.js"></script>',
        f"<script>\n{javascript}\n</script>",
        1,
    )
    st.iframe(
        template_html,
        height=940,
        alt="ClothesSpot support dashboard",
    )
