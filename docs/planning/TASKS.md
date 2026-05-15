# TASKS.md — Banking Agentic AI Platform

> Build tasks for Codex. Complete in order.
> Each task is one Codex prompt (see PROMPT TEMPLATE at the bottom).
> All acceptance criteria must pass before the next task begins.
> Read AGENTS.md and docs/architecture.md before every task.

---

## Current Repository Status

Tasks 01 through 15 have been implemented for the local reference
application. The current repo runs the full six-layer pipeline for the three
supported scenarios with mock/default LLM behavior and local Docker services.

The following production-target capabilities described in the task prompts or
architecture notes are not implemented in this repository:
- AWS-native storage and operations: DynamoDB, S3 Object Lock, Athena,
  SageMaker, Bedrock, X-Ray, CloudWatch, EventBridge, Glue, App Mesh, and IAM.
- Production authentication/authorization, multi-tenant isolation, CI/CD,
  deployment manifests, secret-manager integration, and alert routing.
- Real outbound channel integrations such as FCM/APNS, Twilio, SendGrid, or
  production CRM writes. Current execution uses mock channel adapters.
- Long-retention cold audit storage, Object Lock immutability, and Athena-style
  replay queries. Local audit is PostgreSQL for adapter tests and process-local
  memory for the demo/API runner.
- Automated retraining pipelines, scheduled batch scoring, model-card storage,
  and production MLOps workflows. Layer 5 implements local experiment tracking,
  drift calculations, and an MLflow wrapper.
- Fraud alert execution. The catalog may mention it as a future/example
  blueprint, but only payment risk, billing dispute, and churn prevention are
  implemented and tested end to end.

---

## TASK 01 — Repo Scaffold

Create the complete project skeleton with no implementation logic.
Everything downstream depends on this structure being correct.

### Starter Files Already Provided

The following files are already in the repo root — **do not recreate them,
use them as the starting point:**

- `pyproject.toml` — all Python dependencies pre-specified with pinned versions.
  Add any missing items but do not change existing pinned versions.
- `docker-compose.yml` — all 7 services with health checks configured.
  Do not modify service definitions.
- `prometheus.yml` — Prometheus scrape config. Do not modify.
- `grafana/provisioning/` — datasource and dashboard provider configs.
- the mini platform prototype in `prototype/` — working platform demo (reference for UI)
- the architecture diagram prototype in `prototype/` — static architecture diagram (reference for UI)

Task 01 work is everything **not** in the list above.

### Deliverables

**Python project:**
- `pyproject.toml` — all dependencies from AGENTS.md tech stack,
  project metadata, tool configuration (mypy, ruff, pytest, coverage)
- `Makefile` — all targets from AGENTS.md
- `alembic/` — migration scaffold (env.py, script.py.mako)
- `alembic/versions/001_initial_schema.py` — tables:
  `feature_store`, `audit_log`, `approval_queue`, `experiments`,
  `experiment_variants`, `experiment_results`, `outcome_events`
  (see docs/architecture.md for field details per table)
- All `__init__.py` files for every Python package directory
- All placeholder `.py` files (empty, with module docstring only) for
  every file listed in the project structure in AGENTS.md

**Docker:**
- `docker-compose.yml` — all 7 services with health checks
- `prometheus.yml` — scrape config for platform API metrics endpoint
- `grafana/provisioning/` — datasource + dashboard provisioning

**UI:**
- `ui/package.json` — all dependencies from AGENTS.md
- `ui/tsconfig.json` — strict TypeScript config
- `ui/vite.config.ts` — dev server proxy to API on port 8000
- `ui/tailwind.config.ts`
- `ui/index.html`
- `ui/src/main.tsx` — React root
- `ui/src/App.tsx` — React Router with placeholder routes for all 7 pages
- Empty placeholder files for all components and pages listed in AGENTS.md
  (each with a TypeScript comment describing what it will contain)

**Config:**
- `.env.example` — all variables documented with comments
- `.gitignore` — excludes .env, __pycache__, .venv, node_modules,
  *.pyc, .mypy_cache, .ruff_cache, dist/, build/, coverage/
- `README.md` — Quick Start section (see below)

**README.md Quick Start section must contain:**
```
## Quick Start — No API Key Required

git clone https://github.com/your-org/banking-agentic-platform
cd banking-agentic-platform
make install
make docker-up
cp .env.example .env
make demo

# Output: full pipeline trace for Marcus Webb (C002)
# No API key. No external service. Runs entirely locally.

## Optional: Real LLM Inference

# Local model (free, no account)
brew install ollama && ollama pull llama3.2
echo "LLM_BACKEND=ollama" >> .env && make demo

# Cloud API (requires key)
echo "LLM_BACKEND=api" >> .env
echo "ANTHROPIC_API_KEY=your-key" >> .env
make demo
```

### Acceptance Criteria

- [ ] `make docker-up` — all 7 services start, all health checks pass
- [ ] `make install` — completes without error (uv sync + pnpm install)
- [ ] `make test` — pytest collects 0 tests, 0 failures
- [ ] `make typecheck` — 0 type errors (empty placeholder files)
- [ ] `make lint` — 0 lint errors
- [ ] `npm run dev` in `ui/` — Vite starts on port 5173 without error
- [ ] All 7 placeholder routes render without console errors

---

## TASK 02 — Core Schemas and Interfaces

Implement all shared types. No logic — schemas and interfaces only.
Everything in layers 1–6 imports from here.

Read `docs/architecture.md` Layers 1–6 schema sections before starting.
Every field name, type, and default must match exactly.

### Deliverables

**`platform/core/schemas.py`**

All Pydantic v2 models. Key schemas (see docs/architecture.md for all fields):

```python
# Customer Profile (Layer 1)
class Segment(str, Enum): STANDARD, PRIME, AFFLUENT, PRIVATE
class Channel(str, Enum): MOBILE, WEB, PHONE, BRANCH
class CardProfile(BaseModel): ...
class BankingProfile(BaseModel): ...
class CRMProfile(BaseModel): ...      # Optional — None when CRM degraded
class BehavioralProfile(BaseModel): ...
class ModelSignals(BaseModel): ...    # includes model_versions: dict
class CustomerProfile(BaseModel): ...  # includes sources_degraded, partial_context

# Service results
class AssemblyResult(BaseModel): ...
class RetrievalResult(BaseModel): ...
class PolicyChunk(BaseModel): ...

# Agent schemas
class AgentContext(BaseModel): ...    # includes authorized_tools list
class RiskAssessment(BaseModel): ...  # output of RiskScoringAgent
class InterventionProposal(BaseModel): ...  # output of InterventionAgent
class ProposedAction(BaseModel): ...  # ACT-001, ACT-002

# Guardrails
class CheckResult(BaseModel): ...    # APPROVED | FLAGGED | BLOCKED
class GuardrailsResult(BaseModel): ...
class ApprovalQueueItem(BaseModel): ... # includes sla_deadline, priority

# A/B
class ExperimentVariant(BaseModel): ...
class ExperimentResult(BaseModel): ...

# Execution
class ExecutionResult(BaseModel): ...
class OutcomeEvent(BaseModel): ...   # PUSH_OPENED | ENROLLED | IGNORED | etc.

# Audit
class AuditRecord(BaseModel): ...    # base + event_type discriminator
```

**`platform/core/interfaces.py`**

Protocol classes (no implementation):
```python
class ContextStore(Protocol): ...
class FeatureStore(Protocol): ...
class AuditWriter(Protocol): ...
class QueueStore(Protocol): ...
class VectorStore(Protocol): ...
class LLMClient(Protocol): ...       # async complete(system, user, schema) -> dict
class ChannelAdapter(Protocol): ...  # async send(action) -> DeliveryReceipt
```

**`platform/core/exceptions.py`**

All typed exceptions:
```python
class PlatformError(Exception): ...        # base
class SourceTimeoutError(PlatformError): ...
class SourceUnavailableError(PlatformError): ...
class SessionExpiredError(PlatformError): ...
class DuplicateSessionError(PlatformError): ...
class SchemaValidationError(PlatformError): ...
class ToolAuthorizationError(PlatformError): ...
class GuardrailBlockError(PlatformError): ...
class PipelineError(PlatformError): ...
```

**`platform/core/config.py`**

```python
class Settings(BaseSettings):
    # LLM
    LLM_BACKEND: Literal["mock", "ollama", "api"] = "mock"
    LLM_MODEL: str = "llama3.2"
    ANTHROPIC_API_KEY: Optional[SecretStr] = None
    OPENAI_API_KEY: Optional[SecretStr] = None

    # Infrastructure
    VALKEY_URL: str = "redis://localhost:6379"
    POSTGRES_URL: str = "postgresql+asyncpg://platform:platform@localhost:5432/platform"
    QDRANT_URL: str = "http://localhost:6333"
    MLFLOW_TRACKING_URI: str = "http://localhost:5001"
    JAEGER_ENDPOINT: str = "http://localhost:4317"

    # Platform
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

**`ui/src/api/types.ts`**

TypeScript interfaces mirroring every Pydantic schema.
Use `camelCase` (FastAPI serializes snake_case → camelCase automatically).

### Acceptance Criteria

- [ ] `make typecheck` — 0 errors
- [ ] `make lint` — 0 errors
- [ ] `pytest tests/unit/test_schemas.py -v` — all pass
  Tests must cover: valid data accepted, invalid data rejected,
  optional fields default correctly, enums reject invalid values
- [ ] TypeScript types compile: `cd ui && npx tsc --noEmit`

---

## TASK 03 — Infrastructure Adapters

Implement all adapter classes. Business logic in layers 1–6 uses only
interfaces (from Task 02) — never concrete adapters directly.

### Deliverables

**`platform/adapters/valkey_context_store.py`**
- `ValkeyContextStore` implementing `ContextStore`
- `get()`: returns None if key missing (TTL expired)
- `set()`: uses `EX=ttl`, `NX=True` — raises `DuplicateSessionError` if key exists
- `delete()`: silently succeeds if key missing
- Connection pooled via `redis.asyncio.ConnectionPool`

**`platform/adapters/postgres_feature_store.py`**
- `PostgresFeatureStore` implementing `FeatureStore`
- Tables: `feature_store` (customer_id, feature_name, value, computed_at, model_version)
- `get_signals(customer_id)` → `ModelSignals`
- `upsert_signals(customer_id, signals)` → used by batch jobs

**`platform/adapters/postgres_audit_writer.py`**
- `PostgresAuditWriter` implementing `AuditWriter`
- `write(record: AuditRecord)` — INSERT with `ON CONFLICT DO NOTHING`
  (audit_id is unique — idempotent writes)
- Never updates. Never deletes.

**`platform/adapters/postgres_queue_store.py`**
- `PostgresQueueStore` implementing `QueueStore`
- `enqueue(item: ApprovalQueueItem)` → persists item
- `dequeue_pending(priority, limit)` → items past SLA first
- `update_decision(queue_id, decision, reason)` → marks APPROVED/REJECTED

**`platform/adapters/qdrant_vector_store.py`**
- `QdrantVectorStore` implementing `VectorStore`
- Collection: `knowledge_base`
- `upsert(chunks: list[PolicyChunk])` — stores dense + sparse vectors
- `search(dense_vector, sparse_vector, filter, top_k)` → `list[PolicyChunk]`
- Metadata filter support: `product_line`, `jurisdiction`, `document_type`

**`platform/adapters/mock_llm_client.py`**
- `MockLLMClient` implementing `LLMClient`
- Scripted realistic responses for all 3 customers × 3 scenarios
- Routes based on keywords in `user_message` (risk signals, scenario name)
- Returns dict that validates against the requested `schema`
- C002 payment_risk → CRITICAL risk, hardship eligible
- C001 payment_risk → LOW risk, no intervention needed
- C003 any scenario → LOW risk, monitoring only

**`platform/adapters/ollama_llm_client.py`**
- `OllamaLLMClient` implementing `LLMClient`
- POST to `{OLLAMA_BASE_URL}/api/chat` with `format: "json"`
- 120s timeout
- Parses JSON response, validates against schema

**`platform/adapters/litellm_client.py`**
- `LiteLLMClient` implementing `LLMClient`
- Uses `litellm.acompletion()` with `response_format={"type": "json_object"}`
- Reads API key from Settings (never hardcoded)
- Strips ```json fences before JSON parsing

**`platform/adapters/mock_channel_adapter.py`**
- `MockPushAdapter`, `MockSMSAdapter`, `MockCRMAdapter`
  all implementing `ChannelAdapter`
- Log delivery to structlog
- Write delivery record to `audit_log` table
- Return `DeliveryReceipt` with `status="DELIVERED"` and timestamp

**`platform/adapters/adapter_factory.py`**
- `create_context_store(settings)` → `ContextStore`
- `create_feature_store(settings)` → `FeatureStore`
- `create_audit_writer(settings)` → `AuditWriter`
- `create_queue_store(settings)` → `QueueStore`
- `create_vector_store(settings)` → `VectorStore`
- `create_llm_client(settings)` → `LLMClient`
- `create_channel_adapter(channel_type, settings)` → `ChannelAdapter`

### Acceptance Criteria

- [ ] `pytest tests/integration/test_adapters.py -v` — all pass
  Uses testcontainers for real Valkey, PostgreSQL, Qdrant instances.
  Tests: Valkey TTL expiry, NX write semantics, PostgreSQL CRUD,
  Qdrant upsert + search + metadata filter, Mock LLM schema conformance
- [ ] Mock LLM returns valid schema for all 3 customers × 3 scenarios
- [ ] `make typecheck` — 0 errors

---

## TASK 04 — Layer 1: Context Assembly

Read `docs/architecture.md` LAYER 1 section fully before implementing.

### Key Design Decisions (from architecture doc)

- Parallel fetch: `asyncio.gather()` with 150ms timeout per adapter
- Graceful degradation: timeout marks source degraded, never raises to caller
- Valkey write: `EX=300, NX=True` — raises `DuplicateSessionError` if collision
- Feature store pull: fires in parallel with normalization (not sequential)
- Profile hash: SHA-256 of profile JSON — written to audit record
- session_id format: `sess_{customer_id}_{yyyymmdd}_{hhmmss}_{random_6}`

### Deliverables

**`platform/layer1_context/adapters/`** — four mock source adapters

Each adapter simulates a real external system with realistic latency:
```python
class CardSystemAdapter:
    """
    Simulates the Card System API.
    Real latency: ~40ms. Mock latency: asyncio.sleep(0.038).
    Returns raw card data (field names match source system, not canonical).
    """
    async def fetch(self, customer_id: str) -> dict:
        await asyncio.sleep(0.038)
        # Return customer-specific data from a fixtures dict
        # C002: balance=3800, limit=5000, missed_pmts_90d=2, etc.
```

CRM adapter simulates timeout for C002 in payment_risk scenario:
```python
class CRMAdapter:
    async def fetch(self, customer_id: str) -> dict:
        await asyncio.sleep(0.160)  # Exceeds 150ms timeout
        # This sleep is intentional — tests the timeout path
```

**`platform/layer1_context/normalizer.py`**
- Maps raw source field names → canonical schema field names
- Computes derived fields (utilization = balance/limit)
- Drops internal system IDs
- Returns typed sub-schemas (CardProfile, BankingProfile, etc.)

**`platform/layer1_context/feature_store.py`**
- `pull_signals(customer_id, feature_store)` → `ModelSignals`
- Includes model_versions in the returned signals
- Simulates ~7ms latency

**`platform/layer1_context/service.py`** — main entry point
```python
class ContextAssemblyService:
    async def assemble(
        self, customer_id: str, session_id: str, scenario: str
    ) -> AssemblyResult:
        # 1. Fire all 4 adapters in parallel with 150ms timeout
        # 2. Record which sources succeeded and which degraded
        # 3. Normalize available data to canonical schema
        # 4. Pull feature store signals (parallel with normalization)
        # 5. Merge into CustomerProfile
        # 6. Write to Valkey (NX=True, EX=300)
        # 7. Write audit record
        # 8. Return AssemblyResult (session_id, partial_context, latency_ms)
```

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer1.py -v` — all pass
- [ ] `pytest tests/integration/test_layer1_integration.py -v` — all pass
  Uses testcontainers (Valkey + PostgreSQL)
- [ ] Demo: `python -m platform.demo` shows:
  - All 4 adapter fetches with individual latencies
  - CRM timeout warning for C002
  - "partial_context: True, sources_degraded: ['crm']"
  - Valkey write confirmed with session key
  - Audit record ID printed
- [ ] Total assembly latency < 200ms for C002 (CRM times out at 150ms)
- [ ] Assembly succeeds even when all 4 adapters are down (all degraded)

---

## TASK 05 — Layer 2: Vector Search

Read `docs/architecture.md` LAYER 2 section + all four deep dives fully.

### Key Design Decisions

- Chunking: hierarchical (document → section → paragraph levels)
- Hybrid search: dense (sentence-transformers) + sparse (rank_bm25) + RRF merge
- Re-ranking: cross-encoder on top-20 candidates
- Query: dynamically constructed from CustomerProfile signals
- KB version: date string (YYYY-MM-DD) tracked in audit record

### Deliverables

**`knowledge_base/`** — five policy YAML documents

Each document has three levels of content (document, sections, paragraphs):
```yaml
# hardship_eligibility.yaml
document_id: KB-HARD-001
title: "Hardship Program Eligibility Criteria"
document_type: POLICY
product_line: credit_card
jurisdiction: US
version: "2.3"
effective_date: "2026-01-01"
content:
  summary: "Policy covering eligibility criteria, program terms..."
  sections:
    - title: "Eligibility Requirements"
      content: "Customers with 2 or more missed payments..."
      paragraphs:
        - "Customers with 2+ missed payments in a 90-day window..."
        - "Checking balance must be below $500..."
```

**`platform/layer2_vector/chunker.py`**
- `HierarchicalChunker.chunk(document)` → `list[PolicyChunk]`
- Three chunk types: DOCUMENT (summary), SECTION, PARAGRAPH
- Each chunk carries parent references for hierarchy traversal
- chunk_id format: `{doc_id}-{version}-{type}-{index}`

**`platform/layer2_vector/embedder.py`**
- `DenseEmbedder` — sentence-transformers `all-MiniLM-L6-v2`
- `SparseEmbedder` — rank_bm25 (fit on full KB corpus at load time)
- Both accept `list[str]` → return list of vectors

**`platform/layer2_vector/retriever.py`**
- `HybridRetriever.search(dense_q, sparse_q, filter, top_k=20)`
- Runs ANN search (Qdrant) + BM25 scoring in parallel
- RRF merge: `score = sum(1 / (60 + rank))` for each result list
- Returns top-20 merged candidates

**`platform/layer2_vector/reranker.py`**
- `CrossEncoderReranker.rerank(query, candidates, top_k=3)`
- Model: `cross-encoder/ms-marco-MiniLM-L-6-v2`
- Returns top-k re-ranked `PolicyChunk` list with scores

**`platform/layer2_vector/query_builder.py`**
- `build_retrieval_query(profile: CustomerProfile, scenario: str) -> str`
- Constructs natural language query from profile signals
- Different templates per scenario
- C002 payment_risk produces:
  "Customer with critical payment risk. 2 missed payments,
  checking balance $312.40, no direct deposit. Utilization 76%.
  Payment propensity 31%. Hardship program eligibility, intervention
  options, payment deferral, contact frequency."

**`platform/layer2_vector/kb_loader.py`**
- `KnowledgeBaseLoader.load_and_index()` — called at API startup
- Reads all YAML files from `knowledge_base/`
- Chunks, embeds, upserts to Qdrant
- Tracks kb_version (today's date) in Qdrant collection metadata

**`platform/layer2_vector/service.py`**
```python
class VectorSearchService:
    async def retrieve(
        self, session_id: str, scenario: str, top_k: int = 3
    ) -> RetrievalResult:
        # 1. Read CustomerProfile from Valkey (consumer — never writes)
        # 2. Build retrieval query from profile + scenario
        # 3. Embed query (dense + sparse)
        # 4. Metadata pre-filter
        # 5. Hybrid ANN + BM25 → RRF merge → top-20
        # 6. Cross-encoder re-rank → top-3
        # 7. Write audit record
        # 8. Return RetrievalResult
```

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer2.py -v` — all pass
- [ ] `pytest tests/integration/test_layer2_integration.py -v` — all pass
  (Qdrant testcontainer)
- [ ] C002 payment_risk query returns KB-HARD-001 as top-1 result
- [ ] Hybrid search outperforms pure vector on exact term "section 1005.11"
  (test that BM25 correctly surfaces the regulation document)
- [ ] KB loads successfully from all 5 YAML files on startup

---

## TASK 06 — Layer 3: Multi-Agent Orchestration

Read `docs/architecture.md` LAYER 3 section fully.

### Key Design Decisions

- Hub-and-spoke: `pipeline_registry.py` defines static pipelines
- Agents never call each other — only through Orchestrator
- Tool authorization checked by registry BEFORE the tool call executes
- Agents PROPOSE only — never execute against customer systems
- Pipeline state checkpointed to Valkey after every step
- All failures (timeout, schema error, tool auth violation) → `HumanReviewQueue`

### Deliverables

**`platform/layer3_orchestration/tool_registry.py`**
```python
# Tool definitions with per-agent authorization
TOOLS = {
    "read_customer_profile": ToolDefinition(
        authorized_agents=["RiskScoringAgent", "InterventionAgent", ...],
        mode="read_only",
        description="Read unified customer profile from context store",
    ),
    "query_transaction_history": ToolDefinition(
        authorized_agents=["RiskScoringAgent"],
        mode="read_only",
        description="Retrieve last 90 days of transactions",
    ),
    "propose_intervention": ToolDefinition(
        authorized_agents=["InterventionAgent"],
        mode="propose_only",
        description="Propose an intervention action (does not execute)",
    ),
    # ... all tools
}

def authorize_tool_call(agent_name: str, tool_name: str) -> None:
    """Raises ToolAuthorizationError if agent is not authorized."""
```

**`platform/layer3_orchestration/pipeline_registry.py`**
```python
PIPELINES = {
    "payment_risk_intervention": Pipeline(
        steps=[
            PipelineStep(
                agent="RiskScoringAgent",
                timeout_ms=8000,
                output_schema=RiskAssessment,
                on_failure="human_review",
            ),
            BranchStep(
                condition=lambda output: output.risk_level in ["HIGH", "CRITICAL"],
                if_true="InterventionAgent",
                if_false="MonitoringAgent",
            ),
            PipelineStep(
                agent="InterventionAgent",
                timeout_ms=10000,
                output_schema=InterventionProposal,
                on_failure="human_review",
            ),
        ]
    ),
    "billing_dispute_resolution": Pipeline(...),
    "churn_prevention": Pipeline(...),
}
```

**`platform/layer3_orchestration/agents/base_agent.py`**
```python
class BaseAgent:
    """
    Base class for all specialized agents.
    Subclasses override: system_prompt_template, output_schema.
    Never override: run() — it enforces tool authorization.
    """
    async def run(self, context: AgentContext, llm: LLMClient) -> AgentOutput:
        # 1. Build system prompt from template + policy chunks
        # 2. Build user message from customer profile + prior outputs
        # 3. Execute LLM call
        # 4. Validate output against output_schema
        # 5. Return AgentOutput
```

**Six agent implementations** — each defines:
- `system_prompt_template`: str (includes tool list, output schema, policy context)
- `output_schema`: type (RiskAssessment, InterventionProposal, etc.)
- Any agent-specific pre/post processing

**`platform/layer3_orchestration/orchestrator.py`**
```python
class Orchestrator:
    async def run_pipeline(
        self,
        session_id: str,
        scenario: str,
        policy_chunks: list[PolicyChunk],
        trace_id: str,
    ) -> OrchestratorOutput:
        # 1. Load pipeline definition from registry
        # 2. For each step:
        #    a. Assemble AgentContext
        #    b. Run agent (with timeout)
        #    c. Validate output schema
        #    d. Checkpoint state to Valkey
        #    e. Evaluate branch condition if applicable
        #    f. On any failure → enqueue to HumanReviewQueue
        # 3. Write orchestration audit record
        # 4. Return OrchestratorOutput (proposed_actions)
```

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer3.py -v` — all pass (mock LLM)
- [ ] C002 payment_risk pipeline executes all steps in order
- [ ] Branch decision logs correctly (CRITICAL → InterventionAgent)
- [ ] `ToolAuthorizationError` raised when InterventionAgent attempts
  to call "execute_payment_deferral" (not in its authorized list)
- [ ] Agent timeout (>8000ms) routes to HumanReviewQueue
- [ ] Schema validation failure routes to HumanReviewQueue
- [ ] Pipeline state checkpointed after each step (verify in Valkey)
- [ ] `make typecheck` — 0 errors

---

## TASK 07 — Layer 4: Guardrails & Policy Enforcement

Read `docs/architecture.md` LAYER 4 section + all four deep dives fully.

### Key Design Decisions

- YAML rule store — reloads through file mtime polling (< 5 second reload)
- Three categories in strict sequence: REGULATORY → BUSINESS → AI
- Regulatory BLOCK stops immediately — no further checks run
- Fairness: BISG proxy methodology (scipy statistical tests)
- Confidence thresholds are per-action-type + 0.05 for partial context
- Approval queue: SLA tiers (URGENT=30min, HIGH=2hr, STANDARD=4hr, LOW=24hr)

### Deliverables

**`rules/`** — nine YAML rule files (three per category)

Rule schema:
```yaml
rule_id: B-002
name: "Supervisor Approval Threshold"
category: BUSINESS_POLICY
version: "3.1"
effective_date: "2026-01-01"
expires_date: null
condition:
  action_type: CREATE_HARDSHIP_ENROLLMENT_CASE
  field: amount
  operator: GREATER_THAN
  value: 5000
outcome: FLAG
severity: MEDIUM
flag_message: "Deferral amount exceeds $5,000 — supervisor approval required"
```

**`platform/layer4_guardrails/rule_engine.py`**
- `RuleLoader` — loads YAML files from `rules/`, watches for changes
- `RuleEvaluator.evaluate(action, profile, rules)` → `list[CheckResult]`
- Applies rules in category sequence: REGULATORY first
- Stops evaluating if any regulatory rule returns BLOCKED

**`platform/layer4_guardrails/fairness.py`**
- `BisgFairnessChecker.check(action_type, customer_segment, db_session)`
- Queries historical decisions from `audit_log` table (last 30 days)
- Computes offer rate per cohort (approximated by segment + zip bucket)
- Calculates Adverse Impact Ratio (AIR)
- Returns APPROVED if AIR >= 0.80, FLAGGED if AIR < 0.80

**`platform/layer4_guardrails/checks/responsible_ai.py`**
- `ConfidenceCheck.check(action, agent_confidence, partial_context)` →
  threshold from ai001 YAML + 0.05 modifier if partial_context=True
- `ConsistencyCheck.check(risk_assessment, profile)` →
  validates CRITICAL risk has ≥ 2 supporting signals
- `AnomalyCheck.check(action_type, recent_actions_db)` →
  flags if action type distribution deviates > 3-sigma from 7d baseline

**`platform/layer4_guardrails/service.py`**
```python
class GuardrailsService:
    async def evaluate(
        self, orchestrator_output: OrchestratorOutput, session_id: str
    ) -> GuardrailsResult:
        # For each proposed action:
        # 1. Run REGULATORY checks (stop if BLOCKED)
        # 2. Run BUSINESS_POLICY checks (accumulate flags)
        # 3. Run RESPONSIBLE_AI checks (accumulate flags)
        # 4. Determine disposition: APPROVED | FLAGGED | BLOCKED
        # 5. If FLAGGED: enqueue to approval queue
        # 6. Write guardrails audit record (with rule versions used)
        # 7. Return GuardrailsResult
```

**`platform/layer4_guardrails/approval_queue.py`**
- `ApprovalQueueService.enqueue(action, flags, context, priority)`
- Priority derived from flag severity + risk level
- SLA deadline set at enqueue time based on priority tier
- `get_pending(limit)` — returns items sorted by SLA urgency
- `record_decision(queue_id, decision, reason)` → routes feedback

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer4.py -v` — all pass
- [ ] ACT-001 (push notification) returns APPROVED (8/8 checks)
- [ ] ACT-002 (hardship case $420) returns FLAGGED with reasons:
  "B-002: standard approval" + "AI-002: CRM unavailable on account action"
- [ ] Regulatory BLOCK stops evaluation immediately (verify B-001 not run)
- [ ] Rule reload: change a YAML threshold, verify new value applied
  within 5 seconds without restart
- [ ] Fairness check: balanced test data returns APPROVED
- [ ] Confidence check: confidence 0.65 on CREATE_HARDSHIP fails threshold
- [ ] Approval queue item created with correct SLA deadline for STANDARD priority

---

## TASK 08 — Layer 5: A/B Evaluation & Model Governance

Read `docs/architecture.md` LAYER 5 section fully.

### Key Design Decisions

- Variant assignment: `hash(customer_id + experiment_id) % 100`
  — deterministic, same customer always gets same variant
- Conclude when: `confidence >= 0.95 AND n >= min_sample_size`
- PSI thresholds: 0.10 (monitor), 0.25 (investigate/retrain)
- MLflow for model registry with champion/challenger as model tags

### Deliverables

**`platform/layer5_ab/statistics.py`**
```python
def z_test_proportions(n_a, conv_a, n_b, conv_b) -> tuple[float, float]:
    """Returns (z_score, p_value) for two-proportion z-test."""

def calculate_psi(expected: np.ndarray, actual: np.ndarray, bins=10) -> float:
    """Population Stability Index. Returns float (0=stable, >0.25=major shift)."""

def calculate_air(rate_protected: float, rate_reference: float) -> float:
    """Adverse Impact Ratio. Returns float (1.0=equal, <0.80=adverse impact)."""

def ks_test(reference: np.ndarray, current: np.ndarray) -> tuple[float, float]:
    """Kolmogorov-Smirnov test. Returns (statistic, p_value)."""
```

**`platform/layer5_ab/experiment_service.py`**
```python
class ExperimentService:
    def select_variant(
        self, customer_id: str, scenario: str, action_type: str
    ) -> ExperimentVariant:
        # 1. Load active experiment for this scenario + action_type
        # 2. If experiment concluded → always return winner
        # 3. Check if leader meets confidence + sample size thresholds
        # 4. Fall back to hash-based assignment
        # 5. Write AB_ASSIGNMENT audit record
        # 6. Return selected variant

    def record_outcome(self, experiment_id: str, variant_id: str, outcome: str):
        # Update variant result counts
        # Recalculate confidence using z_test_proportions
        # Check if experiment should conclude (confidence + sample size)
        # If concludes: write winner to experiment record
```

**`platform/layer5_ab/drift_monitor.py`**
- `FeatureDriftMonitor.check(model_id, feature_name)` → uses evidently
- `PredictionDriftMonitor.check(model_id)` → PSI on score distribution
- `PerformanceDriftMonitor.check(model_id)` → rolling 30d recall (requires outcome data)
- Generates evidently HTML reports to `reports/{model_id}_{date}.html`

**`platform/layer5_ab/model_registry.py`**
- Thin wrapper around MLflow
- `register_model(model_id, version, metrics)` → MLflow run + model version
- `promote_to_champion(model_id, version)` → sets "champion" tag
- `get_current_champion(model_id)` → returns version string
- Seed three models (risk, churn, payment_propensity) with initial versions on startup

**Bootstrap data:** Seed `experiments` table with one active experiment:
```python
# exp_payment_message_v3
# Variant A: soft framing (current leader, 8420 samples, 41% conversion)
# Variant B: direct framing (8380 samples, 34% conversion)
# Status: RUNNING (not yet concluded — tests verify conclusion logic)
```

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer5.py -v` — all pass
- [ ] `hash("C002" + "exp_payment_message_v3") % 100 == 34` → Variant A
- [ ] Same customer always gets same variant (50 random customer_ids tested)
- [ ] PSI calculation verified: known distribution shift produces PSI > 0.25
- [ ] AIR calculation: equal rates → 1.0, 40% disparity → 0.6
- [ ] MLflow: model registration + champion promotion tested
- [ ] Evidently: drift report generated without error

---

## TASK 09 — Layer 6: SDK Surface & Execution

Read `docs/architecture.md` LAYER 6 section fully.

### Deliverables

**`platform/layer6_sdk/blueprints.py`** — four blueprints
```python
class BlueprintConfig:
    name: str
    scenario: str
    agents: list[str]
    channels: list[str]
    description: str

PAYMENT_RISK_INTERVENTION = BlueprintConfig(...)
BILLING_DISPUTE_RESOLUTION = BlueprintConfig(...)
CHURN_PREVENTION = BlueprintConfig(...)
FRAUD_ALERT = BlueprintConfig(...)
```

**`platform/layer6_sdk/blueprint_runner.py`**
```python
class BlueprintRunner:
    async def run(
        self,
        blueprint: BlueprintConfig,
        customer_id: str,
        trigger: str,
        caller_id: str,
    ) -> ExecutionResult:
        # 1. Generate session_id + trace_id
        # 2. Layer 1: assemble context
        # 3. Layer 2: retrieve policy chunks
        # 4. Layer 3: run orchestration
        # 5. Layer 4: evaluate guardrails
        # 6. Layer 5: select variant for approved actions
        # 7. Execute approved actions via channel adapters
        # 8. Return ExecutionResult
```

**`platform/layer6_sdk/outcome_router.py`**
```python
class OutcomeRouter:
    async def route(self, outcome: OutcomeEvent) -> None:
        # Parallel:
        # 1. Update A/B experiment results (Layer 5)
        # 2. Write to model governance outcome store (Layer 5)
        # 3. Write OUTCOME_CAPTURED audit record
        # Conditional:
        # 4. If approval queue item involved: route feedback
```

**`platform/api/routers/sse.py`** — Server-Sent Events
```python
@router.get("/pipeline/events/{trace_id}")
async def pipeline_events(trace_id: str):
    """
    SSE stream. Emits events as each layer completes.
    UI Architecture View subscribes to this for live diagram updates.

    Event types:
      layer_started   { layer, timestamp }
      layer_completed { layer, latency_ms, output_summary }
      layer_error     { layer, error }
      pipeline_done   { trace_id, total_ms }
    """
```

**`platform/api/routers/pipeline.py`**
```python
POST /pipeline/run
  Body: { customer_id, scenario, blueprint? }
  Returns: { trace_id, session_id, status: "started" }
  Runs pipeline in background (asyncio.create_task)
  SSE stream carries progress

GET /pipeline/status/{trace_id}
  Returns current pipeline state from Valkey
```

All other API routers: implement CRUD endpoints for audit, experiments,
guardrails queue, model registry — see AGENTS.md project structure.

**`platform/demo.py`** — standalone demo
```python
"""
Banking Agentic AI Platform — Demo

Runs Marcus Webb (C002) through the payment risk intervention pipeline.
Prints live trace, layer-by-layer results, and complete audit trail.
No API key required. Uses mock LLM by default.

Usage:
  python -m platform.demo
  python -m platform.demo --customer C001 --scenario churn_prevention
"""
```

### Acceptance Criteria

- [ ] `pytest tests/unit/test_layer6.py -v` — all pass
- [ ] `pytest tests/integration/test_api.py -v` — all pass
- [ ] `python -m platform.demo` runs in < 10 seconds with mock LLM
  Output shows all 6 layers, latencies, and action summary
- [ ] POST /pipeline/run returns trace_id; GET /pipeline/status shows completed
- [ ] SSE stream emits 6 layer_completed events for a full pipeline run
- [ ] Outcome POST correctly updates experiment result count

---

## TASK 10 — Observability Wiring

Wire structured logging, distributed tracing, and metrics into every layer.
This task modifies existing layer code — do not break existing tests.

### Deliverables

**`platform/observability/logging.py`**
```python
def configure_logging(settings: Settings) -> None:
    """
    Configure structlog with processors:
    - add_log_level
    - add_timestamp (ISO 8601)
    - JSONRenderer (production) or ConsoleRenderer (development)
    Every log entry must include trace_id via contextvars.
    """
```

**`platform/observability/tracing.py`**
```python
def configure_tracing(settings: Settings) -> None:
    """OpenTelemetry setup with OTLP exporter to Jaeger."""

def traced(layer: str, operation: str):
    """
    Decorator. Creates a span for the decorated async function.
    Adds: layer, operation, trace_id, customer_id (from kwargs if present).
    Records exceptions and sets span status ERROR on exception.
    """

# Apply to every service method in all 6 layers:
# @traced(layer="L1", operation="context_assembly")
# async def assemble(self, ...) -> ...:
```

**`platform/observability/metrics.py`**
```python
# Prometheus metrics — one histogram per layer
LAYER_LATENCY = Histogram(
    "platform_layer_latency_seconds",
    "Latency per layer",
    labelnames=["layer", "scenario", "status"],
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0, 3.0, 10.0, 30.0],
)

ADAPTER_LATENCY = Histogram(...)        # per source adapter
GUARDRAIL_CHECKS = Counter(...)        # per check type + outcome
AGENT_TOOL_CALLS = Counter(...)        # per agent + tool
EXPERIMENT_ASSIGNMENTS = Counter(...)  # per experiment + variant

def metered(layer: str):
    """Decorator. Records latency and status to Prometheus."""

# Apply to every service method in all 6 layers:
# @metered(layer="L1")
# async def assemble(self, ...) -> ...:
```

**`platform/api/main.py`** — add metrics endpoint
```python
from prometheus_client import make_asgi_app
# Mount at /metrics for Prometheus scraping
```

**Grafana dashboard provisioning:**
- `grafana/provisioning/dashboards/platform.json`
- Panels: p99 latency per layer, error rate per layer,
  adapter success rates, guardrail check outcomes,
  experiment assignment distribution

### Acceptance Criteria

- [ ] `pytest tests/ -v` — all existing tests still pass
- [ ] Run `make demo`, open Jaeger at localhost:16686
  → trace visible with all 6 layer spans
  → CRM timeout span visible with TIMEOUT status
- [ ] Open Prometheus at localhost:9090
  → `platform_layer_latency_seconds` metric present
  → All 6 layers have latency observations
- [ ] Open Grafana at localhost:3000
  → Platform dashboard loads with all panels

---

## TASK 11 — UI Scaffold + Shared Components

Implements the React application shell. No page logic yet.

### Deliverables

**`ui/src/App.tsx`** — React Router routes
```tsx
// Routes:
// /                  → PipelineRunner
// /architecture      → ArchitectureView
// /audit/:traceId    → AuditTrail
// /experiments       → Experiments
// /drift             → DriftMonitor
// /guardrails        → GuardrailsView
// /models            → ModelRegistry
```

**`ui/src/components/Layout.tsx`**
- Fixed left sidebar (240px wide)
- Nav items for all 7 pages with icons (Lucide)
- Active route highlighted
- Top bar: "Banking Agentic AI Platform" + LLM mode badge
  (reads from GET /config — shows "Mock LLM" | "Ollama" | "API")
- Main content area with scroll

**`ui/src/api/client.ts`** — typed API client
```typescript
export const api = {
  runPipeline: (body: RunPipelineRequest) => Promise<RunPipelineResponse>,
  getPipelineStatus: (traceId: string) => Promise<PipelineStatus>,
  getAuditTrail: (traceId: string) => Promise<AuditRecord[]>,
  getExperiments: () => Promise<Experiment[]>,
  getModels: () => Promise<ModelVersion[]>,
  getRules: () => Promise<Rule[]>,
  getApprovalQueue: () => Promise<ApprovalQueueItem[]>,
  recordDecision: (queueId: string, decision: Decision) => Promise<void>,
  recordOutcome: (traceId: string, outcome: OutcomeEvent) => Promise<void>,
}
```

**`ui/src/hooks/usePipelineEvents.ts`** — SSE hook
```typescript
// Connects to GET /pipeline/events/{traceId} via EventSource
// Returns: { layers: Record<LayerId, LayerState>, isComplete }
// Updates Zustand store as events arrive
```

**`ui/src/hooks/usePipelineStore.ts`** — Zustand store
```typescript
interface PipelineStore {
  activeTraceId: string | null;
  layerStates: Record<string, LayerState>;
  setLayerActive: (layer: string) => void;
  setLayerComplete: (layer: string, latencyMs: number, summary: string) => void;
  setLayerError: (layer: string, error: string) => void;
  reset: () => void;
}
```

**Shared components:**
- `LayerStatusBadge` — idle (grey) | active (blue pulse) | complete (green) | error (red)
- `LatencyBar` — visual bar proportional to layer latency
- `CodeBlock` — syntax-highlighted JSON/Python display
- `SchemaViewer` — renders a Pydantic schema as a readable card

### Acceptance Criteria

- [ ] `npm run dev` starts without error
- [ ] All 7 routes load without console errors
- [ ] Layout sidebar renders all nav items with icons
- [ ] LLM mode badge shows "Mock LLM" (from API)
- [ ] `usePipelineEvents` hook connects to SSE and updates store
- [ ] TypeScript: `npx tsc --noEmit` — 0 errors

---

## TASK 12 — Architecture View (Priority UI Page)

This is the most important UI page. Read AGENTS.md and
docs/architecture.md fully before implementing.

### Existing Prototype to Reference

Two prototype files exist in `prototype/` and must be used as
**design and logic references** for this task:

- the mini platform prototype in `prototype/` — the working platform demo.
  Use its color tokens, dark theme, layer card design, and execution
  log pattern. The `T` color object defines the design language.
  The layer card expand/collapse pattern is the model for LayerNode.

- the architecture diagram prototype in `prototype/` — the static architecture
  diagram. Use its three-tab structure (Architecture / Data Flow /
  Tech Stack) as the foundation for the LayerDetail panel tabs.
  The LAYERS and CROSS arrays contain the exact text content for
  each layer's Problem and Decisions tabs.

**Do not copy these files directly.** Use them as reference for:
  - Design language (colors, typography, spacing from `T` tokens)
  - Layer content (problem statements, design decisions, tech stack)
  - Data flow timeline (the TIMELINE array in the diagram file)
  - The three-tab structure for LayerDetail

The implemented Architecture View in React Flow is a significant
upgrade from the prototype — animated edges, live SSE overlay,
per-layer drill-down with four tabs, React Flow zoom/pan.
The prototypes define the aesthetic and content; React Flow
and the SSE integration are new work.

### Deliverables

**`ui/src/architecture/PlatformDiagram.tsx`** — React Flow diagram

Node layout (top-to-bottom flow):
```
[TRIGGER]
    │
[L1 Context Assembly]
    │
[L2 Vector Search]
    │
[L3 Orchestration]  ←── [Hub-and-Spoke detail: AgentA → Orch → AgentB]
    │
[L4 Guardrails]
    │
[L5 A/B Evaluation]
    │
[L6 SDK + Execution]
    │
[OUTCOME CAPTURE]

Vertical bars alongside all layers:
  [OBSERVABILITY]  [MLOPS]
```

Node component (`LayerNode.tsx`):
```tsx
// Four visual states driven by Zustand store:
// idle:     dim border, muted text
// active:   bright colored border + glow + spinning ring
// complete: green border + checkmark + latency label fades in
// error:    red border + error icon

// Click → sets selected layer in Zustand → triggers Panel 3 update
```

Edge component (`DataFlowEdge.tsx`):
```tsx
// Animated dashed line that travels from source to target node
// Label shows what data is passed between layers:
// L1→L2: "session_id: sess_..."
// L2→L3: "3 policy chunks"
// L3→L4: "ACT-001 + ACT-002 proposed"
// L4→L5: "ACT-001 APPROVED"
// L5→L6: "Variant A selected"
// Animation plays when source node transitions to "complete"
```

**`ui/src/architecture/LayerNavigator.tsx`** — left panel (30%)
```tsx
// Lists all 8 sections (6 layers + 2 cross-cutting)
// Per item: layer number badge, name, status badge, last-run latency
// Click → selects layer → updates LayerDetail panel
// During pipeline: auto-scrolls to active layer
```

**`ui/src/architecture/LayerDetail.tsx`** — right panel (25%)

Four tabs per layer:

**Problem tab:** Hardcoded narrative text from docs/architecture.md.
Each layer has 2-3 paragraphs explaining what problem it solves and why.

**Architecture tab:** Mini React Flow diagram for just this layer.
Shows the internal components and data flow within that layer only.
Example for L1: parallel fetch arrows → normalization → feature store →
merge → Valkey write.

**Decisions tab:** Table with three columns — Decision | Choice | Rationale.
Content pulled from the "Key Design Decisions" tables in docs/architecture.md.
Each layer has 8-12 rows.

**Last Run tab:** Live data from most recent pipeline execution.
Polled from GET /audit/latest (returns most recent audit records per layer).
Shows: customer, scenario, latency, sources degraded, key output values.
Updates after every pipeline run.

**`ui/src/pages/ArchitectureView.tsx`** — parent page
```tsx
// Three-panel layout:
// Left 30%:  LayerNavigator
// Center 45%: PlatformDiagram
// Right 25%: LayerDetail

// During pipeline execution (SSE active):
//   usePipelineStore drives diagram node states
//   usePipelineEvents updates store from SSE stream

// Header bar: "Watch live" toggle + "Run new pipeline" button
//   (Run button triggers POST /pipeline/run + connects SSE)
```

### Acceptance Criteria

- [ ] Architecture diagram renders all 8 nodes + 7 edges + 2 cross-cutting bars
- [ ] Clicking each layer node loads correct Problem + Decisions content
- [ ] All 6 layers have content populated in all 4 tabs
- [ ] Run a pipeline from PipelineRunner, open ArchitectureView:
  → Layers light up in sequence as pipeline executes
  → Edge labels appear as data flows between layers
  → Final state: all nodes green with latency labels
- [ ] Error state: if L3 agent times out → L3 node turns red
- [ ] Diagram is zoom/pan-able (React Flow default behavior)
- [ ] Mobile: diagram is scrollable (not broken on narrow viewport)

---

## TASK 13 — Pipeline Runner UI

**`ui/src/pages/PipelineRunner.tsx`**

Layout:
```
[Customer Selector]  [Scenario Selector]  [LLM Mode Badge]

[Run Pipeline Button]   [Watch in Architecture View →]

─────── Execution Log ───────────────────────────────
  10:42:33.000  [L1]  Context Assembly started
  10:42:33.150  [L1]  ⚠ CRM adapter timeout — proceeding degraded
  10:42:33.167  [L1]  ✓ Profile assembled (167ms)
  10:42:33.222  [L2]  ✓ 3 policy chunks retrieved (55ms)
  10:42:33.223  [L3]  RiskScoringAgent running...
  ...

─────── Results Summary ─────────────────────────────
  Risk Level:     CRITICAL (confidence 0.89)
  Intervention:   Hardship Program Enrollment Offer
  ACT-001:        APPROVED → Push notification delivered
  ACT-002:        FLAGGED → Approval queue (4hr SLA)
  Variant:        A — soft framing
  Total Latency:  6,444ms
  Trace ID:       trace_20260511_...  [copy button]
```

SSE stream drives the Execution Log in real time.
"Watch in Architecture View" links to `/architecture?traceId={id}`.

### Acceptance Criteria

- [ ] All 3 customers and 3 scenarios selectable
- [ ] Pipeline runs end-to-end with mock LLM
- [ ] Execution log streams in real time via SSE
- [ ] Results panel shows all layer outputs
- [ ] "Watch in Architecture View" opens diagram with that trace active
- [ ] Trace ID copyable to clipboard

---

## TASK 14 — Remaining UI Pages

Implement in order. All pages use TanStack Query for data fetching.

**`AuditTrail.tsx`** (`/audit/:traceId`)
- Timeline: all audit records for a trace_id sorted by timestamp
- Each record: event_type badge, timestamp, expandable JSON detail
- "Regulatory Replay" section: structured reconstruction answering:
  "What data did the agent have? What policy? What compliance checks?"

**`Experiments.tsx`** (`/experiments`)
- List of active + concluded experiments
- Per experiment: variant stats table + Recharts bar chart
  (conversion rate per variant with confidence interval)
- Statistical significance indicator (p-value badge)

**`DriftMonitor.tsx`** (`/drift`)
- Model list with drift status badges (stable / monitor / investigate / retrain)
- PSI trend line chart per model (Recharts)
- Embedded Evidently HTML report in iframe (`/drift/report/{modelId}`)

**`GuardrailsView.tsx`** (`/guardrails`)
- Rule store viewer: grouped by category, per rule shows version + condition
- Approval queue: items sorted by SLA urgency
  Each item: flag reasons, customer context summary, SLA countdown timer
  Approve / Reject buttons → PUT /queue/{id}/decision

**`ModelRegistry.tsx`** (`/models`)
- Model cards: champion badge, version, recall, AIR score
- Champion/Challenger status: show traffic split (95/5)
- Evaluation gate results: 4 gates with pass/fail badges

### Acceptance Criteria

- [ ] All 5 pages load data without console errors
- [ ] AuditTrail: run demo, enter trace_id, see full 8-record timeline
- [ ] Experiments: Variant A shows as leader with stats
- [ ] DriftMonitor: Evidently report renders in iframe
- [ ] GuardrailsView: approval queue item visible after demo run
- [ ] ModelRegistry: three models seeded with champion versions

---

## TASK 15 — Full Integration Test + README Polish

### Deliverables

**`tests/integration/test_full_pipeline.py`**
```python
# 9 pipeline runs: all 3 customers × all 3 scenarios
@pytest.mark.parametrize("customer_id,scenario", [
    ("C001", "payment_risk_intervention"),
    ("C001", "billing_dispute_resolution"),
    ("C001", "churn_prevention"),
    ("C002", "payment_risk_intervention"),  # primary test
    ("C002", "billing_dispute_resolution"),
    ("C002", "churn_prevention"),
    ("C003", "payment_risk_intervention"),
    ("C003", "billing_dispute_resolution"),
    ("C003", "churn_prevention"),
])
async def test_full_pipeline(customer_id, scenario):
    # Assert: audit trail has exactly 8 records
    # Assert: all audit records have trace_id, session_id, customer_id
    # Assert: C002 payment_risk produces CRITICAL risk assessment
    # Assert: guardrails evaluated for all proposed actions
    # Assert: variant assignment consistent (same customer = same variant)
    # Assert: total latency < 500ms with mock LLM
```

**README.md — final polish:**

Sections:
1. Overview + what makes it different (architecture-as-code, live diagram)
2. Architecture diagram (screenshot of /architecture page)
3. Quick Start (tested, no API key required)
4. Layer-by-layer description (1-2 paragraphs each)
5. Technology stack table
6. Running with a real LLM (Ollama + API options)
7. Contributing

### Acceptance Criteria

- [ ] `pytest tests/ -v` — 0 failures across all tests
- [ ] All 9 parameterized pipeline runs pass
- [ ] `make typecheck` — 0 errors
- [ ] `make lint` — 0 errors
- [ ] README Quick Start works on a clean machine (no prior setup)
- [ ] Screenshot of /architecture page in README

---

## PROMPT TEMPLATE

Use this exact prompt for every task:

```
Complete TASK [NUMBER] from TASKS.md.

Before writing any code:
1. Read AGENTS.md fully
2. Read the relevant section(s) of docs/architecture.md for this task

Standards to follow:
- Type hints on every function signature
- Docstrings on every public class and method
- Test file created alongside every new module
- No secrets or API keys in any file
- Interfaces for all external dependencies (interfaces.py)
- structlog for all logging (never print())
- Async throughout (never sync I/O in business logic)

When implementation is complete, run the acceptance criteria:
[paste the acceptance criteria checklist from the task]

Report:
- Which acceptance criteria passed ✓
- Which failed ✗ and what the error was
- Any deviations from docs/architecture.md with justification

Do not begin TASK [NEXT NUMBER] until all acceptance criteria pass.
```

---

## Progress Tracker

| Task | Description | Status |
|------|-------------|--------|
| 01 | Repo Scaffold | ✅ |
| 02 | Core Schemas + Interfaces | ✅ |
| 03 | Infrastructure Adapters | ✅ |
| 04 | Layer 1: Context Assembly | ✅ |
| 05 | Layer 2: Vector Search | ✅ |
| 06 | Layer 3: Orchestration | ✅ |
| 07 | Layer 4: Guardrails | ✅ |
| 08 | Layer 5: A/B + Model Governance | ✅ |
| 09 | Layer 6: SDK + Execution | ✅ |
| 10 | Observability Wiring | ✅ |
| 11 | UI Scaffold + Shared Components | ✅ |
| 12 | Architecture View (Priority) | ✅ |
| 13 | Pipeline Runner UI | ✅ |
| 14 | Remaining UI Pages | ✅ |
| 15 | Full Integration Test + README | ✅ |
| Last completed | May 2026 | ✅ |
