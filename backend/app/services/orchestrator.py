"""Orchestration service layer for FastAPI and Streamlit."""

from typing import Any, Dict, List, Optional
from backend.app.agents.team import AutoGenSupportTeam
from backend.app.models.schemas import ComplaintRequest, ProcessedComplaintResponse


_team_instance: Optional[AutoGenSupportTeam] = None


def get_support_team() -> AutoGenSupportTeam:
    """Retrieve singleton AutoGenSupportTeam instance."""
    global _team_instance
    if _team_instance is None:
        _team_instance = AutoGenSupportTeam()
    return _team_instance


def process_customer_complaint(request: ComplaintRequest) -> ProcessedComplaintResponse:
    """Process incoming customer complaint through the multi-agent pipeline."""
    team = get_support_team()
    return team.run_complaint_workflow(
        raw_complaint=request.complaint,
        customer_name=request.customer_name,
        order_id=request.order_id,
    )
