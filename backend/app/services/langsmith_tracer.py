"""LangSmith Tracing and Observability Client for ClothesSpot.

Provides non-blocking telemetry and trace logging to LangSmith.
If the langsmith package is not installed or LANGCHAIN_TRACING_V2 is false,
tracing operates as a clean no-op without degrading latency.
"""

from functools import wraps
import os
import time
from typing import Callable, Optional

# Optional native LangSmith client
try:
    from langsmith import Client, traceable
    LANGSMITH_NATIVE = True
except ImportError:
    Client = None
    LANGSMITH_NATIVE = False


def is_langsmith_enabled() -> bool:
    """Check if LangSmith tracing is active via environment variables."""
    tracing_flag = os.getenv("LANGCHAIN_TRACING_V2", "false").lower()
    has_key = bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
    return tracing_flag in ("true", "1", "yes") and has_key


def trace_agent_run(run_type: str = "chain", name: Optional[str] = None):
    """Decorator to trace agent execution steps and tool invocations to LangSmith."""
    def decorator(func: Callable):
        if LANGSMITH_NATIVE and is_langsmith_enabled():
            return traceable(run_type=run_type, name=name or func.__name__)(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            error = None
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error = str(e)
                raise
            finally:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                if is_langsmith_enabled():
                    print(f"[LangSmith Telemetry] Run: {name or func.__name__} | Type: {run_type} | Duration: {duration_ms}ms | Error: {error}")
        return wrapper
    return decorator