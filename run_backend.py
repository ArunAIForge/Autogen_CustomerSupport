"""Run backend FastAPI server."""

import sys
from pathlib import Path
import uvicorn

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import bootstrap  # noqa: F401
from backend.app.config import settings

if __name__ == "__main__":
    print("Starting ClothesSpot API on http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)...")
    uvicorn.run(
        "backend.app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.APP_ENV.lower() == "development",
        log_level=settings.LOG_LEVEL.lower(),
    )
