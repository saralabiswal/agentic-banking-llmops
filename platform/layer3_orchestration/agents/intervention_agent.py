"""Payment intervention agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import InterventionProposal
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.intervention import SYSTEM_PROMPT


class InterventionAgent(BaseAgent):
    """Proposes payment interventions without executing customer actions."""

    agent_name = "InterventionAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = InterventionProposal
    required_tools = (
        "read_customer_profile",
        "query_intervention_history",
        "propose_intervention",
    )
