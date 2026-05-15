"""Pipeline run and status API router.

Author: Sarala Biswal
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from platform.api.dependencies import get_runner
from platform.layer6_sdk.blueprint_runner import BlueprintRunner
from platform.layer6_sdk.blueprints import BLUEPRINTS, BlueprintConfig, blueprint_for_scenario
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter()


class PipelineRunRequest(BaseModel):
    """Request body for starting a pipeline."""

    customer_id: str
    scenario: str
    blueprint: str | None = None
    caller_id: str = "api"
    trigger: str = "api"


class PipelineRunSummary(BaseModel):
    """Recent pipeline run summary for UI selectors."""

    trace_id: str
    session_id: str | None = None
    status: str
    customer_id: str | None = None
    scenario: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


@router.post("/pipeline/run")
async def run_pipeline(
    request: PipelineRunRequest,
    runner: BlueprintRunner = Depends(get_runner),
) -> dict[str, str]:
    """Start a pipeline in the background and return identifiers."""
    started_at = datetime.now(UTC)
    session_id = f"sess_{request.customer_id}_{started_at:%Y%m%d_%H%M%S}_{uuid4().hex[:6]}"
    trace_id = f"trace_{session_id}"
    blueprint = (
        BLUEPRINTS[request.blueprint]
        if request.blueprint is not None and request.blueprint in BLUEPRINTS
        else blueprint_for_scenario(request.scenario)
    )
    runner.status_by_trace[trace_id] = {
        "trace_id": trace_id,
        "session_id": session_id,
        "status": "started",
        "customer_id": request.customer_id,
        "scenario": request.scenario,
        "started_at": started_at.isoformat(),
    }
    asyncio.create_task(
        _run_background(
            runner=runner,
            blueprint=blueprint,
            customer_id=request.customer_id,
            trigger=request.trigger,
            caller_id=request.caller_id,
            session_id=session_id,
            trace_id=trace_id,
        )
    )
    return {"trace_id": trace_id, "session_id": session_id, "status": "started"}


@router.get("/pipeline/runs")
async def pipeline_runs(
    runner: BlueprintRunner = Depends(get_runner),
) -> list[PipelineRunSummary]:
    """Return recent pipeline runs newest first."""
    indexed_runs = list(enumerate(runner.status_by_trace.items()))
    sorted_runs = sorted(indexed_runs, key=_run_sort_key, reverse=True)
    return [
        PipelineRunSummary(
            trace_id=trace_id,
            session_id=_optional_string(status.get("session_id")),
            status=_optional_string(status.get("status")) or "unknown",
            customer_id=_optional_string(status.get("customer_id")),
            scenario=_optional_string(status.get("scenario")),
            started_at=_optional_string(status.get("started_at")),
            completed_at=_optional_string(status.get("completed_at")),
        )
        for _, (trace_id, status) in sorted_runs
    ]


@router.get("/pipeline/status/{trace_id}")
async def pipeline_status(
    trace_id: str,
    runner: BlueprintRunner = Depends(get_runner),
) -> dict[str, object]:
    """Return current pipeline state."""
    return runner.status_by_trace.get(trace_id, {"trace_id": trace_id, "status": "unknown"})


async def _run_background(
    *,
    runner: BlueprintRunner,
    blueprint: BlueprintConfig,
    customer_id: str,
    trigger: str,
    caller_id: str,
    session_id: str,
    trace_id: str,
) -> None:
    try:
        await runner.run(
            blueprint=blueprint,
            customer_id=customer_id,
            trigger=trigger,
            caller_id=caller_id,
            session_id=session_id,
            trace_id=trace_id,
        )
    except Exception as exc:
        runner.status_by_trace[trace_id] = {
            **runner.status_by_trace.get(trace_id, {}),
            "status": "failed",
            "error": str(exc),
            "completed_at": datetime.now(UTC).isoformat(),
        }


def _run_sort_key(item: tuple[int, tuple[str, dict[str, Any]]]) -> tuple[str, int]:
    index, (trace_id, status) = item
    sort_timestamp = (
        _optional_string(status.get("started_at"))
        or _optional_string(status.get("completed_at"))
        or _timestamp_from_trace_id(trace_id)
        or ""
    )
    return sort_timestamp, index


def _timestamp_from_trace_id(trace_id: str) -> str | None:
    parts = trace_id.split("_")
    if len(parts) < 5:
        return None
    date_part = parts[-3]
    time_part = parts[-2]
    if not (date_part.isdigit() and time_part.isdigit()):
        return None
    return f"{date_part}T{time_part}"


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None
