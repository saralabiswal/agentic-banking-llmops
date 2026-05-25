"""LLM-as-judge evaluator for agent reasoning quality.

Author: Sarala Biswal
"""

from __future__ import annotations

import json
from platform.core.interfaces import LLMInferenceService
from platform.evaluation.schemas import JudgeResult
from platform.llm_inference.schemas import TaskType

RUBRIC = """
Score 5: Reasoning cites specific policy, quantifies risk, names action.
Score 4: Reasoning is complete but lacks specific policy reference.
Score 3: Reasoning is plausible but generic.
Score 2: Reasoning has gaps or internal inconsistencies.
Score 1: Reasoning is off-topic, hallucinated, or dangerous.
"""


class LLMJudgeEvaluator:
    """Uses the routed inference service to score agent reasoning quality."""

    def __init__(self, llm: LLMInferenceService) -> None:
        """Create a judge evaluator."""
        self._llm = llm

    async def evaluate_reasoning(
        self,
        agent_output: str,
        scenario: str,
        customer_context: str,
        trace_id: str,
    ) -> JudgeResult:
        """Evaluate agent reasoning against the rubric."""
        try:
            result = await self._llm.complete(
                messages=[
                    {"role": "system", "content": RUBRIC},
                    {
                        "role": "user",
                        "content": (
                            f"scenario={scenario}\n"
                            f"customer_context={customer_context}\n"
                            f"agent_output={agent_output}"
                        ),
                    },
                ],
                task_type=TaskType.INTERVENTION_REASONING,
                trace_id=trace_id,
                schema=JudgeResult,
            )
            payload = json.loads(result.content)
            payload["trace_id"] = trace_id
            return JudgeResult.model_validate(payload)
        except Exception:
            return JudgeResult(
                score=3,
                reasoning="Fallback judge result: evaluator could not parse a routed LLM response.",
                flags=["judge_fallback"],
                trace_id=trace_id,
            )
