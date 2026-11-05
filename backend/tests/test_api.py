"""Integration tests for FastAPI endpoints."""

import csv
from pathlib import Path
import tempfile

import bootstrap  # noqa: F401
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.services.ticket_logger import CSV_COLUMNS, TicketLogger


client = TestClient(app)


def test_api_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["knowledge_base_indexed"] is True


def test_api_dashboard_pages():
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "ClothesSpot" in dashboard.text
    assert 'href="/static/dashboard.css"' in dashboard.text
    assert 'src="/static/dashboard.js"' in dashboard.text
    for page in ("overview", "tickets", "agents", "knowledge", "analytics"):
        assert f'id="page-{page}"' in dashboard.text


    stylesheet = client.get("/static/dashboard.css")
    assert stylesheet.status_code == 200
    assert "--navy: #17243a" in stylesheet.text
    script = client.get("/static/dashboard.js")
    assert script.status_code == 200
    assert 'const API_BASE_URL = "";' in script.text
    for endpoint in ("/api/tickets", "/api/analytics", "/api/search", "/api/process-complaint", "/api/evaluation/run"):
        assert endpoint in script.text

    docs = client.get("/docs")
    assert docs.status_code == 200
    assert "swagger-ui" in docs.text


def test_api_process_complaint_resolved():
    payload = {
        "complaint": "Where is my order? It was supposed to arrive yesterday.",
        "customer_name": "Alex",
        "order_id": "ORD-1001",
    }
    res = client.post("/api/process-complaint", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "Resolved"
    assert data["ticket_id"]


def test_api_process_complaint_escalated():
    payload = {
        "complaint": "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer.",
        "customer_name": "Marcus",
        "order_id": "ORD-5005",
    }
    res = client.post("/api/process-complaint", json=payload)
    assert res.status_code == 200
    assert res.json()["status"] == "Escalated"


def test_api_request_validation():
    res = client.post(
        "/api/process-complaint",
        json={"complaint": "Hi"},
    )
    assert res.status_code == 422


def test_api_tickets_and_download():
    res_list = client.get("/api/tickets")
    assert res_list.status_code == 200
    data = res_list.json()
    assert data["total"] == len(data["tickets"])

    res_download = client.get("/api/tickets/download")
    assert res_download.status_code == 200
    assert "text/csv" in res_download.headers["content-type"]


def test_api_analytics():
    res = client.get("/api/analytics")
    assert res.status_code == 200
    data = res.json()
    assert "total_tickets" in data
    assert 0.0 <= data["avg_confidence"] <= 1.0


def test_api_search():
    res = client.get("/api/search?query=refund%20shoes")
    assert res.status_code == 200
    assert res.json()["found"] is True


def test_api_search_validation():
    res = client.get("/api/search?query=x")
    assert res.status_code == 422


def test_api_frontend_cors():
    res = client.options(
        "/api/tickets",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code == 200
    assert res.headers["access-control-allow-origin"] == "http://localhost:8501"


def test_ticket_log_migrates_legacy_csv():
    with tempfile.TemporaryDirectory() as temp_dir:
        log_path = Path(temp_dir) / "tickets.csv"
        with log_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(CSV_COLUMNS[:-2])
            writer.writerow([
                "TKT-0001", "2026-01-01 12:00:00", "Alex", "ORD-1",
                "A complaint", "Shipping", "Low", "Neutral",
                "shipping_policy.md", "A response", "Resolved", "None",
            ])

        logger = TicketLogger(str(log_path))
        migrated = logger.get_all_tickets()
        assert migrated[0]["confidence"] == ""
        assert migrated[0]["agent_steps"] == []

        logger.log_ticket(
            ticket_id="TKT-0002",
            timestamp="2026-01-01 12:01:00",
            customer_name="Sam",
            order_id="ORD-2",
            complaint="Another complaint",
            category="Account",
            urgency="Low",
            sentiment="Neutral",
            kb_sources="account_and_login.md",
            response="A response",
            status="Resolved",
            escalation_reason="None",
            confidence=0.85,
        )
        assert logger.get_analytics()["avg_confidence"] == 0.85
