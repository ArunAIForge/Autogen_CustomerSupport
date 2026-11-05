"""Start the local FastAPI backend and Streamlit dashboard together."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:8501"


def _port_is_available(port: int) -> bool:
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) != 0


def _backend_is_healthy() -> bool:
    try:
        with urlopen(f"{BACKEND_URL}/health", timeout=2) as response:
            data = json.loads(response.read())
        return response.status == 200 and data.get("status") == "healthy"
    except (OSError, URLError, ValueError):
        return False


def _frontend_is_healthy() -> bool:
    try:
        with urlopen(f"{FRONTEND_URL}/_stcore/health", timeout=2) as response:
            return response.status == 200 and response.read().strip() == b"ok"
    except (OSError, URLError):
        return False


def _wait_for_backend(process: subprocess.Popen, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _backend_is_healthy():
            return
        if process.poll() is not None:
            raise RuntimeError("The FastAPI backend exited before becoming healthy.")
        time.sleep(0.25)
    raise TimeoutError(f"The FastAPI backend did not become healthy at {BACKEND_URL}.")


def main() -> int:
    if not _port_is_available(8501):
        if _frontend_is_healthy() and _backend_is_healthy():
            print(f"ClothesSpot is already available at {FRONTEND_URL}.")
            return 0
        if _frontend_is_healthy():
            print(
                f"The dashboard is already running at {FRONTEND_URL}, "
                "but its API is unavailable. Start the backend with `python run_backend.py`."
            )
        else:
            print("Port 8501 is already in use by another application.")
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["BACKEND_BASE_URL"] = BACKEND_URL
    backend_process = None
    frontend_process = None

    try:
        if not _backend_is_healthy():
            backend_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "backend.app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
                env=env,
            )
            _wait_for_backend(backend_process)
        elif not _port_is_available(8000):
            print(f"Reusing the healthy API at {BACKEND_URL}.")

        frontend_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.address",
                "127.0.0.1",
                "--server.port",
                "8501",
                "--server.headless",
                "true",
            ],
            cwd=ROOT,
            env=env,
        )
        print(f"ClothesSpot is starting at {FRONTEND_URL}. Press Ctrl+C to stop.")
        return frontend_process.wait()
    except (OSError, RuntimeError, TimeoutError) as error:
        print(f"Could not start ClothesSpot: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 0
    finally:
        for process in (frontend_process, backend_process):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
