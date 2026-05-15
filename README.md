# Banking Agentic AI Platform

Author: Sarala Biswal

A cloud-agnostic, production-grade Agentic AI platform for banking decisions.
It demonstrates how to compose live customer context, hybrid retrieval,
multi-agent reasoning, guardrails, experimentation, execution, observability,
and audit replay into one governed platform.

What makes this project different:

- Architecture-as-code: every layer has typed schemas, runtime services, tests,
  and UI visibility.
- Live diagram: `/architecture` animates the six-layer pipeline from SSE events.
- No API key required: the default mock LLM exercises all downstream logic.
- Regulatory replay: one `trace_id` reconstructs context, policy, guardrails,
  action, and outcomes.

## Architecture Diagram

See [Logical Architecture Diagram](docs/logical-architecture.md) for the
platform runtime view, service boundaries, governance flow, state stores, and
feedback loop.

## Why This Architecture

Banks hold enough customer data to intervene before a customer misses a
payment, churns, or disputes a charge. Most AI systems fail to act on it
because they combine three problems: stale batch context, ungoverned agent
actions, and no feedback loop.

This platform separates those concerns into six layers that every banking
AI product team needs but rarely builds correctly:

- **Context Assembly** delivers a live customer profile in under 200ms —
  not last night's batch export.
- **Vector Search** retrieves the right policy at decision time — not
  hardcoded prompts that go stale when regulations change.
- **Orchestration** routes agent work through a governed hub — agents
  propose actions, never execute them directly.
- **Guardrails** checks every proposed action against regulatory,
  business, and fairness rules before it reaches a customer.
- **A/B Evaluation** measures what works and closes the loop between
  interventions and model governance.
- **SDK Surface** gives product teams all six layers in a few lines of
  code — not three months of reimplementation.

The result: interventions that are live, governed, measurable, and
explainable. One `trace_id` reconstructs the complete decision trail
for any regulatory examination.

## Quick Start — No API Key Required

```bash
git clone <repository-url>
cd banking-agentic-ai-platform
make install
make docker-up
cp .env.example .env
make demo

# Output: full pipeline trace for Marcus Webb (C002)
# No API key. No external service. Runs entirely locally.
```

To run the API and UI:

```bash
make dev
# UI:  http://localhost:5173
# API: http://localhost:8000
```

## Current Implementation

The local implementation includes:

- FastAPI API with pipeline run/status, SSE events, audit replay, guardrails,
  experiments, model registry, drift reports, and runtime config endpoints.
- React/Vite UI routes for `/about`, `/`, `/architecture`, `/audit/:traceId`,
  `/experiments`, `/drift`, `/guardrails`, `/models`, and `/settings`.
- Runtime LLM switching from the Settings page using process-local config:
  Mock LLM, Ollama, or API mode. The UI never writes `.env`, restarts the
  server, or stores API keys in browser storage.
- Local Docker services for Valkey, PostgreSQL, Qdrant, Jaeger, Prometheus,
  Grafana, and MLflow.
- Process-local demo/API audit replay for live UI runs, plus PostgreSQL audit
  writer support in the adapter layer.

## Layers

**Layer 1 — Context Assembly**  
Fetches card, banking, CRM, behavioral, and feature-store signals in parallel.
Source failures degrade safely into `partial_context` instead of failing the
pipeline.

**Layer 2 — Vector Search**  
Builds a scenario-aware query from the live profile, runs hybrid dense + BM25
retrieval, merges with RRF, and returns policy chunks with lineage.

**Layer 3 — Orchestration**  
Runs hub-and-spoke agent workflows. Agents propose typed actions only; tool
authorization is enforced in code before tool execution.

**Layer 4 — Guardrails**  
Evaluates proposed actions through regulatory, business policy, and responsible
AI checks. Flagged actions enter an SLA-backed approval queue.

**Layer 5 — A/B + Model Governance**  
Assigns variants deterministically, tracks outcomes, and exposes drift/model
governance signals for champion/challenger models.

**Layer 6 — SDK + Execution**  
Presents the product-team surface: blueprint execution, channel adapters,
delivery receipts, and outcome capture.

**Cross-cutting — Observability + Audit**  
Every layer emits metrics, traces, logs, and append-only audit evidence linked
by `trace_id`. The demo/API runner keeps audit replay in process memory for
local interactivity; the adapter layer includes PostgreSQL audit inserts for
durable storage paths.

## Technology Stack

| Area | Stack |
| --- | --- |
| Backend | Python, FastAPI, Pydantic v2, asyncio |
| Storage | Valkey/Redis, PostgreSQL, Qdrant, MLflow |
| Retrieval | sentence-transformers, rank_bm25, RRF reranking |
| LLM | Mock LLM by default, Ollama or LiteLLM optional |
| Observability | structlog, OpenTelemetry, Prometheus, Grafana, Jaeger |
| Frontend | React, TypeScript, Vite, TanStack Query, Zustand |
| UI | Tailwind CSS, React Flow, Recharts, lucide-react |
| Testing | pytest, pytest-asyncio, testcontainers, Playwright smoke checks |

## Optional: Real LLM Inference

You can switch LLM backends from the `/settings` page while the server is
running. The setting is in-memory for the current server process.

```bash
# Local model (free, no account)
brew install ollama
ollama pull llama3.2
echo "LLM_BACKEND=ollama" >> .env
make demo

# Cloud API (requires key)
echo "LLM_BACKEND=api" >> .env
echo "ANTHROPIC_API_KEY=your-key" >> .env
make demo
```

## Useful Commands

```bash
make install     # uv sync + pnpm install
make dev         # docker services + API + UI dev server
make demo        # run the standalone C002 payment-risk demo
make test        # full pytest suite
make test-unit   # unit tests only
make test-int    # integration tests only
make typecheck   # mypy + TypeScript
make lint        # ruff + TypeScript
make format      # ruff format + prettier
make docker-up   # seven local services
make docker-down
make migrate     # run Alembic migrations
```

## Contributing

Read the local planning specs under `docs/planning/` when they are present,
especially `AGENTS.md` and `architecture.md`, before changing a layer. Keep
field names aligned with the architecture spec, use interfaces for external
dependencies, keep business logic async, and add tests with each behavior
change.
