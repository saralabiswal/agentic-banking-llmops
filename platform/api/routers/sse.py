"""Server-Sent Events router for pipeline progress.

Author: Sarala Biswal
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from platform.api.dependencies import get_runner
from platform.layer6_sdk.blueprint_runner import BlueprintRunner

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.get("/pipeline/events/{trace_id}")
async def pipeline_events(
    trace_id: str,
    runner: BlueprintRunner = Depends(get_runner),
) -> StreamingResponse:
    """Stream retained and live pipeline events for a trace ID."""

    async def event_stream() -> AsyncIterator[str]:
        """Serialize retained and future runner events into the SSE wire format."""
        async for event in runner.event_bus.stream(trace_id):
            # The UI expects each event payload to carry the trace ID for stateless parsing.
            yield (
                f"event: {event.event_type}\n"
                f"data: {json.dumps({'trace_id': trace_id, **event.payload}, default=str)}\n\n"
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
