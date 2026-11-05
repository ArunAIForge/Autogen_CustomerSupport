"""Sequential support workflow orchestration with optional LangSmith tracing."""

from typing import Any, Dict, List, Optional
from backend.app.agents.query_agent import CustomerQueryAgent
from backend.app.agents.knowledge_agent import KnowledgeBaseAgent
from backend.app.agents.resolution_agent import ResolutionAgent
from backend.app.agents.log_agent import LogAgent
from backend.app.agents.autogen_runtime import create_model_client
from backend.app.guardrails.input_guardrails import InputGuardrails
from backend.app.guardrails.output_guardrails import OutputGuardrails
from backend.app.models.schemas import AgentStep, ProcessedComplaintResponse
from backend.app.services.langsmith_tracer import trace_agent_run


class AutoGenSupportTeam:
    """Orchestrates multi-agent support team across the full complaint lifecycle."""

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client if model_client is not None else create_model_client()
        self.query_agent = CustomerQueryAgent(model_client=self.model_client)
        self.kb_agent = KnowledgeBaseAgent(model_client=self.model_client)
        self.resolution_agent = ResolutionAgent(model_client=self.model_client)
        self.log_agent = LogAgent(model_client=self.model_client)
        self.input_guardrails = InputGuardrails()
        self.output_guardrails = OutputGuardrails()

    @trace_agent_run(run_type="chain", name="AutoGenSupportTeam.run_complaint_workflow")
    def run_complaint_workflow(
        self,
        raw_complaint: str,
        customer_name: Optional[str] = None,
        order_id: Optional[str] = None
    ) -> ProcessedComplaintResponse:
        """Execute full sequential pipeline: Query -> KB -> Resolution -> Log."""
        # 1. Input Guardrails validation & PII redaction
        input_val = self.input_guardrails.validate_input(raw_complaint, customer_name)
        if not input_val["valid"]:
            ticket_id = self.log_agent.logger.get_next_ticket_id()
            refusal_response = f"Your request could not be processed due to a security policy violation: {input_val['reason']}"
            return ProcessedComplaintResponse(
                ticket_id=ticket_id,
                timestamp=self.log_agent.logger.get_next_ticket_id(),
                customer_name=customer_name or "Guest",
                order_id=order_id or "N/A",
                complaint=raw_complaint,
                category="Security",
                urgency="High",
                sentiment="Negative",
                summary="Input violation / Prompt injection attempt intercepted.",
                kb_sources=[],
                response=refusal_response,
                confidence=0.0,
                status="Escalated",
                escalation_reason=f"Security Guardrail Violation: {input_val['reason']}",
                agent_steps=[
                    AgentStep(
                        agent_name="InputGuardrails",
                        role="Security & Sanitation",
                        content=f"Rejected: {input_val['reason']}",
                    )
                ],
                redactions=input_val["redactions"],
                guardrail_status={"input_valid": False, "injection_detected": input_val["injection_detected"]},
            )

        sanitized_complaint = input_val["sanitized_text"]
        sanitized_customer = input_val.get("customer_name") or customer_name or "Guest"
        redactions = input_val["redactions"]

        agent_steps: List[AgentStep] = []

        # Step 1: CustomerQueryAgent
        query_out = self._execute_query_agent(sanitized_complaint)
        agent_steps.append(
            AgentStep(
                agent_name=self.query_agent.name,
                role=self.query_agent.description,
                content=query_out["formatted_output"],
                structured_data={
                    "category": query_out["category"],
                    "urgency": query_out["urgency"],
                    "sentiment": query_out["sentiment"],
                    "summary": query_out["summary"],
                    "flags": query_out["flags"],
                },
            )
        )

        # Step 2: KnowledgeBaseAgent
        kb_out = self._execute_kb_agent(query_out, sanitized_complaint)
        agent_steps.append(
            AgentStep(
                agent_name=self.kb_agent.name,
                role=self.kb_agent.description,
                content=kb_out["formatted_output"],
                structured_data={
                    "found": kb_out["found"],
                    "can_resolve": kb_out["can_resolve"],
                    "sources": kb_out["sources"],
                    "passage_count": len(kb_out["passages"]),
                },
            )
        )

        # Step 3: ResolutionAgent
        res_out = self._execute_resolution_agent(query_out, kb_out, sanitized_complaint, sanitized_customer)
        out_val = self.output_guardrails.validate_response(
            response_text=res_out["response"],
            retrieved_passages=kb_out["passages"],
            sources=kb_out["sources"],
        )
        if not out_val["valid"]:
            res_out["response"] = (
                "I could not verify a safe answer from the retrieved company documents. "
                "This ticket has been escalated for human review."
            )
            res_out["confidence"] = 0.0
            res_out["sources"] = []
            res_out["formatted_output"] = (
                f"Confidence: 0.00\nGuardrail: {out_val['reason']}\n"
                f"Response:\n{res_out['response']}"
            )

        agent_steps.append(
            AgentStep(
                agent_name=self.resolution_agent.name,
                role=self.resolution_agent.description,
                content=res_out["formatted_output"],
                structured_data={
                    "confidence": res_out["confidence"],
                    "sources": res_out["sources"],
                    "guardrail_passed": out_val["valid"],
                },
            )
        )

        # Step 4: LogAgent
        log_out = self._execute_log_agent(
            query_out,
            kb_out,
            res_out,
            sanitized_complaint,
            sanitized_customer,
            order_id,
            [step.model_dump() for step in agent_steps],
        )
        agent_steps.append(
            AgentStep(
                agent_name=self.log_agent.name,
                role=self.log_agent.description,
                content=log_out["formatted_output"],
                structured_data={
                    "ticket_id": log_out["ticket_id"],
                    "status": log_out["status"],
                    "escalation_reason": log_out["escalation_reason"],
                },
            )
        )

        return ProcessedComplaintResponse(
            ticket_id=log_out["ticket_id"],
            timestamp=log_out["timestamp"],
            customer_name=sanitized_customer,
            order_id=order_id or "N/A",
            complaint=sanitized_complaint,
            category=query_out["category"],
            urgency=query_out["urgency"],
            sentiment=query_out["sentiment"],
            summary=query_out["summary"],
            kb_sources=kb_out["sources"],
            response=res_out["response"],
            confidence=res_out["confidence"],
            status=log_out["status"],
            escalation_reason=log_out["escalation_reason"],
            agent_steps=agent_steps,
            redactions=redactions,
            guardrail_status={
                "input_valid": True,
                "output_valid": out_val["valid"],
                "hallucination_detected": out_val.get("hallucination_detected", False),
            },
        )

    @trace_agent_run(run_type="llm", name="CustomerQueryAgent.process")
    def _execute_query_agent(self, complaint: str):
        return self.query_agent.process(complaint)

    @trace_agent_run(run_type="tool", name="KnowledgeBaseAgent.process")
    def _execute_kb_agent(self, query_out: Dict[str, Any], complaint: str):
        return self.kb_agent.process(query_out, complaint)

    @trace_agent_run(run_type="llm", name="ResolutionAgent.process")
    def _execute_resolution_agent(self, query_out: Dict[str, Any], kb_out: Dict[str, Any], complaint: str, customer_name: str):
        return self.resolution_agent.process(
            query_data=query_out,
            kb_data=kb_out,
            raw_complaint=complaint,
            customer_name=customer_name,
        )

    @trace_agent_run(run_type="tool", name="LogAgent.process")
    def _execute_log_agent(
        self,
        query_out: Dict[str, Any],
        kb_out: Dict[str, Any],
        res_out: Dict[str, Any],
        complaint: str,
        customer_name: str,
        order_id: Optional[str],
        agent_steps: List[Dict[str, Any]],
    ):
        return self.log_agent.process(
            query_data=query_out,
            kb_data=kb_out,
            resolution_data=res_out,
            raw_complaint=complaint,
            customer_name=customer_name,
            order_id=order_id,
            agent_steps=agent_steps,
        )