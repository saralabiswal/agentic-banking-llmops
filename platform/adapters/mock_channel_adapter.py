"""Mock channel adapters for push, SMS, and CRM delivery.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from platform.core.interfaces import AuditWriter
from platform.core.schemas import AuditRecord, Channel, DeliveryReceipt, ProposedAction
from uuid import uuid4

import structlog

logger = structlog.get_logger()


class _BaseMockChannelAdapter:
    """Base behavior for deterministic mock channel delivery."""

    channel: Channel

    def __init__(self, audit_writer: AuditWriter | None = None) -> None:
        """Create a mock adapter with an optional audit writer."""
        self._audit_writer = audit_writer

    async def send(self, action: ProposedAction) -> DeliveryReceipt:
        """Return a delivered receipt and write a delivery audit record when configured."""
        receipt = DeliveryReceipt(
            receipt_id=f"del_{uuid4().hex[:12]}",
            action_id=action.action_id,
            channel=self.channel,
            status="DELIVERED",
            delivered_at=datetime.now(UTC),
            metadata={"action_type": action.action_type},
        )
        logger.info(
            "mock_channel_delivered",
            trace_id=action.metadata.get("trace_id", "unknown"),
            layer="6",
            operation="send",
            action_id=action.action_id,
            channel=self.channel.value,
        )
        if self._audit_writer is not None:
            await self._audit_writer.write(
                AuditRecord(
                    audit_id=f"aud_delivery_{receipt.receipt_id}",
                    event_type="ACTION_EXECUTED",
                    trace_id=str(action.metadata.get("trace_id", "unknown")),
                    session_id=str(action.metadata.get("session_id", "unknown")),
                    customer_id=str(action.metadata.get("customer_id", "unknown")),
                    timestamp=receipt.delivered_at,
                    layer="6",
                    payload=receipt.model_dump(mode="json"),
                )
            )
        return receipt


class MockPushAdapter(_BaseMockChannelAdapter):
    """Mock push notification adapter."""

    channel = Channel.PUSH


class MockSMSAdapter(_BaseMockChannelAdapter):
    """Mock SMS adapter."""

    channel = Channel.SMS


class MockCRMAdapter(_BaseMockChannelAdapter):
    """Mock CRM associate-case adapter."""

    channel = Channel.CRM
