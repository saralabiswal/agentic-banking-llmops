"""Dispute triage agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import RiskAssessment
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.dispute_triage import SYSTEM_PROMPT


class DisputeTriageAgent(BaseAgent):
    """Classifies dispute urgency and proposes resolution routing."""

    agent_name = "DisputeTriageAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = RiskAssessment
    required_tools = (
        "read_customer_profile",
        "query_dispute_history",
    )
