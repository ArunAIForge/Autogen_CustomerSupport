"""Pydantic schemas and data models for ClothesSpot AI Customer Desk."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ComplaintRequest(BaseModel):
    """Incoming customer complaint submission."""
    complaint: str = Field(..., min_length=3, max_length=4000, description="Raw complaint text")
    customer_name: Optional[str] = Field(default="", description="Customer full name")
    order_id: Optional[str] = Field(default="", description="Optional associated order ID")


class AgentStep(BaseModel):
    """Execution step detail from a specific agent."""
    agent_name: str
    role: str
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


class ProcessedComplaintResponse(BaseModel):
    """Complete workflow response containing all agent steps and final resolution."""
    ticket_id: str
    timestamp: str
    customer_name: str
    order_id: str
    complaint: str
    category: str
    urgency: str
    sentiment: str
    summary: str
    kb_sources: List[str]
    response: str
    confidence: float
    status: str  # "Resolved" or "Escalated"
    escalation_reason: Optional[str] = None
    agent_steps: List[AgentStep]
    redactions: List[str] = Field(default_factory=list)
    guardrail_status: Dict[str, Any] = Field(default_factory=dict)


class TicketRecord(BaseModel):
    """Audit log ticket record schema matching CSV columns."""
    ticket_id: str
    timestamp: str
    customer_name: str
    order_id: str
    complaint: str
    category: str
    urgency: str
    sentiment: str
    kb_sources: str
    response: str
    status: str
    escalation_reason: str
    confidence: float = 0.0
    agent_steps: List[Dict[str, Any]] = Field(default_factory=list)


class AnalyticsSummary(BaseModel):
    """Aggregated support desk operational metrics."""
    total_tickets: int
    resolved_count: int
    escalated_count: int
    escalation_rate: float
    categories: Dict[str, int]
    urgencies: Dict[str, int]
    sentiments: Dict[str, int]
    avg_confidence: float
