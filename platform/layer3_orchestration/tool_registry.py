"""Tool definitions and registry-enforced authorization for Layer 3.

Author: Sarala Biswal
"""

from __future__ import annotations

from dataclasses import dataclass
from platform.core.exceptions import ToolAuthorizationError
from platform.observability.metrics import record_agent_tool_call
from typing import Literal

ToolMode = Literal["read_only", "compute_only", "propose_only"]


@dataclass(frozen=True)
class ToolDefinition:
    """Static definition of an agent-accessible tool."""

    name: str
    authorized_agents: tuple[str, ...]
    mode: ToolMode
    description: str


TOOLS: dict[str, ToolDefinition] = {
    "read_customer_profile": ToolDefinition(
        name="read_customer_profile",
        authorized_agents=(
            "RiskScoringAgent",
            "InterventionAgent",
            "DisputeTriageAgent",
            "ResolutionAgent",
            "ChurnSignalAgent",
            "RetentionOfferAgent",
        ),
        mode="read_only",
        description="Read unified customer profile from the context store.",
    ),
    "query_transaction_history": ToolDefinition(
        name="query_transaction_history",
        authorized_agents=("RiskScoringAgent",),
        mode="read_only",
        description="Retrieve recent card and deposit transactions.",
    ),
    "compute_risk_signals": ToolDefinition(
        name="compute_risk_signals",
        authorized_agents=("RiskScoringAgent",),
        mode="compute_only",
        description="Compute read-only payment risk indicators.",
    ),
    "query_intervention_history": ToolDefinition(
        name="query_intervention_history",
        authorized_agents=("InterventionAgent",),
        mode="read_only",
        description="Retrieve prior intervention contacts and outcomes.",
    ),
    "propose_intervention": ToolDefinition(
        name="propose_intervention",
        authorized_agents=("InterventionAgent",),
        mode="propose_only",
        description="Propose a payment intervention without executing it.",
    ),
    "query_dispute_history": ToolDefinition(
        name="query_dispute_history",
        authorized_agents=("DisputeTriageAgent", "ResolutionAgent"),
        mode="read_only",
        description="Retrieve dispute and investigation history.",
    ),
    "propose_resolution": ToolDefinition(
        name="propose_resolution",
        authorized_agents=("ResolutionAgent",),
        mode="propose_only",
        description="Propose a dispute resolution without executing it.",
    ),
    "compute_churn_signals": ToolDefinition(
        name="compute_churn_signals",
        authorized_agents=("ChurnSignalAgent",),
        mode="compute_only",
        description="Compute read-only churn and retention indicators.",
    ),
    "propose_retention_offer": ToolDefinition(
        name="propose_retention_offer",
        authorized_agents=("RetentionOfferAgent",),
        mode="propose_only",
        description="Propose a retention offer without executing it.",
    ),
}


def authorize_tool_call(agent_name: str, tool_name: str) -> None:
    """Raise ToolAuthorizationError when an agent is not allowed to use a tool."""
    tool = TOOLS.get(tool_name)
    if tool is None or agent_name not in tool.authorized_agents:
        record_agent_tool_call(agent_name, tool_name, "denied")
        message = f"{agent_name} is not authorized to call tool {tool_name}"
        raise ToolAuthorizationError(message)
    record_agent_tool_call(agent_name, tool_name, "authorized")


def authorized_tools_for_agent(agent_name: str) -> list[str]:
    """Return the ordered tool allowlist for an agent."""
    return [
        tool_name
        for tool_name, definition in TOOLS.items()
        if agent_name in definition.authorized_agents
    ]
