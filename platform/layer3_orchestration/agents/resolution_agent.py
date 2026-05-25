"""Dispute resolution agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import InterventionProposal
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.resolution import SYSTEM_PROMPT
from platform.llm_inference.schemas import TaskType


class ResolutionAgent(BaseAgent):
    """Proposes dispute resolutions without executing credits or notices."""

    agent_name = "ResolutionAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = InterventionProposal
    task_type = TaskType.DISPUTE_ANALYSIS
    required_tools = (
        "read_customer_profile",
        "query_dispute_history",
        "propose_resolution",
    )
