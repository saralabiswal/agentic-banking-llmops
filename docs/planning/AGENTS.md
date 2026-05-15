# AGENTS.md — Banking Agentic AI Platform

> This file is read by Codex before every task.
> It is the single source of authority for all coding standards,
> technology choices, and structural decisions.
> When in doubt, follow this file. If this file conflicts with a task
> prompt, follow this file and note the conflict.

---

## What This Repository Is

A local, open-source reference implementation of a production-grade Agentic AI
Platform for banking. Six layers and two cross-cutting concerns are implemented
so the full platform can run on a developer machine with no API key. The code is
production-shaped, but this repository is not a complete production deployment.

**Domain:** Banking / Financial Decisions
- Payment risk intervention
- Billing dispute resolution
- Churn prevention

**Test customers used throughout:**
- C001: Alexandra Chen, Prime, low risk (0.08)
- C002: Marcus Webb, Standard, HIGH RISK (0.71) — primary example
- C003: Priya Sharma, Affluent, very low risk (0.03)

### Current Implementation Scope

Implemented in this repository:
- Six-layer pipeline for payment risk intervention, billing dispute resolution,
  and churn prevention using deterministic test customers and mock/default LLM.
- FastAPI API, SSE event stream, React/Vite UI, local Docker services, typed
  Pydantic schemas, TypeScript API types, tests, metrics, traces, and audit
  replay for local runs.
- Local adapters for Valkey/Redis, PostgreSQL, Qdrant, MLflow, Ollama, LiteLLM,
  and mock channel/LLM delivery.

Not implemented in this repository:
- AWS-native production backends such as DynamoDB, S3 Object Lock, Athena,
  SageMaker, Bedrock, X-Ray, CloudWatch, EventBridge, Glue, App Mesh, and IAM.
  These remain target deployment mappings in `docs/architecture.md`.
- Production authentication/authorization, secrets management, multi-tenant
  isolation, HA deployment manifests, CI/CD, and operational alert routing.
- Real external delivery integrations such as FCM/APNS, Twilio, SendGrid, or a
  production CRM. Layer 6 uses mock channel adapters.
- Automated retraining jobs, batch scoring, model-card storage, long-retention
  cold audit archival, and scheduled MLOps workflows. Layer 5 implements local
  experiment, drift, and MLflow wrapper behavior only.
- Fraud alert execution. A fraud blueprint is documented as a catalog example,
  but the implemented/tested scenarios are the three listed above.

---

## Architecture Reference

**Before implementing any layer, read the corresponding section in
`docs/architecture.md`.**

The architecture document contains:
- The exact problem each layer solves
- Canonical Pydantic schemas (implement these exactly as specified)
- Key design decisions with rationale (do not deviate without a comment)
- Full data flow examples using Marcus Webb (C002)
- Target technology mapping tables (cloud-agnostic → AWS-native)

The architecture document is the ground truth. Code must be traceable
to its implemented-local sections and target architecture notes. If the
document says a field is named `missed_pmts`, the code
uses `missed_pmts` — not `missed_payments` or `missedPayments`.

---

## Technology Stack

Use exactly these libraries. Do not substitute without explicit instruction.

### Python Backend

```
Runtime:         Python 3.12+
Package manager: uv (not pip directly)
Config:          pyproject.toml (PEP 517/518)

Core:
  pydantic v2              All schemas and data validation
  pydantic-settings        Typed settings from environment
  python-dotenv            .env file loading
  httpx                    Async HTTP client (not aiohttp, not requests)
  asyncio                  Parallel async operations

Storage:
  redis-py (async)         Valkey/Redis client (TTL context store)
  sqlalchemy 2.0           ORM (async) for all PostgreSQL access
  alembic                  Database migrations
  psycopg[async]           PostgreSQL async driver

Vector Search:
  qdrant-client            Vector store client
  sentence-transformers    Local embeddings + cross-encoder
  rank_bm25                BM25 sparse scoring

LLM:
  litellm                  LLM provider abstraction (wraps all providers)
  anthropic                Claude SDK (used via litellm)

API:
  fastapi                  REST API + SSE endpoints
  uvicorn                  ASGI server

Data Science:
  numpy                    Numerical operations
  pandas                   DataFrame operations
  scipy                    Statistical tests (KS, Z-test, AIR)

ML Governance:
  evidently                Drift monitoring + HTML reports
  mlflow                   Model registry + experiment tracking

Observability:
  structlog                Structured JSON logging
  opentelemetry-sdk        Distributed tracing
  opentelemetry-exporter-otlp  OTLP exporter
  prometheus-client        Metrics exposition

Config:
  PyYAML                   Rule store YAML parsing
  watchdog                 Optional file watcher; current rule reload uses
                           YAML mtime polling

Testing:
  pytest                   Test runner
  pytest-asyncio           Async test support
  pytest-cov               Coverage reporting
  factory-boy              Test data factories
  respx                    Mock httpx calls
  testcontainers           Real services in CI tests
  Faker                    Realistic fake data
```

### UI Frontend

```
Runtime:         Node.js 20+
Package manager: pnpm
Build:           Vite

Core:
  react@18                 UI framework
  react-dom@18
  react-router-dom@6       Client-side routing
  typescript               Type safety (strict mode)

State:
  @tanstack/react-query    Server state + caching + polling
  zustand                  Client state (pipeline live state)

Styling:
  tailwindcss              Utility-first CSS
  @tailwindcss/typography  Prose styling

Diagrams:
  @xyflow/react            Architecture diagram (React Flow v12)
  recharts                 Charts (latency, experiments, drift)

UI Utilities:
  lucide-react             Icons
  clsx                     Conditional class names
  date-fns                 Date formatting

Dev:
  @vitejs/plugin-react
  eslint + typescript-eslint
  prettier
```

---

## Project Structure

**Never deviate from this structure.**

```
banking-agentic-platform/
│
├── AGENTS.md                    ← This file
├── TASKS.md                     ← Build task list
├── README.md
├── pyproject.toml
├── docker-compose.yml
├── Makefile
├── .env.example
├── .gitignore
│
├── docs/
│   └── architecture.md          ← Full architecture spec
│
├── platform/                    ← Python backend
│   ├── __init__.py
│   │
│   ├── core/                    ← Shared types — no external dependencies
│   │   ├── __init__.py
│   │   ├── schemas.py           All Pydantic schemas
│   │   ├── interfaces.py        Protocol classes for all adapters
│   │   ├── exceptions.py        All typed exceptions
│   │   └── config.py            Settings (pydantic-settings)
│   │
│   ├── adapters/                ← Infrastructure adapter implementations
│   │   ├── __init__.py
│   │   ├── valkey_context_store.py
│   │   ├── postgres_feature_store.py
│   │   ├── postgres_audit_writer.py
│   │   ├── postgres_queue_store.py
│   │   ├── qdrant_vector_store.py
│   │   ├── mock_llm_client.py
│   │   ├── ollama_llm_client.py
│   │   ├── litellm_client.py
│   │   ├── mock_channel_adapter.py
│   │   └── adapter_factory.py
│   │
│   ├── layer1_context/          ← Context Assembly
│   │   ├── __init__.py
│   │   ├── service.py           ContextAssemblyService
│   │   ├── normalizer.py        Schema normalization
│   │   ├── feature_store.py     Feature store pull
│   │   └── adapters/            Source system adapters (mock HTTP)
│   │       ├── card_adapter.py
│   │       ├── banking_adapter.py
│   │       ├── crm_adapter.py
│   │       └── behavioral_adapter.py
│   │
│   ├── layer2_vector/           ← Vector Search
│   │   ├── __init__.py
│   │   ├── service.py           VectorSearchService
│   │   ├── chunker.py           HierarchicalChunker
│   │   ├── embedder.py          DenseEmbedder + SparseEmbedder
│   │   ├── retriever.py         HybridRetriever (ANN + BM25 + RRF)
│   │   ├── reranker.py          CrossEncoderReranker
│   │   ├── query_builder.py     Dynamic query construction
│   │   └── kb_loader.py         Knowledge base indexer
│   │
│   ├── layer3_orchestration/    ← Multi-Agent Orchestration
│   │   ├── __init__.py
│   │   ├── orchestrator.py      Orchestrator
│   │   ├── pipeline_registry.py Static pipeline definitions
│   │   ├── tool_registry.py     Tool definitions + authorization
│   │   ├── state_manager.py     Pipeline state (Valkey)
│   │   ├── agents/
│   │   │   ├── base_agent.py
│   │   │   ├── risk_scoring_agent.py
│   │   │   ├── intervention_agent.py
│   │   │   ├── dispute_triage_agent.py
│   │   │   ├── resolution_agent.py
│   │   │   ├── churn_signal_agent.py
│   │   │   └── retention_offer_agent.py
│   │   └── prompts/
│   │       ├── risk_scoring.py
│   │       ├── intervention.py
│   │       ├── dispute_triage.py
│   │       ├── resolution.py
│   │       ├── churn_signal.py
│   │       └── retention_offer.py
│   │
│   ├── layer4_guardrails/       ← Guardrails & Policy Enforcement
│   │   ├── __init__.py
│   │   ├── service.py           GuardrailsService
│   │   ├── rule_engine.py       RuleLoader + RuleEvaluator
│   │   ├── fairness.py          BISG disparity analysis
│   │   ├── approval_queue.py    ApprovalQueueService + SLA
│   │   └── checks/
│   │       ├── regulatory.py
│   │       ├── business_policy.py
│   │       └── responsible_ai.py
│   │
│   ├── layer5_ab/               ← A/B Evaluation & Model Governance
│   │   ├── __init__.py
│   │   ├── experiment_service.py
│   │   ├── statistics.py        Statistical tests
│   │   ├── drift_monitor.py     Three-type drift detection
│   │   ├── model_registry.py    MLflow wrapper
│   │   └── outcome_processor.py Nightly batch
│   │
│   ├── layer6_sdk/              ← SDK Surface & Execution
│   │   ├── __init__.py
│   │   ├── client.py            ActionClient
│   │   ├── blueprints.py        Blueprint definitions
│   │   ├── blueprint_runner.py  Orchestrates all 6 layers
│   │   ├── outcome_router.py    Routes outcomes to L5 + L4 + audit
│   │   └── channel_adapters/
│   │       ├── mock_push.py
│   │       ├── mock_sms.py
│   │       └── mock_crm.py
│   │
│   ├── api/                     ← FastAPI application
│   │   ├── __init__.py
│   │   ├── main.py              FastAPI app + lifespan
│   │   ├── dependencies.py      Dependency injection
│   │   └── routers/
│   │       ├── pipeline.py      POST /pipeline/run, /status/{trace_id}
│   │       ├── outcomes.py      POST /outcomes/{trace_id}
│   │       ├── audit.py         GET /audit/{trace_id}
│   │       ├── experiments.py   GET /experiments
│   │       ├── guardrails.py    GET /rules, /queue
│   │       ├── models.py        GET /models
│   │       └── sse.py           GET /pipeline/events/{trace_id}
│   │
│   ├── observability/           ← Cross-cutting: logging, tracing, metrics
│   │   ├── __init__.py
│   │   ├── logging.py           structlog configuration
│   │   ├── tracing.py           OpenTelemetry setup + decorators
│   │   └── metrics.py           Prometheus metrics per layer
│   │
│   └── demo.py                  ← Standalone demo script
│
├── knowledge_base/              ← Policy documents (YAML)
│   ├── hardship_eligibility.yaml
│   ├── payment_intervention_playbook.yaml
│   ├── contact_frequency_guidelines.yaml
│   ├── dispute_resolution_reg.yaml
│   └── credit_limit_policy.yaml
│
├── rules/                       ← Guardrail rules (versioned YAML)
│   ├── regulatory/
│   │   ├── r001_udaap.yaml
│   │   ├── r002_tcpa_consent.yaml
│   │   └── r003_fcra_adverse_action.yaml
│   ├── business_policy/
│   │   ├── b001_contact_frequency.yaml
│   │   ├── b002_supervisor_threshold.yaml
│   │   └── b003_duplicate_case.yaml
│   └── responsible_ai/
│       ├── ai001_confidence_thresholds.yaml
│       ├── ai002_partial_context.yaml
│       └── ai003_consistency.yaml
│
├── alembic/                     ← Database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/
│   ├── conftest.py              Shared fixtures (containers, clients)
│   ├── fixtures/
│   │   ├── customers.py         CustomerProfile factories
│   │   ├── policies.py          PolicyChunk factories
│   │   └── pipeline_states.py   Pipeline state factories
│   ├── unit/
│   │   ├── test_schemas.py
│   │   ├── test_layer1.py
│   │   ├── test_layer2.py
│   │   ├── test_layer3.py
│   │   ├── test_layer4.py
│   │   ├── test_layer5.py
│   │   └── test_layer6.py
│   └── integration/
│       ├── test_adapters.py
│       ├── test_layer1_integration.py
│       ├── test_layer2_integration.py
│       ├── test_api.py
│       └── test_full_pipeline.py
│
└── ui/                          ← React frontend
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    ├── tailwind.config.ts
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx
        ├── api/
        │   ├── client.ts        Typed API client (fetch wrappers)
        │   └── types.ts         TypeScript types matching Pydantic schemas
        ├── components/
        │   ├── Layout.tsx
        │   ├── LayerStatusBadge.tsx
        │   ├── LatencyBar.tsx
        │   ├── CodeBlock.tsx
        │   └── SchemaViewer.tsx
        ├── pages/
        │   ├── PipelineRunner.tsx
        │   ├── ArchitectureView.tsx
        │   ├── AuditTrail.tsx
        │   ├── Experiments.tsx
        │   ├── DriftMonitor.tsx
        │   ├── GuardrailsView.tsx
        │   └── ModelRegistry.tsx
        ├── architecture/        ← Architecture View components
        │   ├── LayerNavigator.tsx
        │   ├── PlatformDiagram.tsx
        │   ├── LayerNode.tsx
        │   ├── DataFlowEdge.tsx
        │   ├── CrossCuttingBar.tsx
        │   └── LayerDetail.tsx
        ├── hooks/
        │   ├── usePipelineEvents.ts  SSE hook
        │   └── usePipelineStore.ts   Zustand store
        └── lib/
            └── utils.ts
```

---

## Coding Standards

### Python — Non-Negotiable Rules

**1. Type hints on every function signature**
```python
# CORRECT
async def assemble(
    self,
    customer_id: str,
    session_id: str,
    scenario: str,
) -> AssemblyResult:

# WRONG — no type hints
async def assemble(self, customer_id, session_id, scenario):
```

**2. Docstrings on every public class and method**
```python
class ContextAssemblyService:
    """
    Assembles a unified customer profile from multiple source systems.
    Writes result to TTL context store (Valkey) and audit log.
    Never raises on source failure — degrades gracefully.
    SLA: 200ms at p99.
    """
```

**3. Pydantic v2 for all cross-boundary data**
- Every schema defined in `platform/core/schemas.py`
- Use `model_validator` and `field_validator` not pre-v2 syntax
- `model_config = ConfigDict(frozen=True)` for immutable schemas

**4. Async throughout — no sync I/O in business logic**
```python
# CORRECT
async def fetch(self, customer_id: str) -> RawCardData:
    async with httpx.AsyncClient() as client:
        response = await client.get(...)

# WRONG — blocks the event loop
def fetch(self, customer_id: str) -> RawCardData:
    response = requests.get(...)
```

**5. Interface pattern — mandatory for every external dependency**
```python
# platform/core/interfaces.py
class ContextStore(Protocol):
    """TTL-bound key-value store for session-scoped customer profiles."""
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...

# platform/adapters/valkey_context_store.py
class ValkeyContextStore:
    """
    Implements ContextStore using Valkey (Redis-compatible).
    Production: connect to ElastiCache, OCI Redis, or GCP Memorystore
    by changing VALKEY_URL in .env — zero code changes required.
    """
    def __init__(self, url: str) -> None: ...
    async def get(self, key: str) -> Optional[str]: ...
    async def set(self, key: str, value: str, ttl: int) -> None: ...
    async def delete(self, key: str) -> None: ...
```

Business logic imports `ContextStore` (the interface), never
`ValkeyContextStore` (the adapter). Adapters are wired at startup
in `adapter_factory.py` based on `Settings`.

**6. Structured logging — always include trace_id, layer, operation**
```python
import structlog
logger = structlog.get_logger()

# CORRECT
logger.info(
    "context_assembly_complete",
    trace_id=trace_id,
    layer="L1",
    operation="assemble",
    customer_id=customer_id,
    latency_ms=elapsed,
    sources_degraded=sources_degraded,
)

# WRONG — no context, no trace_id
print(f"Assembly complete for {customer_id}")
logger.info("done")
```

**7. Never raise bare Exception**
```python
# platform/core/exceptions.py defines all exceptions
# CORRECT
raise SourceTimeoutError(
    source="CRMAdapter",
    customer_id=customer_id,
    timeout_ms=150,
)

# WRONG
raise Exception("CRM timed out")
raise ValueError("timeout")
```

**8. Graceful degradation — never let an adapter failure raise to the caller**
```python
# CORRECT
async def _fetch_source(self, adapter: SourceAdapter, customer_id: str):
    try:
        return await asyncio.wait_for(
            adapter.fetch(customer_id),
            timeout=0.150,  # 150ms
        )
    except (asyncio.TimeoutError, SourceUnavailableError) as e:
        logger.warning("source_adapter_failed", adapter=adapter.name, error=str(e))
        return None  # caller marks source as degraded

# WRONG — raises to caller
async def _fetch_source(self, adapter, customer_id):
    return await adapter.fetch(customer_id)  # can raise
```

**9. Test file for every module**
Every new Python module gets a test file created in the same commit.
No module ships without at least one test.

**10. No secrets anywhere in the codebase**
- API keys: environment variables only, never in code
- `.env` is in `.gitignore` — never committed
- `.env.example` is committed — contains no real values

### TypeScript / React — Non-Negotiable Rules

**1. Strict TypeScript — no `any`**
```typescript
// CORRECT
interface LayerState {
  id: string;
  status: "idle" | "active" | "complete" | "error";
  latencyMs: number | null;
}

// WRONG
const layer: any = { ... };
```

**2. API types mirror Pydantic schemas exactly**
- `ui/src/api/types.ts` contains TypeScript interfaces for every
  Pydantic schema in `platform/core/schemas.py`
- Field names use `camelCase` in TypeScript (FastAPI auto-converts)
- Keep them in sync — if a schema changes in Python, update TypeScript

**3. React Query for all server state**
```typescript
// CORRECT
const { data, isLoading, error } = useQuery({
  queryKey: ["audit", traceId],
  queryFn: () => api.getAudit(traceId),
  refetchInterval: isActive ? 1000 : false,
});

// WRONG — manual fetch in useEffect
useEffect(() => {
  fetch(`/audit/${traceId}`).then(...)
}, [traceId]);
```

**4. Zustand only for UI state that is not server data**
- Pipeline execution live state (active layer, animation triggers)
- Selected layer in Architecture View
- NOT: audit records, experiments, model list — those belong in React Query

**5. Tailwind only — no inline styles, no CSS modules**
```tsx
// CORRECT
<div className="flex items-center gap-3 rounded-lg border border-slate-700 bg-slate-900 p-4">

// WRONG
<div style={{ display: "flex", gap: "12px" }}>
```

---

## LLM Configuration

The platform supports three modes. **Default is always `mock`.**

```
LLM_BACKEND=mock    → MockLLMClient
                      No API key. Scripted realistic responses.
                      Exercises all downstream layers fully.
                      Default. Repo works out-of-box with this.

LLM_BACKEND=ollama  → OllamaLLMClient
                      Real local inference. No API key or cost.
                      Requires: ollama installed + model pulled
                      Set LLM_MODEL=llama3.2 (or mistral, phi3.5)
                      Set OLLAMA_BASE_URL=http://localhost:11434

LLM_BACKEND=api     → LiteLLMClient
                      Best quality. Requires API key in .env.
                      Set LLM_MODEL=claude-sonnet-4-20250514
                      or LLM_MODEL=gpt-4o
```

The `MockLLMClient` must return realistic responses that:
- Conform exactly to the expected output schema
- Reflect the customer's actual profile data (not generic text)
- Produce different outputs for different risk levels and scenarios
- Exercise all downstream platform logic (guardrails, A/B, etc.)

---

## Canonical Settings Class

**This is the single source of truth for `platform/core/config.py`.**
Implement it exactly as specified. Do not add or remove fields.

```python
# platform/core/config.py

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):

    # ── LLM ────────────────────────────────────────────────────────
    LLM_BACKEND: Literal["mock", "ollama", "api"] = "mock"
    LLM_MODEL: str = "llama3.2"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None

    # ── Infrastructure ──────────────────────────────────────────────
    VALKEY_URL: str = "redis://localhost:6379"
    POSTGRES_URL: str = (
        "postgresql+asyncpg://platform:platform@localhost:5432/platform"
    )
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "knowledge_base"
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"
    JAEGER_ENDPOINT: str = "http://localhost:4317"
    PROMETHEUS_PORT: int = 8001

    # ── Platform ────────────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # ── Rules & Knowledge Base ──────────────────────────────────────
    RULES_DIR: str = "rules"               # directory of YAML rule files
    KB_DIR: str = "knowledge_base"         # directory of YAML KB documents
    RULES_RELOAD_INTERVAL_SEC: int = 5     # rule reload polling interval

    # ── Layer 1 ─────────────────────────────────────────────────────
    CONTEXT_TTL_SECONDS: int = 300         # Redis TTL for customer profile
    SOURCE_ADAPTER_TIMEOUT_MS: int = 150   # per-adapter hard timeout

    # ── Layer 2 ─────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    RETRIEVAL_TOP_K: int = 3
    HYBRID_ALPHA: float = 0.7              # 0=pure BM25, 1=pure vector

    # ── Layer 3 ─────────────────────────────────────────────────────
    AGENT_DEFAULT_TIMEOUT_MS: int = 8000
    PIPELINE_STATE_TTL_SECONDS: int = 300  # same TTL as customer profile

    # ── Layer 5 ─────────────────────────────────────────────────────
    EXPERIMENT_MIN_SAMPLE_SIZE: int = 5000
    EXPERIMENT_CONFIDENCE_THRESHOLD: float = 0.95
    PSI_WARNING_THRESHOLD: float = 0.10
    PSI_ALERT_THRESHOLD: float = 0.25
    RECALL_ALERT_THRESHOLD: float = 0.78   # alert ML team below this

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",                    # ignore unknown env vars
        case_sensitive=True,
    )


# Singleton — import this everywhere
settings = Settings()
```

**Usage pattern throughout the codebase:**
```python
from platform.core.config import settings

# In adapter_factory.py
def create_llm_client() -> LLMClient:
    match settings.LLM_BACKEND:
        case "mock":   return MockLLMClient()
        case "ollama": return OllamaLLMClient(
                           model=settings.LLM_MODEL,
                           base_url=settings.OLLAMA_BASE_URL
                       )
        case "api":    return LiteLLMClient(model=settings.LLM_MODEL)

# In layer1_context/service.py
async def _fetch_with_timeout(adapter, customer_id):
    timeout = settings.SOURCE_ADAPTER_TIMEOUT_MS / 1000
    return await asyncio.wait_for(adapter.fetch(customer_id), timeout=timeout)
```

---

## Docker Services (docker-compose.yml)

All seven services. Every service has a health check.

```yaml
valkey:
  image: valkey/valkey:8-alpine
  ports: ["6379:6379"]
  # Redis-compatible. Drop-in open-source replacement.

postgres:
  image: postgres:16-alpine
  ports: ["5432:5432"]
  environment:
    POSTGRES_DB: platform
    POSTGRES_USER: platform
    POSTGRES_PASSWORD: platform

qdrant:
  image: qdrant/qdrant:v1.9.4
  ports: ["6333:6333", "6334:6334"]
  volumes: ["qdrant_data:/qdrant/storage"]

jaeger:
  image: jaegertracing/all-in-one:1.57
  ports: ["16686:16686", "4317:4317"]
  # Trace UI at http://localhost:16686

prometheus:
  image: prom/prometheus:v2.52.0
  ports: ["9090:9090"]
  volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml"]

grafana:
  image: grafana/grafana:11.0.0
  ports: ["3000:3000"]
  # Dashboard UI at http://localhost:3000

mlflow:
  image: ghcr.io/mlflow/mlflow:v2.14.1
  ports: ["5001:5000"]
  # Uses SQLite backend for local dev — no psycopg2 dependency.
  # Model registry UI at http://localhost:5001
```

---

## Environment Variables

All variables are in `.env.example`. Copy to `.env` to override.
Defaults work with docker-compose out of the box.

```bash
# LLM (default: mock — no key required)
LLM_BACKEND=mock
LLM_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434   # only if LLM_BACKEND=ollama
# ANTHROPIC_API_KEY=sk-ant-...           # only if LLM_BACKEND=api
# OPENAI_API_KEY=sk-...                  # only if LLM_BACKEND=api + OpenAI

# Infrastructure (defaults match docker-compose.yml)
VALKEY_URL=redis://localhost:6379
POSTGRES_URL=postgresql+asyncpg://platform:platform@localhost:5432/platform
QDRANT_URL=http://localhost:6333
MLFLOW_TRACKING_URI=http://localhost:5001
JAEGER_ENDPOINT=http://localhost:4317
PROMETHEUS_PORT=8001

# Platform
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## Makefile Targets

```makefile
install      uv sync + pnpm install in ui/
dev          Start API (uvicorn) + UI dev server (vite) + docker services
test         pytest tests/ -v --cov=platform
test-unit    pytest tests/unit/ -v
test-int     pytest tests/integration/ -v
lint         ruff check platform/ ui/src/
typecheck    mypy platform/ + tsc --noEmit in ui/
format       ruff format platform/ + prettier --write ui/src/
docker-up    docker-compose up -d
docker-down  docker-compose down
migrate      alembic upgrade head
demo         python -m platform.demo
clean        Remove __pycache__, .pytest_cache, coverage files
```

---

## Definition of Done

**A task is complete when ALL of the following are true:**

1. `make test` passes — zero test failures
2. `make typecheck` passes — zero type errors
3. `make lint` passes — zero lint errors
4. `docker-compose up -d` + `python -m platform.demo` runs end-to-end
5. No API keys or secrets in any committed file
6. Every new module has a corresponding test file
7. Every public class and method has a docstring
8. All field names match exactly what is specified in `docs/architecture.md`

---

## Key Architecture Decisions (Never Override These)

These are structural — changing them breaks the design:

| Decision | Rule |
|----------|------|
| Context store write | Always `NX=True` — fail on duplicate session |
| Context store TTL | Always 300 seconds — enforced by Valkey, not app code |
| Agent actions | Agents PROPOSE only — never execute against customer systems |
| Tool authorization | Enforced by tool_registry before any call — not by prompt |
| Hub-and-spoke | Agents never call each other — always through Orchestrator |
| Partial context | Never fail on source timeout — mark degraded, continue |
| Audit records | Written to PostgreSQL, never updated after insert |
| LLM default | Always `mock` — repo must run with zero API key |
| Feature versioning | Model trained on feature vN must serve on feature vN |
| Guardrail sequence | REGULATORY → BUSINESS → AI — regulatory block stops all |

---

*This file is version-controlled. Changes to coding standards or
technology choices are made here first, then propagated to all tasks.*
