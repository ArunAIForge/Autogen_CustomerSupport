"""ClothesSpot FastAPI Application Backend.

Production-grade multi-agent support automation desk backend.
Provides endpoints for complaint processing, knowledge base retrieval,
audit ticket logging, analytics, and local benchmark evaluation.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import settings
from backend.app.models.schemas import (
    AnalyticsSummary,
    ComplaintRequest,
    ProcessedComplaintResponse,
)
from backend.app.services.orchestrator import process_customer_complaint
from backend.app.services.ticket_logger import get_ticket_logger
from backend.app.retrieval.kb_manager import get_kb_manager
from backend.app.guardrails.input_guardrails import InputGuardrails
from backend.app.evaluation.benchmark_evaluator import BenchmarkEvaluator


app = FastAPI(
    title=f"{settings.APP_NAME} AI Customer Support Automation Desk",
    description="Customer support workflow with policy retrieval, escalation, and ticket logging.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ticket_logger = get_ticket_logger()
kb_manager = get_kb_manager()
input_guardrails = InputGuardrails()
frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount(
    "/static",
    StaticFiles(directory=str(frontend_dir)),
    name="frontend",
)


@app.get("/health", tags=["System"])
def health_check() -> Dict[str, Any]:
    """System health check and component status."""
    return {
        "status": "healthy",
        "app": f"{settings.APP_NAME} AI Customer Automation",
        "timestamp": datetime.now().isoformat(),
        "knowledge_base_indexed": kb_manager.is_indexed,
        "indexed_chunks": len(kb_manager.chunks),
        "log_file_ready": ticket_logger.log_path.exists(),
    }


@app.post("/api/process-complaint", response_model=ProcessedComplaintResponse, tags=["Support Desk"])
def api_process_complaint(request: ComplaintRequest) -> ProcessedComplaintResponse:
    """Process an incoming complaint through the support workflow."""
    return process_customer_complaint(request)


@app.get("/api/tickets", tags=["Audit Logging"])
def api_get_tickets() -> Dict[str, Any]:
    """Retrieve all tickets logged in tickets.csv."""
    records = ticket_logger.get_all_tickets()
    return {
        "total": len(records),
        "tickets": records,
    }


@app.get("/api/tickets/download", tags=["Audit Logging"])
def api_download_tickets_csv() -> FileResponse:
    """Download the raw tickets.csv audit log file."""
    if not ticket_logger.log_path.exists():
        raise HTTPException(status_code=404, detail="Log file tickets.csv does not exist yet.")
    return FileResponse(
        path=str(ticket_logger.log_path),
        filename="tickets.csv",
        media_type="text/csv",
    )


@app.get("/api/analytics", response_model=AnalyticsSummary, tags=["Analytics"])
def api_get_analytics() -> AnalyticsSummary:
    """Retrieve operational support desk metrics."""
    data = ticket_logger.get_analytics()
    return AnalyticsSummary(
        total_tickets=data["total_tickets"],
        resolved_count=data["resolved_count"],
        escalated_count=data["escalated_count"],
        escalation_rate=data["escalation_rate"],
        categories=data["categories"],
        urgencies=data["urgencies"],
        sentiments=data["sentiments"],
        avg_confidence=data["avg_confidence"],
    )


@app.get("/api/search", tags=["Knowledge Base"])
def api_search_kb(
    query: str = Query(..., min_length=2, description="Search query string"),
    category: Optional[str] = Query(None, description="Optional category filter"),
    top_k: int = Query(3, ge=1, le=10, description="Number of passages to return"),
) -> Dict[str, Any]:
    """Direct search of company knowledge base using hybrid retrieval."""
    res = kb_manager.search_kb(query=query, category=category, top_k=top_k)
    return res


@app.post("/api/guardrails/validate", tags=["AI Safety"])
def api_validate_guardrails(request: ComplaintRequest) -> Dict[str, Any]:
    """Test input guardrails (prompt injection and PII detection)."""
    val = input_guardrails.validate_input(request.complaint, request.customer_name)
    return val


@app.get("/api/evaluation/run", tags=["Benchmarks"])
def api_run_evaluation() -> Dict[str, Any]:
    """Run local deterministic benchmark scenarios."""
    evaluator = BenchmarkEvaluator()
    report = evaluator.run_eval()
    return report


@app.get("/", response_class=HTMLResponse, tags=["Dashboard UI"])
def root_dashboard() -> HTMLResponse:
    """Serve the support dashboard."""
    html_file = frontend_dir / "index.html"
    if html_file.is_file():
        with open(html_file, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    raise HTTPException(status_code=500, detail="Dashboard template is missing.")
