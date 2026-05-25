"""Unit tests for API router helpers and adapter factory wiring.

Author: Sarala Biswal
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from platform.adapters import adapter_factory
from platform.api.routers import audit, guardrails, models
from platform.core.config import Settings
from platform.core.schemas import AuditRecord, Channel, CheckResult, ProposedAction
from platform.layer6_sdk.blueprint_runner import BlueprintRunner, InMemoryAuditWriter
from typing import Any

from pydantic import SecretStr


class ExternalAuditWriter:
    """Audit writer test double that is not the in-memory writer."""

    async def write(self, record: AuditRecord) -> None:
        """Accept audit writes without retaining them."""
        del record


class Recorder:
    """Factory test double that records constructor arguments."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs


async def test_audit_router_returns_latest_and_trace_filtered_records() -> None:
    """Audit router should expose recent records only for in-memory audit writers."""
    writer = InMemoryAuditWriter()
    runner = BlueprintRunner(audit_writer=writer)
    early = AuditRecord(
        audit_id="aud_1",
        event_type="CONTEXT_ASSEMBLY",
        trace_id="trace_a",
        session_id="sess_a",
        customer_id="C001",
        timestamp=datetime(2026, 5, 25, 10, 0, tzinfo=UTC),
        layer="1",
        payload={"step": "early"},
    )
    late = early.model_copy(
        update={
            "audit_id": "aud_2",
            "trace_id": "trace_b",
            "timestamp": datetime(2026, 5, 25, 10, 5, tzinfo=UTC),
        }
    )
    await writer.write(early)
    await writer.write(late)

    latest = await audit.get_latest_audit(runner)
    trace_records = await audit.get_audit("trace_a", runner)
    external_latest = await audit.get_latest_audit(
        BlueprintRunner(audit_writer=ExternalAuditWriter())
    )

    assert [record["audit_id"] for record in latest] == ["aud_2", "aud_1"]
    assert [record["audit_id"] for record in trace_records] == ["aud_1"]
    assert external_latest == []


async def test_guardrails_router_lists_rules_queue_and_records_decision() -> None:
    """Guardrail endpoints should serialize rules, pending queue, and reviewer decisions."""
    runner = BlueprintRunner()
    action = ProposedAction(
        action_id="ACT-review",
        action_type="OFFER_PLAN",
        requires_approval=True,
        channel=Channel.PUSH,
        amount=Decimal("25.00"),
        customer_message="We can help.",
    )
    flag = CheckResult(
        status="FLAGGED",
        rule_id="B-002",
        category="BUSINESS_POLICY",
        severity="HIGH",
        message="Supervisor approval required",
    )
    queue_item = await runner.approval_queue.enqueue(action, [flag], {"trace_id": "trace_q"})

    rules = await guardrails.get_rules()
    queue = await guardrails.get_queue(runner)
    response = await guardrails.record_decision(
        queue_item.queue_id,
        guardrails.DecisionRequest(decision="APPROVED", reason="ok"),
        runner,
    )

    assert {rule["rule_id"] for rule in rules} >= {"R-001", "B-002", "AI-001"}
    assert queue[0]["queue_id"] == queue_item.queue_id
    assert response == {"status": "recorded"}
    assert await runner.approval_queue.get_pending() == []


async def test_models_router_returns_catalog_and_fallback_drift_report() -> None:
    """Model router should return seeded models and fallback reports for unknown IDs."""
    catalog = await models.get_models()
    known_report = await models.get_drift_report("churn_model")
    fallback_report = await models.get_drift_report("unknown_model")

    assert {model["model_id"] for model in catalog} >= {"risk_model", "churn_model"}
    assert "churn_model" in known_report.body.decode()
    assert "risk_model" in fallback_report.body.decode()


def test_adapter_factory_wires_infrastructure_adapters(monkeypatch) -> None:
    """Factory functions should pass runtime settings into concrete adapters."""
    monkeypatch.setattr(adapter_factory, "ValkeyContextStore", Recorder)
    monkeypatch.setattr(adapter_factory, "PostgresFeatureStore", Recorder)
    monkeypatch.setattr(adapter_factory, "PostgresAuditWriter", Recorder)
    monkeypatch.setattr(adapter_factory, "PostgresQueueStore", Recorder)
    monkeypatch.setattr(adapter_factory, "QdrantVectorStore", Recorder)
    monkeypatch.setattr(adapter_factory, "QdrantMemoryStore", Recorder)
    monkeypatch.setattr(adapter_factory, "MLScoringService", Recorder)
    config = Settings(
        VALKEY_URL="redis://valkey.test:6379",
        POSTGRES_URL="postgresql+asyncpg://user:pass@db.test/app",
        QDRANT_URL="http://qdrant.test",
        QDRANT_COLLECTION="kb_test",
        EMBEDDING_MODEL="embedding-test",
    )

    context_store = adapter_factory.create_context_store(config)
    feature_store = adapter_factory.create_feature_store(config)
    audit_writer = adapter_factory.create_audit_writer(config)
    queue_store = adapter_factory.create_queue_store(config)
    vector_store = adapter_factory.create_vector_store(config)
    memory_store = adapter_factory.create_memory_store(config)
    ml_service = adapter_factory.create_ml_scoring_service()

    assert context_store.args == ("redis://valkey.test:6379",)
    assert feature_store.args == ("postgresql+asyncpg://user:pass@db.test/app",)
    assert audit_writer.args == ("postgresql+asyncpg://user:pass@db.test/app",)
    assert queue_store.args == ("postgresql+asyncpg://user:pass@db.test/app",)
    assert vector_store.args == ("http://qdrant.test", "kb_test")
    assert memory_store.kwargs == {
        "url": "http://qdrant.test",
        "collection": "customer_memory",
        "embedding_model": "embedding-test",
    }
    assert ml_service.args == ()


def test_adapter_factory_selects_llm_clients_and_channel_adapters(monkeypatch) -> None:
    """Factory should select LLM and channel adapters from settings and channel names."""
    monkeypatch.setattr(adapter_factory, "MockLLMClient", Recorder)
    monkeypatch.setattr(adapter_factory, "OllamaLLMClient", Recorder)
    monkeypatch.setattr(adapter_factory, "LiteLLMClient", Recorder)
    monkeypatch.setattr(adapter_factory, "MockPushAdapter", Recorder)
    monkeypatch.setattr(adapter_factory, "MockSMSAdapter", Recorder)
    monkeypatch.setattr(adapter_factory, "MockCRMAdapter", Recorder)
    monkeypatch.setattr(adapter_factory, "create_audit_writer", lambda config: "audit-writer")

    mock_client = adapter_factory.create_llm_client(Settings(LLM_BACKEND="mock"))
    ollama_client = adapter_factory.create_llm_client(
        Settings(LLM_BACKEND="ollama", LLM_MODEL="llama3.2", OLLAMA_BASE_URL="http://ollama")
    )
    openai_client = adapter_factory.create_llm_client(
        Settings(
            LLM_BACKEND="api",
            LLM_MODEL="gpt-4o-mini",
            OPENAI_API_KEY=SecretStr("openai-key"),
        )
    )
    anthropic_client = adapter_factory.create_llm_client(
        Settings(
            LLM_BACKEND="api",
            LLM_MODEL="claude-sonnet-4-20250514",
            ANTHROPIC_API_KEY=SecretStr("anthropic-key"),
        )
    )

    push_adapter = adapter_factory.create_channel_adapter("MOBILE_PUSH")
    sms_adapter = adapter_factory.create_channel_adapter("SMS")
    crm_adapter = adapter_factory.create_channel_adapter("CASE")
    default_adapter = adapter_factory.create_channel_adapter("EMAIL")

    assert mock_client.args == ()
    assert ollama_client.kwargs == {"model": "llama3.2", "base_url": "http://ollama"}
    assert openai_client.kwargs == {"model": "gpt-4o-mini", "api_key": "openai-key"}
    assert anthropic_client.kwargs == {
        "model": "claude-sonnet-4-20250514",
        "api_key": "anthropic-key",
    }
    assert push_adapter.args == ("audit-writer",)
    assert sms_adapter.args == ("audit-writer",)
    assert crm_adapter.args == ("audit-writer",)
    assert default_adapter.args == ("audit-writer",)
