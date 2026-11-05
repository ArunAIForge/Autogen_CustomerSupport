"""Generate customer replies using only retrieved company policy passages."""

from typing import Any, Dict, Optional

from backend.app.agents.autogen_runtime import create_assistant, run_assistant

RESOLUTION_AGENT_SYSTEM_MESSAGE = """You are the ResolutionAgent for ClothesSpot.
Use only retrieved company-document passages. Quote or accurately summarize their
contents, cite the source filename, and never promise actions or timelines absent
from those passages. If no suitable passage exists, say so and recommend human
review without claiming that a person has already acted."""


class ResolutionAgent:
    """Generates customer-ready responses strictly grounded in retrieved passages."""

    name = "ResolutionAgent"
    description = "Answers from retrieved company policies and cites their source files."

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client
        self.autogen_agent = create_assistant(
            self.name, self.description, RESOLUTION_AGENT_SYSTEM_MESSAGE, model_client
        )

    def process(
        self,
        query_data: Dict[str, Any],
        kb_data: Dict[str, Any],
        raw_complaint: str,
        customer_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        passages = kb_data.get("passages", [])
        sources = kb_data.get("sources", [])
        found = bool(kb_data.get("found") and passages and sources)
        can_resolve = bool(kb_data.get("can_resolve", False))
        greeting = f"Hello {customer_name}," if customer_name else "Hello,"

        if found:
            cited_passages = []
            for index, passage in enumerate(passages[:2]):
                source = passage.get("file_name")
                if not source and index < len(sources):
                    source = sources[index]
                source = source or "company knowledge base"
                content = passage.get("content", "").strip()
                if content:
                    cited_passages.append(f"[{source}] {content}")

            policy_context = "\n\n".join(cited_passages)
            task = (
                f"Customer request: {raw_complaint}\n"
                f"Retrieved policy passages:\n{policy_context}\n"
                f"Can this policy resolve the request: {can_resolve}\n"
                "Reply empathetically using only these passages. Cite source filenames. "
                "Do not invent actions, guarantees, or facts."
            )
            response = run_assistant(self.autogen_agent, task) or (
                f"{greeting}\n\nThank you for contacting ClothesSpot. "
                "The relevant information in our company documentation is:\n\n"
                + policy_context
            )
            if not can_resolve:
                response += (
                    "\n\nYour request needs review by our support team. "
                    "This ticket has been escalated for human review."
                )
            elif not self.autogen_agent:
                response += (
                    "\n\nIf these instructions do not address your situation, "
                    "please reply with your order details so our team can review it."
                )
            confidence = 0.90 if can_resolve else 0.50
        else:
            response = (
                f"{greeting}\n\nThank you for contacting ClothesSpot. "
                "I could not find a relevant answer in the available company "
                "documents, so I cannot confirm the applicable policy. "
                "This ticket has been escalated for human review."
            )
            confidence = 0.30

        return {
            "agent": self.name,
            "response": response,
            "confidence": confidence,
            "sources": sources if found else [],
            "formatted_output": f"Confidence: {confidence:.2f}\nResponse:\n{response}",
        }
