"""Base class for specialized Layer 3 agents.

Author: Sarala Biswal
"""

from __future__ import annotations

import time
from platform.core.exceptions import ToolAuthorizationError
from platform.core.interfaces import LLMClient
from platform.core.schemas import AgentContext, AgentOutput
from platform.layer3_orchestration.tool_registry import authorize_tool_call
from platform.observability.metrics import metered
from platform.observability.tracing import traced
from typing import ClassVar

from pydantic import BaseModel


class BaseAgent:
    """
    Base class for specialized agents.

    Subclasses define prompt text, output schema, and required tools. The
    shared run method enforces registry-level tool authorization before any
    model call and returns typed AgentOutput objects.
    """

    agent_name: ClassVar[str] = "BaseAgent"
    system_prompt_template: ClassVar[str] = ""
    output_schema: ClassVar[type[BaseModel]] = BaseModel
    required_tools: ClassVar[tuple[str, ...]] = ()
    max_tokens: ClassVar[int] = 2048

    @traced(layer="L3", operation="agent_run")
    @metered(layer="L3")
    async def run(self, context: AgentContext, llm: LLMClient) -> AgentOutput:
        """Run the agent and validate the model output against its schema."""
        started = time.perf_counter()
        self._authorize_required_tools(context)
        raw_output = await llm.complete(
            system=self._build_system_prompt(context),
            user=self._build_user_message(context),
            schema=self.output_schema,
        )
        validated = self.output_schema.model_validate(raw_output)
        return AgentOutput(
            agent_name=self.agent_name,
            output=validated.model_dump(mode="json"),
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    def _authorize_required_tools(self, context: AgentContext) -> None:
        for tool_name in self.required_tools:
            if tool_name not in context.authorized_tools:
                message = f"{self.agent_name} context missing tool {tool_name}"
                raise ToolAuthorizationError(message)
            authorize_tool_call(self.agent_name, tool_name)

    def _build_system_prompt(self, context: AgentContext) -> str:
        policy_refs = ", ".join(
            f"{chunk.document_id}-v{chunk.doc_version}" for chunk in context.policy_chunks
        )
        tools = ", ".join(context.authorized_tools)
        return (
            f"{self.system_prompt_template}\n"
            f"Authorized tools: {tools}.\n"
            f"Policy context: {policy_refs}.\n"
            "Return only fields that match the requested schema."
        )

    def _build_user_message(self, context: AgentContext) -> str:
        prior = [output.model_dump(mode="json") for output in context.prior_outputs]
        return (
            f"customer_id={context.customer_id}\n"
            f"session_id={context.session_id}\n"
            f"scenario={context.scenario}\n"
            f"pipeline_step={context.pipeline_step}\n"
            f"trace_id={context.trace_id}\n"
            f"prior_outputs={prior}\n"
            f"policy_chunks={[chunk.raw_text for chunk in context.policy_chunks]}"
        )
