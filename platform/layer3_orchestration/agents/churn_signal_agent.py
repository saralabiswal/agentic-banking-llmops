"""Churn signal agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import RiskAssessment
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.churn_signal import SYSTEM_PROMPT


class ChurnSignalAgent(BaseAgent):
    """Assesses churn signals and proposes retention routing."""

    agent_name = "ChurnSignalAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = RiskAssessment
    required_tools = (
        "read_customer_profile",
        "compute_churn_signals",
    )
