"""Risk scoring agent implementation.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import RiskAssessment
from platform.layer3_orchestration.agents.base_agent import BaseAgent
from platform.layer3_orchestration.prompts.risk_scoring import SYSTEM_PROMPT
from platform.llm_inference.schemas import TaskType


class RiskScoringAgent(BaseAgent):
    """Assesses payment risk and proposes the next orchestration hop."""

    agent_name = "RiskScoringAgent"
    system_prompt_template = SYSTEM_PROMPT
    output_schema = RiskAssessment
    task_type = TaskType.RISK_SCORING
    required_tools = (
        "read_customer_profile",
        "query_transaction_history",
        "compute_risk_signals",
    )
