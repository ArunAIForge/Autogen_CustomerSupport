"""Knowledge Base Agent for ClothesSpot.

Searches company documents (FAQs, policies) and pulls out only the relevant passages
with their exact source filenames.
"""

from typing import Any, Dict, List, Optional
from backend.app.agents.autogen_runtime import create_assistant
from backend.app.retrieval.kb_manager import get_kb_manager, search_kb


KNOWLEDGE_AGENT_SYSTEM_MESSAGE = """You are the KnowledgeBaseAgent for ClothesSpot.
Your sole job is to search the official company documents (shipping_policy.md, refund_policy.md, account_and_login.md, product_faq.md, billing_and_payments.md) using the search_kb tool.
You must pull out only the relevant policy passages and report the exact source file names.
Never invent policies or facts. If no relevant document is found in the knowledge base, state so honestly.
"""


class KnowledgeBaseAgent:
    """Invokes search_kb to extract grounded policy passages."""

    name = "KnowledgeBaseAgent"
    description = "Searches the company documents (FAQs, policies) and pulls out only the relevant passages."

    def __init__(self, model_client: Any = None) -> None:
        self.model_client = model_client
        self.autogen_agent = create_assistant(
            self.name, self.description, KNOWLEDGE_AGENT_SYSTEM_MESSAGE, model_client
        )
        self.kb_manager = get_kb_manager()

    def process(self, query_agent_data: Dict[str, Any], raw_complaint: str) -> Dict[str, Any]:
        """Search company knowledge base using summary and detected category."""
        summary = query_agent_data.get("summary", raw_complaint)
        category = query_agent_data.get("category", "General")

        # Execute hybrid search with query expansion
        search_result = self.kb_manager.search_kb(query=f"{summary} {raw_complaint}", category=category, top_k=3)

        found = search_result.get("found", False)
        passages = search_result.get("passages", [])
        sources = search_result.get("sources", [])
        can_resolve = search_result.get("can_resolve", True)

        if not found or not passages:
            formatted_output = (
                "Search Status: NO_MATCHING_DOCUMENT\n"
                "Sources Checked: shipping_policy.md, refund_policy.md, account_and_login.md, product_faq.md, billing_and_payments.md\n"
                "Passages Retrieved: None\n"
                "Note: No company policy or FAQ exists matching this inquiry."
            )
            return {
                "agent": self.name,
                "found": False,
                "can_resolve": False,
                "sources": [],
                "passages": [],
                "formatted_output": formatted_output,
                "raw_result": search_result,
            }

        passage_texts = []
        for p in passages:
            passage_texts.append(f"[{p['file_name']} - {p['section']}]\n{p['content']}")

        joined_passages = "\n\n".join(passage_texts)
        formatted_output = (
            f"Search Status: MATCH_FOUND\n"
            f"Sources: {', '.join(sources)}\n"
            f"Passages Retrieved:\n{joined_passages}"
        )

        if not can_resolve and search_result.get("resolution_notes"):
            formatted_output += f"\n\nConstraint Note: {search_result['resolution_notes']}"

        return {
            "agent": self.name,
            "found": True,
            "can_resolve": can_resolve,
            "sources": sources,
            "passages": passages,
            "formatted_output": formatted_output,
            "raw_result": search_result,
        }
