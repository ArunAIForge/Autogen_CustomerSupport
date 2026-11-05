"""ClothesSpot root Streamlit application entrypoint.

Supports running directly via:
    streamlit run app.py
or:
    python app.py
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bootstrap  # noqa: F401

# Execute frontend Streamlit dashboard
from frontend.streamlit_app import *  # noqa: F401, F403

if __name__ == "__main__":
    try:
        import streamlit
    except ImportError:
        run_standalone_fallback()