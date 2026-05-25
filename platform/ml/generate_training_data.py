"""Generate synthetic training and benchmark data for banking propensity models.

Author: Sarala Biswal
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RISK_FEATURES = [
    "card_utilization",
    "card_missed_payments_90d",
    "banking_overdraft_count_30d",
    "checking_to_credit_limit_ratio",
    "crm_tenure_months",
    "crm_nps_score",
    "card_balance_to_limit_ratio",
]

CHURN_FEATURES = [
    "crm_tenure_months",
    "crm_nps_score",
    "crm_open_tickets",
    "intervention_count_7d",
    "card_utilization",
    "log_checking_balance",
    "days_since_last_contact",
]

DATA_DIR = Path(__file__).resolve().parent / "data"


def generate_payment_risk_data(n_samples: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic payment-default risk training samples."""
    rng = np.random.default_rng(seed)
    card_utilization = rng.beta(2.5, 2.0, n_samples)
    missed = rng.poisson(lam=np.clip(card_utilization * 1.8, 0.1, 3.0))
    overdrafts = rng.poisson(lam=np.clip(card_utilization * 0.9, 0.05, 2.0))
    credit_limit = rng.lognormal(mean=8.4, sigma=0.45, size=n_samples)
    checking_balance = rng.normal(loc=1700, scale=1800, size=n_samples)
    checking_ratio = checking_balance / credit_limit
    tenure = rng.integers(1, 121, n_samples)
    nps = np.clip(rng.normal(loc=32 - card_utilization * 45, scale=28, size=n_samples), -100, 100)
    card_balance_ratio = np.clip(
        card_utilization + rng.normal(loc=0.0, scale=0.04, size=n_samples),
        0.0,
        1.0,
    )
    logits = (
        -3.3
        + 2.6 * card_utilization
        + 0.55 * missed
        + 0.38 * overdrafts
        - 0.75 * checking_ratio
        - 0.006 * tenure
        - 0.009 * nps
        + 1.1 * card_balance_ratio
    )
    label = _threshold_labels(logits, target_rate=0.15, rng=rng)
    return pd.DataFrame(
        {
            "card_utilization": card_utilization,
            "card_missed_payments_90d": missed,
            "banking_overdraft_count_30d": overdrafts,
            "checking_to_credit_limit_ratio": checking_ratio,
            "crm_tenure_months": tenure,
            "crm_nps_score": nps,
            "card_balance_to_limit_ratio": card_balance_ratio,
            "segment": _balance_segment(checking_balance),
            "label": label,
        }
    )


def generate_churn_data(n_samples: int = 2000, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic churn-propensity training samples."""
    rng = np.random.default_rng(seed + 17)
    tenure = rng.integers(1, 145, n_samples)
    nps = np.clip(rng.normal(loc=36, scale=34, size=n_samples), -100, 100)
    open_tickets = rng.poisson(lam=np.clip((40 - nps) / 35, 0.05, 3.5))
    interventions = rng.poisson(lam=0.35, size=n_samples)
    card_utilization = rng.beta(2.0, 2.6, n_samples)
    checking_balance = np.clip(rng.lognormal(mean=7.2, sigma=1.0, size=n_samples) - 700, 0, None)
    log_checking = np.log1p(checking_balance)
    days_since_last_contact = rng.integers(1, 181, n_samples)
    logits = (
        -3.0
        - 0.012 * tenure
        - 0.018 * nps
        + 0.35 * open_tickets
        + 0.24 * interventions
        + 0.9 * card_utilization
        - 0.13 * log_checking
        + 0.009 * days_since_last_contact
    )
    label = _threshold_labels(logits, target_rate=0.12, rng=rng)
    return pd.DataFrame(
        {
            "crm_tenure_months": tenure,
            "crm_nps_score": nps,
            "crm_open_tickets": open_tickets,
            "intervention_count_7d": interventions,
            "card_utilization": card_utilization,
            "log_checking_balance": log_checking,
            "days_since_last_contact": days_since_last_contact,
            "segment": _balance_segment(checking_balance),
            "label": label,
        }
    )


def generate_benchmark_set(n_samples: int = 200, seed: int = 4242) -> dict[str, pd.DataFrame]:
    """Generate held-out benchmark datasets for evaluation gates."""
    return {
        "payment_risk_model": generate_payment_risk_data(n_samples=n_samples, seed=seed),
        "churn_propensity_model": generate_churn_data(n_samples=n_samples, seed=seed),
    }


def write_training_data(output_dir: Path = DATA_DIR) -> None:
    """Write reproducible synthetic datasets to CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    generate_payment_risk_data().to_csv(output_dir / "payment_risk_training.csv", index=False)
    generate_churn_data().to_csv(output_dir / "churn_training.csv", index=False)
    benchmarks = generate_benchmark_set()
    benchmarks["payment_risk_model"].to_csv(
        output_dir / "payment_risk_benchmark.csv",
        index=False,
    )
    benchmarks["churn_propensity_model"].to_csv(output_dir / "churn_benchmark.csv", index=False)


def _threshold_labels(
    logits: np.ndarray,
    target_rate: float,
    rng: np.random.Generator,
) -> np.ndarray:
    noisy_score = logits + rng.normal(loc=0.0, scale=0.35, size=len(logits))
    threshold = np.quantile(noisy_score, 1.0 - target_rate)
    return np.asarray(noisy_score >= threshold, dtype=int)


def _balance_segment(balance: np.ndarray) -> list[str]:
    quantiles = np.quantile(balance, [0.25, 0.5, 0.75])
    segments: list[str] = []
    for value in balance:
        amount = float(value)
        if amount <= float(quantiles[0]):
            segments.append("Q1_LOW_BALANCE")
        elif amount <= float(quantiles[1]):
            segments.append("Q2_BALANCE")
        elif amount <= float(quantiles[2]):
            segments.append("Q3_BALANCE")
        else:
            segments.append("Q4_HIGH_BALANCE")
    return segments


def main() -> None:
    """CLI entry point for `make generate-data`."""
    write_training_data()
    print(f"Wrote training and benchmark datasets to {DATA_DIR}")


if __name__ == "__main__":
    main()
