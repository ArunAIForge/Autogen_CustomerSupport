"""Log Agent for ClothesSpot.

Records every ticket to logs/tickets.csv using the log_ticket tool, evaluates
the 5-point escalation policy, and terminates the AutoGen workflow with LOGGED.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from backend.app.agents.autogen_runtime import create_assistant
from backend.app.services.ticket_logger import get_ticket_logger, log_ticket


LOG_AGENT_SYSTEM_MESSAGE = """You are the LogAgent for ClothesSpot.
Your responsibility is to:
1. Evaluate the 5-point escalation policy:
   Escalate to human support if ANY of these 5 conditions is true:
   - Urgency is High
   - Customer sentiment is Angry
   - KnowledgeBaseAgent found no matching document or cannot resolve the query
   - Issue involves legal threats, fraud, or payment disputes
   - ResolutionAgent confidence is low (< 0.70)
2. Call the log_ticket tool to append a complete audit record to logs/tickets.csv.
3. Emit the word LOGGED to signal clean termination of the multi-agent workflow.
"""


class LogAgent:
    """Evaluates escalation criteria, writes tickets to CSV, and terminates workflow."""

    name = "LogAgent"
    description = "Records every ticket to a file. If the case is complicated, marks it Escalated and hands it to human support."

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client
        self.autogen_agent = create_assistant(
            self.name, self.description, LOG_AGENT_SYSTEM_MESSAGE, model_client
        )
        self.logger = get_ticket_logger()

    def evaluate_escalation(
        self,
        query_data: Dict[str, Any],
        kb_data: Dict[str, Any],
        resolution_data: Dict[str, Any]
    ) -> Tuple[str, Optional[str]]:
        """Evaluate strict 5-point escalation rule."""
        urgency = query_data.get("urgency", "Low")
        sentiment = query_data.get("sentiment", "Neutral")
        flags = query_data.get("flags", [])
        found = kb_data.get("found", False)
        can_resolve = kb_data.get("can_resolve", True)
        confidence = float(resolution_data.get("confidence", 1.0))

        reasons: List[str] = []

        # 1. Urgency is High
        if urgency.lower() == "high":
            reasons.append("High urgency")

        # 2. Customer is very angry
        if sentiment.lower() == "angry":
            reasons.append("Angry customer")

        # 3. No matching document or cannot resolve request
        if not found or not can_resolve:
            reasons.append("No matching document found in knowledge base")

        # 4. Legal threats, fraud, or payment disputes
        if "legal_threats" in flags:
            reasons.append("Legal threat")
        if "payment_disputes" in flags:
            reasons.append("Payment dispute")
        if "fraud" in flags:
            reasons.append("Suspected fraud / security incident")

        # 5. Low confidence
        if confidence < 0.70:
            reasons.append(f"Low confidence ({confidence:.2f})")

        if reasons:
            status = "Escalated"
            escalation_reason = " + ".join(reasons)
        else:
            status = "Resolved"
            escalation_reason = "None"

        return status, escalation_reason

    def process(
        self,
        query_data: Dict[str, Any],
        kb_data: Dict[str, Any],
        resolution_data: Dict[str, Any],
        raw_complaint: str,
        customer_name: Optional[str] = None,
        order_id: Optional[str] = None,
        agent_steps: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Record ticket and emit LOGGED termination signal."""
        status, escalation_reason = self.evaluate_escalation(query_data, kb_data, resolution_data)
        
        ticket_id = self.logger.get_next_ticket_id()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sources_str = ", ".join(kb_data.get("sources", [])) if kb_data.get("sources") else "None"
        workflow_steps = list(agent_steps or [])
        workflow_steps.append({
            "agent_name": self.name,
            "timestamp": timestamp,
            "decision": status,
            "escalation_reason": escalation_reason,
            "termination": "LOGGED",
        })
        
        # Log via ticket tool
        confirmation = log_ticket(
            ticket_id=ticket_id,
            timestamp=timestamp,
            customer_name=customer_name or "Guest",
            order_id=order_id or "N/A",
            complaint=raw_complaint,
            category=query_data.get("category", "General"),
            urgency=query_data.get("urgency", "Low"),
            sentiment=query_data.get("sentiment", "Neutral"),
            kb_sources=sources_str,
            response=resolution_data.get("response", ""),
            status=status,
            escalation_reason=escalation_reason,
            confidence=float(resolution_data.get("confidence", 0.0)),
            agent_steps=workflow_steps,
        )

        formatted_output = (
            f"Ticket ID: {ticket_id}\n"
            f"Status: {status}\n"
            f"Escalation Reason: {escalation_reason}\n"
            f"Audit Log: Saved to logs/tickets.csv\n"
            f"Termination Signal: LOGGED"
        )

        return {
            "agent": self.name,
            "ticket_id": ticket_id,
            "timestamp": timestamp,
            "status": status,
            "escalation_reason": escalation_reason,
            "agent_steps": workflow_steps,
            "confirmation": confirmation,
            "formatted_output": formatted_output,
        }
