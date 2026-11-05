"""Tests for 5-point escalation policy and logging audit verification."""

try:
    import pytest
except ImportError:
    pytest = None
import bootstrap  # noqa: F401
from backend.app.agents.team import AutoGenSupportTeam
from backend.app.services.ticket_logger import get_ticket_logger


def test_escalation_point_1_high_urgency():
    team = AutoGenSupportTeam()
    res = team.run_complaint_workflow(
        "My order is 10 days late and nobody replies to my emails! This is urgent."
    )
    assert res.status == "Escalated"
    assert "High urgency" in res.escalation_reason


def test_escalation_point_2_angry_customer():
    team = AutoGenSupportTeam()
    res = team.run_complaint_workflow(
        "This service is completely unacceptable, furious with this delivery failure!"
    )
    assert res.status == "Escalated"
    assert "Angry customer" in res.escalation_reason


def test_escalation_point_3_no_matching_document():
    team = AutoGenSupportTeam()
    res = team.run_complaint_workflow(
        "Do you sell custom company spacesuits for a private astronaut mission?"
    )
    assert res.status == "Escalated"
    assert "No matching document" in res.escalation_reason or "Low confidence" in res.escalation_reason


def test_escalation_point_4_legal_threat_and_payment_dispute():
    team = AutoGenSupportTeam()
    res = team.run_complaint_workflow(
        "You charged my card three times! Fix this now or I'm contacting my bank and a lawyer."
    )
    assert res.status == "Escalated"
    assert "Legal threat" in res.escalation_reason
    assert "Payment dispute" in res.escalation_reason


def test_escalation_point_5_low_confidence_or_b2b_custom():
    team = AutoGenSupportTeam()
    res = team.run_complaint_workflow(
        "Do you sell gift cards for a company of 500 employees with custom branding?"
    )
    assert res.status == "Escalated"
    assert "No matching document" in res.escalation_reason or "Low confidence" in res.escalation_reason


def test_ticket_logging_columns():
    logger = get_ticket_logger()
    tickets = logger.get_all_tickets()
    assert len(tickets) > 0
    
    last = tickets[-1]
    required_keys = [
        "ticket_id", "timestamp", "customer_name", "order_id",
        "complaint", "category", "urgency", "sentiment",
        "kb_sources", "response", "status", "escalation_reason", "confidence"
    ]
    for key in required_keys:
        assert key in last, f"Missing key in CSV log: {key}"
    assert len(last["agent_steps"]) == 4
    assert [step["agent_name"] for step in last["agent_steps"]] == [
        "CustomerQueryAgent",
        "KnowledgeBaseAgent",
        "ResolutionAgent",
        "LogAgent",
    ]
