"""Model registry and drift report API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

SEEDED_MODELS: list[dict[str, object]] = [
    {
        "model_id": "risk_model",
        "version": "risk-v4.2.1",
        "role": "champion",
        "champion_version": "risk-v4.2.1",
        "challenger_version": "risk-v4.3.0-rc1",
        "recall": 0.84,
        "air_score": 0.91,
        "drift_status": "monitor",
        "psi": 0.12,
        "champion_traffic": 95,
        "challenger_traffic": 5,
        "psi_trend": [
            {"date": "2026-05-08", "psi": 0.06},
            {"date": "2026-05-09", "psi": 0.08},
            {"date": "2026-05-10", "psi": 0.10},
            {"date": "2026-05-11", "psi": 0.12},
        ],
        "gates": [
            {"name": "Recall >= 0.78", "status": "PASS"},
            {"name": "Precision regression", "status": "PASS"},
            {"name": "Fairness AIR >= 0.80", "status": "PASS"},
            {"name": "Segment regression", "status": "PASS"},
        ],
    },
    {
        "model_id": "churn_model",
        "version": "churn-v2.8.0",
        "role": "champion",
        "champion_version": "churn-v2.8.0",
        "challenger_version": "churn-v2.9.0-rc2",
        "recall": 0.81,
        "air_score": 0.88,
        "drift_status": "stable",
        "psi": 0.07,
        "champion_traffic": 95,
        "challenger_traffic": 5,
        "psi_trend": [
            {"date": "2026-05-08", "psi": 0.05},
            {"date": "2026-05-09", "psi": 0.06},
            {"date": "2026-05-10", "psi": 0.06},
            {"date": "2026-05-11", "psi": 0.07},
        ],
        "gates": [
            {"name": "Recall >= 0.78", "status": "PASS"},
            {"name": "Precision regression", "status": "PASS"},
            {"name": "Fairness AIR >= 0.80", "status": "PASS"},
            {"name": "Segment regression", "status": "PASS"},
        ],
    },
    {
        "model_id": "payment_propensity_model",
        "version": "payprop-v3.5.2",
        "role": "champion",
        "champion_version": "payprop-v3.5.2",
        "challenger_version": "payprop-v3.6.0-rc1",
        "recall": 0.79,
        "air_score": 0.86,
        "drift_status": "investigate",
        "psi": 0.21,
        "champion_traffic": 95,
        "challenger_traffic": 5,
        "psi_trend": [
            {"date": "2026-05-08", "psi": 0.11},
            {"date": "2026-05-09", "psi": 0.14},
            {"date": "2026-05-10", "psi": 0.18},
            {"date": "2026-05-11", "psi": 0.21},
        ],
        "gates": [
            {"name": "Recall >= 0.78", "status": "PASS"},
            {"name": "Precision regression", "status": "PASS"},
            {"name": "Fairness AIR >= 0.80", "status": "PASS"},
            {"name": "Segment regression", "status": "MONITOR"},
        ],
    },
]


@router.get("/models")
async def get_models() -> list[dict[str, object]]:
    """Return seeded model identifiers."""
    return SEEDED_MODELS


@router.get("/drift/report/{model_id}")
async def get_drift_report(model_id: str) -> HTMLResponse:
    """Return a small embedded Evidently-style drift report."""
    model = next((item for item in SEEDED_MODELS if item["model_id"] == model_id), SEEDED_MODELS[0])
    html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Evidently drift report</title>
        <style>
          body {{
            margin: 0;
            background: #020617;
            color: #cbd5e1;
            font-family: system-ui, sans-serif;
          }}
          main {{ padding: 18px; }}
          h1 {{ color: #f8fafc; font-size: 18px; margin: 0 0 12px; }}
          .grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 10px;
          }}
          .card {{
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 12px;
            background: #0f172a;
          }}
          .value {{ color: #6ee7b7; font-size: 22px; font-weight: 700; }}
        </style>
      </head>
      <body>
        <main>
          <h1>Evidently Report - {model["model_id"]}</h1>
          <div class="grid">
            <section class="card"><div>PSI</div><div class="value">{model["psi"]}</div></section>
            <section class="card">
              <div>Drift status</div><div class="value">{model["drift_status"]}</div>
            </section>
            <section class="card">
              <div>AIR score</div><div class="value">{model["air_score"]}</div>
            </section>
          </div>
        </main>
      </body>
    </html>
    """
    return HTMLResponse(html)
