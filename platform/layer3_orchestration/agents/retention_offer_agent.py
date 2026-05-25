"""Retention offer agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import InterventionProposal
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.retention_offer import SYSTEM_PROMPT
from platform.llm_inference.schemas import TaskType


class RetentionOfferAgent(BaseAgent):
    """Proposes retention offers without executing customer actions."""

    agent_name = "RetentionOfferAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = InterventionProposal
    task_type = TaskType.CHURN_ASSESSMENT
    required_tools = (
        "read_customer_profile",
        "propose_retention_offer",
    )
