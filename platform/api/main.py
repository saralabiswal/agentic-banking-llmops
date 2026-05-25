"""FastAPI application entrypoint.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.api.routers import (
    audit,
    config,
    evaluation,
    experiments,
    guardrails,
    models,
    outcomes,
    pipeline,
    sse,
)
from platform.core.config import settings
from platform.observability.logging import configure_logging
from platform.observability.tracing import configure_tracing

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

configure_logging(settings)
configure_tracing(settings)
app = FastAPI(title="Banking Agentic AI Platform")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(pipeline.router)
app.include_router(sse.router)
app.include_router(config.router)
app.include_router(outcomes.router)
app.include_router(audit.router)
app.include_router(evaluation.router)
app.include_router(experiments.router)
app.include_router(guardrails.router)
app.include_router(models.router)
app.mount("/metrics", make_asgi_app())


@app.get("/health")
async def health() -> dict[str, str]:
    """Return API health."""
    return {"status": "ok"}
