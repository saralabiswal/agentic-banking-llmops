"""Mock LLM client adapter for local deterministic runs.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.core.schemas import (
    Channel,
    InterventionProposal,
    PolicyCompliance,
    PolicyMatch,
    ProposedAction,
    RiskAssessment,
)
from typing import Any

from pydantic import BaseModel


class MockLLMClient:
    """Deterministic LLMClient implementation for offline demos and tests."""

    async def complete(self, system: str, user: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Return a realistic schema-valid response based on customer and scenario text."""
        del system
        response = self._response_for(user_message=user, schema=schema)
        validated = schema.model_validate(response)
        return validated.model_dump(mode="json")

    def _response_for(self, user_message: str, schema: type[BaseModel]) -> dict[str, Any]:
        """Route a request to the scripted response for the requested schema."""
        text = user_message.lower()
        customer_id = self._customer_id(text)
        if schema is RiskAssessment:
            return self._risk_assessment(customer_id, text).model_dump(mode="json")
        if schema is InterventionProposal:
            return self._intervention_proposal(customer_id, text).model_dump(mode="json")
        return schema.model_construct().model_dump(mode="json")

    def _customer_id(self, text: str) -> str:
        """Extract the known customer ID from prompt text."""
        for customer_id in ("c001", "c002", "c003"):
            if customer_id in text:
                return customer_id.upper()
        return "C002" if "marcus" in text else "C001"

    def _risk_assessment(self, customer_id: str, text: str) -> RiskAssessment:
        """Create a customer-specific risk assessment."""
        if customer_id == "C002" and "payment" in text:
            return RiskAssessment(
                risk_level="CRITICAL",
                risk_score=0.71,
                confidence=0.89,
                lower_confidence_reason="CRM unavailable -- NPS and tenure absent",
                primary_signals=[
                    "2 missed payments in 90 days -- meets hardship threshold",
                    "Card utilization 76% -- above 70% risk threshold",
                    "Checking balance $312.40 -- below $500 hardship threshold",
                    "No direct deposit -- income instability signal",
                ],
                protective_signals=[
                    "14 app logins in 30 days -- customer engaged",
                    "SMS and push enabled -- customer reachable",
                    "0 interventions in last 7 days -- contact cap clear",
                ],
                policy_match=PolicyMatch(
                    hardship_eligible=True,
                    reason="2+ missed payments and checking balance below $500",
                    policy_ref="KB-HARD-001-v2.3",
                ),
                recommended_next="InterventionAgent",
            )

        risk_score = 0.03 if customer_id == "C003" else 0.08
        return RiskAssessment(
            risk_level="LOW",
            risk_score=risk_score,
            confidence=0.94,
            lower_confidence_reason=None,
            primary_signals=["Low current risk score", "No acute delinquency signals"],
            protective_signals=["Healthy balances", "Strong engagement pattern"],
            policy_match=PolicyMatch(
                hardship_eligible=False,
                reason="Hardship criteria are not met",
                policy_ref="KB-HARD-001-v2.3",
            ),
            recommended_next="MonitoringAgent",
        )

    def _intervention_proposal(self, customer_id: str, text: str) -> InterventionProposal:
        """Create a customer-specific intervention proposal."""
        if customer_id == "C002" and "payment" in text:
            return InterventionProposal(
                intervention_type="HARDSHIP_PROGRAM_ENROLLMENT_OFFER",
                intervention_channel=Channel.MOBILE,
                customer_message=(
                    "We noticed recent account activity and may be able to help. "
                    "You may qualify for a hardship assistance option."
                ),
                internal_note=(
                    "Customer meets KB-HARD-001-v2.3 eligibility: 2 missed payments "
                    "and checking balance below $500."
                ),
                proposed_actions=[
                    ProposedAction(
                        action_id="ACT-001",
                        action_type="SEND_PUSH_NOTIFICATION",
                        requires_approval=False,
                        channel=Channel.PUSH,
                    ),
                    ProposedAction(
                        action_id="ACT-002",
                        action_type="CREATE_HARDSHIP_ENROLLMENT_CASE",
                        requires_approval=True,
                        case_type="PAYMENT_DEFERRAL_90_DAY",
                        amount="420.00",
                        approval_reason="Standard approval queue for account action.",
                    ),
                ],
                policy_compliance=PolicyCompliance(
                    contact_frequency_ok=True,
                    reason="0 contacts in last 7 days -- under 3/7d cap",
                    policy_ref="KB-COMP-003-v3.1",
                ),
                estimated_impact="34% improvement in on-time payment probability",
                fallback_if_no_response="Escalate to outbound call after 7 days.",
            )

        return InterventionProposal(
            intervention_type="MONITORING_ONLY",
            intervention_channel=Channel.MOBILE,
            customer_message="No immediate action is needed.",
            internal_note="Risk assessment recommends monitoring only.",
            proposed_actions=[
                ProposedAction(
                    action_id="ACT-001",
                    action_type="NO_ACTION_MONITOR",
                    requires_approval=False,
                    channel=Channel.MOBILE,
                )
            ],
            policy_compliance=PolicyCompliance(
                contact_frequency_ok=True,
                reason="No customer contact proposed",
                policy_ref="KB-COMP-003-v3.1",
            ),
            estimated_impact="Avoids unnecessary intervention for low-risk customer.",
            fallback_if_no_response=None,
        )
