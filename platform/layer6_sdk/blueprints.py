"""Blueprint definitions for product-team SDK compositions.

Author: Sarala Biswal
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BlueprintConfig:
    """Static blueprint configuration owned by the platform team."""

    name: str
    scenario: str
    agents: list[str]
    channels: list[str]
    description: str


PAYMENT_RISK_INTERVENTION = BlueprintConfig(
    name="PAYMENT_RISK_INTERVENTION",
    scenario="payment_risk_intervention",
    agents=["RiskScoringAgent", "InterventionAgent"],
    channels=["MOBILE_PUSH", "SMS", "IN_APP_MESSAGE"],
    description="Detect payment risk and intervene with a hardship offer.",
)

BILLING_DISPUTE_RESOLUTION = BlueprintConfig(
    name="BILLING_DISPUTE_RESOLUTION",
    scenario="billing_dispute_resolution",
    agents=["DisputeTriageAgent", "ResolutionAgent"],
    channels=["IN_APP_MESSAGE", "EMAIL", "ASSOCIATE_QUEUE"],
    description="Autonomous dispute triage and resolution.",
)

CHURN_PREVENTION = BlueprintConfig(
    name="CHURN_PREVENTION",
    scenario="churn_prevention",
    agents=["ChurnSignalAgent", "RetentionOfferAgent"],
    channels=["MOBILE_PUSH", "EMAIL", "ASSOCIATE_QUEUE"],
    description="Identify churn signals and generate a retention offer.",
)

FRAUD_ALERT = BlueprintConfig(
    name="FRAUD_ALERT",
    scenario="fraud_alert",
    agents=["FraudDetectionAgent", "AlertAgent"],
    channels=["SMS", "MOBILE_PUSH", "ASSOCIATE_QUEUE"],
    description="Detect anomalous transactions and alert the customer.",
)

BLUEPRINTS: dict[str, BlueprintConfig] = {
    blueprint.name: blueprint
    for blueprint in [
        PAYMENT_RISK_INTERVENTION,
        BILLING_DISPUTE_RESOLUTION,
        CHURN_PREVENTION,
        FRAUD_ALERT,
    ]
}


def blueprint_for_scenario(scenario: str) -> BlueprintConfig:
    """Return the first blueprint matching a scenario."""
    for blueprint in BLUEPRINTS.values():
        if blueprint.scenario == scenario:
            return blueprint
    return PAYMENT_RISK_INTERVENTION
