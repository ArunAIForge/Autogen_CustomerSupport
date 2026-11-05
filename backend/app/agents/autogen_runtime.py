"""Shared AutoGen model setup and bounded synchronous agent execution."""

import asyncio
from typing import Any, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

from backend.app.config import settings


def create_model_client() -> Optional[OpenAIChatCompletionClient]:
    """Create an external model client only when explicitly enabled."""
    if not settings.AUTOGEN_ENABLED:
        return None
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("AUTOGEN_ENABLED requires OPENAI_API_KEY.")
    return OpenAIChatCompletionClient(
        model=settings.OPENAI_MODEL,
        api_key=settings.OPENAI_API_KEY,
    )


def create_assistant(
    name: str,
    description: str,
    system_message: str,
    model_client: Any,
) -> Optional[AssistantAgent]:
    if model_client is None:
        return None
    return AssistantAgent(
        name=name,
        description=description,
        system_message=system_message,
        model_client=model_client,
        max_tool_iterations=1,
    )


def run_assistant(agent: Optional[AssistantAgent], task: str) -> Optional[str]:
    """Run a single bounded task and return its final text, if configured."""
    if agent is None:
        return None
    result = asyncio.run(agent.run(task=task))
    if not result.messages:
        raise RuntimeError(f"AutoGen agent {agent.name} returned no messages.")
    content = getattr(result.messages[-1], "content", None)
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"AutoGen agent {agent.name} returned no text.")
    return content.strip()
