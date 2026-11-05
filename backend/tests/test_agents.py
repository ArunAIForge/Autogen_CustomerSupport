"""Unit tests for the four specialized AutoGen support agents."""

import asyncio

try:
    import pytest
except ImportError:
    pytest = None
import bootstrap  # noqa: F401
from backend.app.agents.query_agent import CustomerQueryAgent
from backend.app.agents.knowledge_agent import KnowledgeBaseAgent
from backend.app.agents.resolution_agent import ResolutionAgent
from backend.app.agents.log_agent import LogAgent
from backend.app.agents.team import AutoGenSupportTeam
from autogen_ext.models.openai import OpenAIChatCompletionClient


def test_customer_query_agent_classification():
    agent = CustomerQueryAgent()
    
    # Shipping query
    res1 = agent.process("Where is my order? It was supposed to arrive yesterday.")
    assert res1["category"] == "Shipping"
    assert res1["urgency"] in ["Medium", "High"]
    assert "yesterday" in res1["summary"].lower()

    # Refund query
    res2 = agent.process("I want to return the shoes I bought last week. How do I get a refund?")
    assert res2["category"] == "Refund"
    assert "shoes" in res2["summary"].lower() or "return" in res2["summary"].lower()

    # Password query
    res3 = agent.process("I forgot my password and can't log in.")
    assert res3["category"] == "Account"

    # Angry billing dispute with lawyer threat
    res4 = agent.process("You charged my card three times! Fix this now or I'm contacting my bank and a lawyer.")
    assert res4["category"] == "Billing"
    assert res4["urgency"] == "High"
    assert res4["sentiment"] == "Angry"
    assert "legal_threats" in res4["flags"]
    assert "payment_disputes" in res4["flags"]


def test_knowledge_base_agent_grounding():
    agent = KnowledgeBaseAgent()
    query_data = {"summary": "Where is my order?", "category": "Shipping"}
    res = agent.process(query_data, "Where is my order? It was supposed to arrive yesterday.")
    
    assert res["found"] is True
    assert "shipping_policy.md" in res["sources"]
    assert len(res["passages"]) > 0


def test_resolution_agent_policy_compliance():
    res_agent = ResolutionAgent()
    query_data = {"category": "Refund", "urgency": "Medium", "sentiment": "Neutral", "flags": []}
    kb_data = {
        "found": True,
        "can_resolve": True,
        "sources": ["refund_policy.md"],
        "passages": [{"content": "30 days return window. Unworn shoes with tags."}]
    }
    
    res = res_agent.process(query_data, kb_data, "I want to return the shoes I bought last week.")
    assert res["confidence"] >= 0.90
    assert "refund_policy.md" in res["response"]
    assert "30" in res["response"]


def test_resolution_agent_does_not_invent_policy_when_no_context():
    res = ResolutionAgent().process(
        {"flags": ["fraud"]},
        {"found": False, "can_resolve": False, "sources": [], "passages": []},
        "Someone accessed my account.",
    )
    assert "could not find a relevant answer" in res["response"]
    assert "2 hours" not in res["response"]
    assert res["sources"] == []


def test_autogen_team_configures_all_four_roles_without_network_calls():
    client = OpenAIChatCompletionClient(model="gpt-4o-mini", api_key="sk-test")
    try:
        team = AutoGenSupportTeam(model_client=client)
        agents = [
            team.query_agent.autogen_agent,
            team.kb_agent.autogen_agent,
            team.resolution_agent.autogen_agent,
            team.log_agent.autogen_agent,
        ]
        assert [agent.name for agent in agents] == [
            "CustomerQueryAgent",
            "KnowledgeBaseAgent",
            "ResolutionAgent",
            "LogAgent",
        ]
    finally:
        asyncio.run(client.close())


def test_log_agent_escalation_rules():
    log_agent = LogAgent()
    
    # 1. Normal resolved case
    q1 = {"urgency": "Low", "sentiment": "Neutral", "flags": [], "category": "Account"}
    kb1 = {"found": True, "can_resolve": True, "sources": ["account_and_login.md"]}
    res1 = {"confidence": 0.95, "response": "Click forgot password"}
    status1, reason1 = log_agent.evaluate_escalation(q1, kb1, res1)
    assert status1 == "Resolved"

    # 2. Angry customer + legal threat
    q2 = {"urgency": "High", "sentiment": "Angry", "flags": ["legal_threats", "payment_disputes"], "category": "Billing"}
    kb2 = {"found": True, "can_resolve": True, "sources": ["billing_and_payments.md"]}
    res2 = {"confidence": 0.85, "response": "We will review your duplicate charges"}
    status2, reason2 = log_agent.evaluate_escalation(q2, kb2, res2)
    assert status2 == "Escalated"
    assert "High urgency" in reason2
    assert "Angry customer" in reason2
    assert "Legal threat" in reason2

    # 3. Out of scope / no matching document
    q3 = {"urgency": "Low", "sentiment": "Neutral", "flags": [], "category": "Product"}
    kb3 = {"found": True, "can_resolve": False, "sources": ["product_faq.md"]}
    res3 = {"confidence": 0.40, "response": "We do not offer corporate gift cards"}
    status3, reason3 = log_agent.evaluate_escalation(q3, kb3, res3)
    assert status3 == "Escalated"
    assert "No matching document" in reason3 or "Low confidence" in reason3
