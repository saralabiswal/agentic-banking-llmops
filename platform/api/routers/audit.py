"""Audit API router.

Author: Sarala Biswal
"""

from __future__ import annotations

from platform.api.dependencies import get_runner
from platform.layer6_sdk.blueprint_runner import BlueprintRunner, InMemoryAuditWriter

from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/audit/latest")
async def get_latest_audit(
    runner: BlueprintRunner = Depends(get_runner),
) -> list[dict[str, object]]:
    """Return the most recent in-memory audit records across traces."""
    audit_writer = runner.audit_writer
    if not isinstance(audit_writer, InMemoryAuditWriter):
        return []
    records = sorted(audit_writer.records, key=lambda record: record.timestamp, reverse=True)
    return [record.model_dump(mode="json") for record in records[:24]]


@router.get("/audit/{trace_id}")
async def get_audit(
    trace_id: str,
    runner: BlueprintRunner = Depends(get_runner),
) -> list[dict[str, object]]:
    """Return audit records for a trace ID."""
    audit_writer = runner.audit_writer
    if not isinstance(audit_writer, InMemoryAuditWriter):
        return []
    return [
        record.model_dump(mode="json")
        for record in audit_writer.records
        if record.trace_id == trace_id
    ]
