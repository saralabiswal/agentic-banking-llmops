# Banking Agentic AI Platform — Architecture Specification
## Engineering Reference · v1.0 · May 2026

> This document is the engineering specification for the Banking Agentic AI Platform.
> It captures every design decision, data flow, trade-off, and implementation detail
> for all six layers and two cross-cutting concerns. Each layer is written so an
> engineer can implement it directly from this document.
>
> **This document is referenced by `AGENTS.md` and `TASKS.md`.**
> Codex reads it before every implementation task. All field names, schema
> definitions, and design decisions in the code must trace back to this document.

---

## Contents

| Section | Description |
|---------|-------------|
| [Platform Overview](#platform-overview) | Domain, test customers, design principles, high-level architecture |
| [Current Implementation Status](#current-implementation-status) | What the repo implements today and what remains target-only |
| [Layer 1 — Context Assembly](#layer-1--context-assembly) | Parallel fetch, TTL context store, feature store, audit log |
| [Layer 2 — Vector Search](#layer-2--vector-search--semantic-retrieval) | Hybrid ANN+BM25, hierarchical chunking, KB update pipeline |
| [Layer 3 — Orchestration](#layer-3--multi-agent-orchestration) | Hub-and-spoke, tool authorization, pipeline state, failure handling |
| [Layer 4 — Guardrails](#layer-4--guardrails--policy-enforcement) | Regulatory/business/AI checks, fairness analysis, approval queue, rule engine |
| [Layer 5 — A/B & Model Governance](#layer-5--ab-evaluation--model-governance) | Variant selection, drift detection, champion/challenger |
| [Layer 6 — SDK Surface](#layer-6--sdk-surface--product-team-interface) | Blueprint catalog, channel adapters, outcome capture |
| [Observability & Audit Trail](#cross-cutting--observability--audit-trail) | SLOs, distributed tracing, regulatory replay, audit storage |
| [MLOps & Drift Detection](#cross-cutting--mlops--drift-detection) | Feature store, evaluation gate, retraining triggers |
| [Full Platform Diagram](#full-platform-architecture-diagram) | Complete ASCII diagram + end-to-end latency breakdown |

---

## Platform Overview

### What We Are Building

A cloud-agnostic, production-grade Agentic AI Platform architecture for
banking, plus a local reference implementation in this repository. The
implemented app demonstrates the six-layer design on a developer machine; the
AWS-native callouts in this document are target deployment mappings, not
services that are currently wired into the repo.

### Current Implementation Status

Implemented in this repository:
- Full six-layer pipeline for payment risk intervention, billing dispute
  resolution, and churn prevention using deterministic test customers.
- FastAPI API, SSE lifecycle events, React/Vite UI, local Docker services,
  typed Pydantic schemas, matching TypeScript API types, and automated tests.
- Local infrastructure adapters for Valkey/Redis, PostgreSQL, Qdrant, MLflow,
  Ollama, LiteLLM, and mock LLM/channel behavior.
- Local observability primitives: structlog context, OpenTelemetry spans to
  Jaeger, Prometheus metrics, Grafana provisioning, and audit replay tied by
  `trace_id`.

Not implemented in this repository:
- AWS-native production backends and operations: DynamoDB, S3 Object Lock,
  Athena, SageMaker, Bedrock, X-Ray, CloudWatch, EventBridge, Glue, App Mesh,
  IAM, and production alert routing.
- Production security and deployment controls: authn/authz, secret-manager
  integration, multi-tenant isolation, HA manifests, CI/CD, and incident runbooks.
- Real delivery channels: FCM/APNS, Twilio, SendGrid, production CRM writes, and
  account-system writes. Layer 6 uses mock channel adapters.
- Long-retention immutable audit archival and Athena-style cold replay. Local
  adapter tests use PostgreSQL audit inserts; the demo/API runner keeps audit
  and SSE events process-local for replay during a run.
- Automated retraining pipelines, scheduled batch scoring, model-card storage,
  and production MLOps workflow orchestration. Layer 5 implements local
  experiment assignment/outcomes, drift calculations, and an MLflow wrapper.
- Fraud alert execution. It appears as a future/example blueprint, but the
  implemented and tested end-to-end scenarios are payment risk, billing dispute,
  and churn prevention.

Unless a section explicitly says "local implementation", AWS-native services
named later in this document describe the target production deployment path.

### Domain

Banking / Financial Decisions across three scenarios:
- **Payment Risk Intervention** — detect and intervene on missed payment risk
- **Billing Dispute Resolution** — autonomous dispute triage and resolution
- **Churn Prevention** — identify churn signals and generate retention offer

### Test Customers (used throughout all examples)

| ID | Name | Segment | Risk Score | Churn Prob | Profile |
|----|------|---------|-----------|-----------|---------|
| C001 | Alexandra Chen | Prime | 0.08 | 0.04 | Low risk, high NPS, long tenure |
| C002 | Marcus Webb | Standard | 0.71 | 0.58 | HIGH RISK — used in all primary examples |
| C003 | Priya Sharma | Affluent | 0.03 | 0.02 | Very low risk, highest CLV |

> **Why Marcus Webb for all primary examples:**
> High utilization (76%), two missed payments, near-zero checking balance,
> CRM timeout during assembly, high mobile engagement. Every layer has
> something meaningful to do with his profile.

### Core Design Principles

| # | Principle | What it means in practice |
|---|-----------|--------------------------|
| 1 | Live context over cached snapshots | Agents act on real data at decision time, not nightly batch exports |
| 2 | Governance as runtime capability | Guardrails and policy enforcement happen before action — not after |
| 3 | Hub-and-spoke orchestration | All inter-agent communication routes through orchestrator — never peer-to-peer |
| 4 | Graceful degradation over hard failure | A missing source produces a partial profile, not a failed pipeline |
| 5 | Full lineage for regulatory replay | Every decision reproducible: data the agent had, model versions, what was missing |
| 6 | Cloud-agnostic architecture | Patterns are universal; AWS-native is the deployment choice, not the design |
| 7 | One writer, many readers | Only the authoritative service for each layer writes to shared stores |
| 8 | Immutable audit trail | Audit records written once, never modified — regulatory requirement |

### High-Level Platform Architecture

```
Inbound Trigger (scheduler / customer event / API call)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 1: Context Assembly Service                           │
│  Parallel fetch → Normalization → Feature Store merge        │
│  → TTL Context Store (Redis/Valkey) + Audit Log              │
│    (PostgreSQL locally; DynamoDB/S3 in target AWS deployment)│
└──────────────────────────────┬───────────────────────────────┘
                               │  session_id (lightweight)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 2: Vector Search Service                              │
│  Dynamic query construction → Hybrid ANN + BM25 search       │
│  → Cross-encoder re-ranking → Policy context packaged        │
└──────────────────────────────┬───────────────────────────────┘
                               │  Relevant policy context (top 3-5 chunks)
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 3: Orchestration Layer                                │
│  Hub-and-spoke routing → Specialized agent invocation        │
│  → Shared context threading → Pipeline state management      │
└──────────────────────────────┬───────────────────────────────┘
                               │  Agent outputs
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 4: Guardrails & Policy Enforcement                    │
│  Runtime policy checks → Block / Flag / Approve              │
│  → Escalation routing → Compliance logging                   │
└──────────────────────────────┬───────────────────────────────┘
                               │  Authorized action
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 5: A/B Evaluation & Model Governance                  │
│  Variant selection → Confidence scoring → Winner routing     │
│  → Drift detection → Retraining signals                      │
└──────────────────────────────┬───────────────────────────────┘
                               │  Winning action + confidence
                               ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 6: SDK Surface                                        │
│  Product team interface → Standardized action output         │
│  → Delivery routing (SMS / push / associate queue)           │
└──────────────────────────────────────────────────────────────┘

Cross-cutting: Observability & Audit Trail  (every layer writes to it)
Cross-cutting: MLOps & Drift Detection      (monitors every model)
```

---
---

# LAYER 1 — Context Assembly

## Problem This Layer Solves

Before any agent can make a decision, it needs to know who the customer is
across every system that holds data about them. In a real banking enterprise,
that data lives in completely separate systems — separate APIs, separate
data models, separate latency profiles, separate auth layers.

If you let the agent fetch data lazily or work from a cached snapshot,
you get decisions that feel wrong: wrong pricing, outdated account status,
stale risk signals. The customer called yesterday about a hardship situation
— but the agent offering a credit limit increase doesn't know that.

**Context Assembly solves this.** Assembles a unified, live customer profile
from multiple sources and hands it to every agent as a single authoritative
context object — assembled once, before any reasoning begins.

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Data sources | 3 hardcoded JS objects | 4-5 live API adapters |
| Fetch pattern | Simulated sequential | True parallel async with per-source timeout |
| Normalization | String template | Canonical typed schema |
| Feature signals | Hardcoded | Pulled from live feature store |
| Context storage | In-memory JS variable | Redis TTL store, session-scoped |
| Degraded sources | Not simulated | Graceful degradation, partial_context flag |
| Audit log | UI panel only | Immutable DynamoDB record per event |

---

## Service Interface

```python
class ContextAssemblyService:
    def assemble(
        self,
        customer_id: str,
        session_id:  str,
        scenario:    str
    ) -> AssemblyResult:
        """
        Assembles unified customer profile from all available sources.
        Writes to TTL context store and audit log.
        Never raises on source failure — degrades gracefully.
        SLA: 200ms at p99.
        """

class AssemblyResult:
    status:           str        # ASSEMBLED | DEGRADED | FAILED
    session_id:       str
    customer_id:      str
    partial_context:  bool
    sources_degraded: list[str]
    ttl_expires_at:   datetime
    assembly_ms:      int
```

---

## Source Adapters

One adapter per upstream system. Independently deployable.
Source system API changes update one adapter — platform is shielded.

```python
class SourceAdapter:
    TIMEOUT_MS = 150    # hard timeout — enforced by caller, not adapter

    def fetch(self, customer_id: str) -> RawSourceData:
        # Raises SourceTimeoutError or SourceUnavailableError on failure
        # Never returns partial data

class CardSystemAdapter(SourceAdapter):      # balance, limit, utilization, missed_pmts
class CoreBankingAdapter(SourceAdapter):     # checking, savings, deposits, overdrafts
class CRMAdapter(SourceAdapter):             # tenure, NPS, open_tickets, last_contact
class BehavioralSignalsAdapter(SourceAdapter): # logins, channel, sms_ok, push_enabled
class FraudSignalsAdapter(SourceAdapter):    # alerts, anomaly_score, synthetic_id_flag
```

---

## Canonical CustomerProfile Schema

```python
@dataclass
class CustomerProfile:
    customer_id:         str
    name:                str
    segment:             Segment        # STANDARD | PRIME | AFFLUENT | PRIVATE
    card:                CardProfile
    banking:             BankingProfile
    crm:                 Optional[CRMProfile]   # None if CRM degraded
    behavioral:          BehavioralProfile
    signals:             ModelSignals
    assembled_at:        datetime
    assembly_latency_ms: int
    sources_available:   list[str]
    sources_degraded:    list[str]
    partial_context:     bool

@dataclass
class ModelSignals:
    risk_score:         float     # 0.0–1.0
    churn_probability:  float     # 0.0–1.0
    clv_estimate:       Decimal
    last_intervention:  datetime
    intervention_7d:    int
    payment_propensity: float
    model_versions:     dict      # {"risk": "v4.2.1"} — audit lineage
```

---

## Feature Store Integration

```
Pre-computed (Feature Store, updated on cadence):
  risk_score          — hourly batch
  churn_probability   — nightly batch
  clv_estimate        — nightly batch
  payment_propensity  — hourly batch

Live (source adapters, fetched fresh):
  card.balance        — intraday changes matter
  banking.checking    — intraday changes matter
  crm.open_tickets    — opened/closed same day
  behavioral signals  — today's app activity

model_versions stored alongside signals = audit lineage.
When model retrained, every prior decision traces to exact version used.
```

---

## TTL Context Store — Producer / Consumer Model

### Core Pattern

```
One producer  : Context Assembly Service  — writes ONCE per session
Many consumers: All agents + Orchestrator — read MANY times per session
Lifetime      : TTL = 300 seconds
Isolation     : session:{session_id}:customer_profile — per session key
```

### Producer

```python
redis.set(
    key   = f"session:{session_id}:customer_profile",
    value = profile.to_json(),
    ex    = 300,    # Redis-enforced TTL — not application logic
    nx    = True    # Only write if key does not exist — prevents overwrite
)

# Rules:
# Write once. Value immutable after write.
# TTL set at write time, never extended.
# Only ContextAssemblyService may write — IAM enforced at infra level.
```

### Consumer

```python
def read_context(session_id: str) -> CustomerProfile:
    result = redis.get(f"session:{session_id}:customer_profile")

    if result is None:
        raise SessionExpiredError(...)   # route to human review — never silently proceed

    profile = CustomerProfile.from_json(result)

    if profile.partial_context:
        # Check sources_degraded before accessing those fields
        # e.g. if "crm" in profile.sources_degraded: profile.crm is None

    audit.log_context_read(session_id, agent_name, timestamp)
    return profile

# Rules:
# Always handle None. Always check partial_context.
# Never write back. Never cache locally.
# Log every read for audit trail.
```

### TTL Expiry Scenarios

```
Scenario A — Normal: all agents complete within TTL. Key auto-evicts at T+300s.

Scenario B — Timeout: agent reads after TTL expires → None → SessionExpiredError
             → Orchestrator routes to human review queue.
             → Audit: "session_expired_mid_pipeline". Never silently uses stale data.

Scenario C — Degraded source: CRM times out during assembly.
             Profile written: sources_degraded=["crm"], crm=None
             Agents read partial_context=True, skip CRM assertions,
             flag output lower_confidence=True. Pipeline continues.
```

---

## Full Data Flow — Marcus Webb, Payment Risk Intervention

### Step 0 — Inbound Request
```
{ customer_id: "C002", session_id: "sess_C002_20260511_104233_f3a2b9",
  scenario: "payment_risk_intervention", requested_by: "payment_risk_scheduler" }
SLA budget: 200ms
```

### Step 1 — Parallel Source Fetch (T+0ms to T+150ms)
```
T+0ms    CardAdapter, BankingAdapter, CRMAdapter, BehavioralAdapter → all fire in parallel
T+38ms   Card: balance 3800, limit 5000, util 0.76, missed_pmts 2, past_due 420
T+61ms   Banking: checking 312.40, savings 0, last_deposit 2026-04-15, overdrafts 1
T+89ms   Behavioral: logins 14, channel MOBILE, sms_ok true, push_ok true
T+150ms  CRM: TIMEOUT → sources_degraded: ["crm"] → pipeline continues
```

### Step 2 — Schema Normalization (T+151ms to T+154ms)
```
Raw fields → canonical schema. Internal IDs dropped. Utilization computed (3800/5000=0.76).
CRM → None (degraded). All source-specific field names unified to canonical contract.
```

### Step 3 — Feature Store Pull (T+155ms to T+162ms)
```
GET customer_id="C002" → risk: 0.71 (risk-v4.2.1), churn: 0.58 (churn-v3.0.8),
clv: 1240 (clv-v2.1.4), payment_propensity: 0.31 (pay-v2.0.3),
last_intervention: 2026-04-28, intervention_7d: 0
model_versions stored alongside signals for audit lineage.
```

### Step 4 — Profile Merge (T+163ms to T+164ms)
```
UnifiedCustomerProfile assembled:
  card.utilization: 0.76 ⚠  card.missed_pmts: 2 ⚠  card.past_due: 420 ⚠
  banking.checking: 312.40 ⚠  banking.savings: 0 ⚠  banking.direct_dep: false ⚠
  crm: None (degraded)
  behavioral.sms_ok: true ✓  behavioral.push_ok: true ✓
  signals.risk_score: 0.71 ⚠  signals.churn_prob: 0.58 ⚠
  signals.payment_propensity: 0.31 ⚠  signals.intervention_7d: 0 ✓
  partial_context: true  sources_degraded: ["crm"]
```

### Step 5 — Redis Write (T+165ms)
```python
redis.set("session:sess_C002_20260511_104233_f3a2b9:customer_profile",
          profile.to_json(), ex=300, nx=True)
# Confirmed OK. Auto-evicts at 10:47:33.
```

### Step 6 — Audit Log (T+166ms)
```python
{ "audit_id": "aud_20260511_104233_C002", "event_type": "CONTEXT_ASSEMBLY",
  "sources_succeeded": ["card","banking","behavioral","feature_store"],
  "sources_failed": ["crm"], "failure_reasons": {"crm": "TIMEOUT_150MS"},
  "assembly_latency_ms": 166, "profile_hash": "sha256:8f3a2b9c...",
  "model_versions_used": {"risk": "risk-v4.2.1", "churn": "churn-v3.0.8"},
  "partial_context": true, "ttl_expires_at": "2026-05-11T10:47:33Z" }
```

### Step 7 — Handoff to Orchestrator (T+167ms)
```
AssemblyResult { status: ASSEMBLED, session_id: "sess_C002_...",
  partial_context: True, sources_degraded: ["crm"],
  ttl_expires_at: 10:47:33, assembly_ms: 167 }
Agents receive session_id only — they read profile from Redis independently.
```

### Timeline Summary
```
T+0ms → T+150ms  Parallel source fetch (CRM timeout at 150ms)
T+151ms→T+154ms  Schema normalization
T+155ms→T+162ms  Feature store pull
T+163ms→T+164ms  Profile merge
T+165ms          Redis write (EX=300, NX=true)
T+166ms          Audit log → DynamoDB
T+167ms          Handoff to Orchestrator
Total: 167ms / 200ms SLA budget ✓
```

---

## Key Design Decisions — Layer 1

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Fetch pattern | Parallel async, 150ms timeout per adapter | Sequential = sum of latencies. Parallel = slowest single source. Non-negotiable at 100M scale. |
| Degraded source | Graceful — partial profile + flag | Hard failure on CRM timeout = no intervention for at-risk customers when CRM is slow. Wrong tradeoff. |
| Context store | Redis TTL, session-scoped, NX write | Sub-ms reads. Native TTL enforced by store, not app. NX prevents silent overwrite. |
| Live vs. pre-computed | Balance = live. Risk score = Feature Store | Intraday balance changes matter. Risk score stable enough for hourly cadence. |
| Normalization layer | Separate from fetch layer | Source API changes update one adapter. Platform shielded from upstream schema churn. |
| Orchestrator handoff | session_id only — not full profile | Keeps payload tiny. Agents fetch from Redis independently. |
| Audit log store | DynamoDB separate from Redis | Redis is ephemeral. Regulatory replay requires permanent storage outlasting TTL. |
| Model versions in profile | Stored alongside signals | Links each signal to exact model version. Mandatory for model governance audit trail. |

---

## Technology Mapping — Layer 1

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Context Assembly Service | Any container runtime | ECS / EKS |
| Source Adapters | REST / gRPC clients | Lambda or ECS sidecars |
| TTL Context Store | Redis | ElastiCache for Redis (multi-AZ) |
| Feature Store | Any feature store | SageMaker Feature Store |
| Audit Log | Append-only store | DynamoDB + S3 |
| Service mesh / auth | mTLS + service identity | AWS App Mesh + IAM |
| Schema registry | Any | AWS Glue Schema Registry |

---

*Layer 1 + TTL deep dive completed: May 2026*

---
---

# LAYER 2 — Vector Search & Semantic Retrieval

## Problem This Layer Solves

By the time the Orchestrator is ready to invoke an agent, it has the unified
customer profile from Layer 1. But the agent doesn't just need to know who
the customer is — it needs to know what the rules are for acting on that
customer's situation.

Those rules live in a knowledge base: policy documents, regulatory guidelines,
intervention playbooks, eligibility criteria, compliance requirements.
Thousands of documents. The agent cannot receive all of them — context window
has limits, and stuffing irrelevant policy into every prompt degrades
reasoning quality.

**Vector Search solves this.** Takes the agent's scenario and retrieves the
specific 3–5 policy documents most relevant to that situation, at query time.
The agent gets exactly what it needs to reason correctly, and nothing it doesn't.

Key shift from traditional search: **semantic similarity, not keyword matching.**
"Customer facing financial hardship" and "borrower experiencing payment
difficulty" mean the same thing — keyword overlap scores low, vector
similarity scores high.

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Knowledge base | 8 hardcoded strings | Thousands of chunked policy documents in vector DB |
| Embeddings | None — word overlap scoring | Real embeddings (text-embedding-3-small or equivalent) |
| Query | Static string per scenario | Dynamically constructed from customer profile signals |
| Retrieval | Word match + random noise | ANN search (HNSW index) |
| Re-ranking | None | Cross-encoder re-ranking on top-K candidates |
| Freshness | Static at build time | Re-embedded on policy document update |
| Metadata filtering | None | Filter by product_line, jurisdiction before ANN search |
| Result format | Raw text strings | Chunks with source doc, version, confidence score |

---

## Two-Phase Lifecycle

Layer 2 operates in two distinct phases. Understanding both is essential
for the system design interview.

### Phase 1 — Indexing (offline, one-time + on policy update)

```
Policy Document (raw text)
        │
        ▼
  Chunking Layer
  Split into overlapping segments (256–512 tokens)
  Strategy: hierarchical (doc → section → paragraph)
        │
        ▼
  Embedding Model
  Each chunk → dense vector (1536 dimensions)
  + sparse vector (BM25 term weights) for hybrid search
        │
        ▼
  Vector Database
  Store: { chunk_id, dense_vector, sparse_vector, metadata, raw_text }
  Build: HNSW index for fast ANN search
```

### Phase 2 — Retrieval (online, per agent invocation)

```
Customer profile + scenario
        │
        ▼
  Dynamic Query Construction
  (from profile signals — not a static string)
        │
        ▼
  Query Embedding (same model used for indexing)
        │
        ▼
  Metadata Pre-filter
  (product_line, jurisdiction — narrows search space before ANN)
        │
        ▼
  Hybrid ANN + BM25 Search → RRF merge → top 20 candidates
        │
        ▼
  Cross-Encoder Re-ranking → top 3–5 chunks
        │
        ▼
  Policy context packaged for agent + audit log written
```

---

## 2a — Chunking Strategy

### Why Chunking Exists

Embedding models have token limits (512–8192). A policy document can be
15,000 tokens. Even within the limit, a single vector for a large document
averages out meaning — retrieval becomes imprecise. Chunking produces
segments that are semantically complete enough to be useful and small enough
for the embedding to capture specific meaning.

### Strategy 1 — Fixed-Size Chunking

```
Split every document into exactly N tokens with M token overlap.

Chunk size: 512 tokens | Overlap: 50 tokens
Chunk 1: tokens 0–511
Chunk 2: tokens 462–973     ← 50 token overlap prevents boundary splits
Chunk 3: tokens 923–1434

Why overlap: a critical sentence straddling a boundary
appears whole in at least one chunk.

Problem: documents don't respect token boundaries.
A chunk may start mid-sentence, end mid-paragraph.
Embedding sees semantically incomplete text → imprecise vector.

When to use: fast to implement, works for dense uniform text
(e.g. regulatory boilerplate where every section is similar).
```

### Strategy 2 — Semantic Chunking

```
Cut at semantic boundaries — paragraph breaks, section headers, topic shifts.

Section 1: "Eligibility Requirements"    → Chunk A
  Para 1: "Customers with 2+ missed payments..."
  Para 2: "Checking balance must be below $500..."

Section 2: "Program Terms"               → Chunk B
  Para 1: "Deferral covers minimum payment only..."

Each chunk is a complete unit of meaning. The embedding for Chunk A
captures everything about eligibility — not enrollment process (Chunk C).

Problem: poorly structured documents may have 3,000-token sections.
Need a max-size fallback — semantic chunking with size cap.

When to use: almost always outperforms fixed-size for retrieval quality.
Extra implementation complexity is worth it for regulated domains.
```

### Strategy 3 — Hierarchical Chunking (production choice for regulated domains)

```
Index the document at multiple granularity levels simultaneously.

Document: "Hardship Program Eligibility Criteria v2.3"
│
├── Document-level chunk (summary)
│   "Policy covering eligibility criteria, program terms, enrollment
│    process, and escalation thresholds for the 90-day hardship
│    deferral program for credit card customers."
│   → coarse retrieval: is this document relevant at all?
│
├── Section-level chunks (one per major section)
│   Section 1: "Eligibility Requirements" (full section)
│   Section 2: "Program Terms" (full section)
│   → mid-precision retrieval
│
└── Paragraph-level chunks (one per paragraph)
    Para 1.1: "Customers with 2+ missed payments in 90 days..."
    Para 1.2: "Checking balance must be below $500..."
    → high-precision retrieval

How retrieval uses hierarchy:
  ANN search runs on paragraph-level chunks (max precision).
  Retrieved paragraph surfaces its parent section for context.
  Agent receives: specific paragraph + surrounding section.
  Prevents "orphaned fact" problem — rule retrieved without
  the exception that lives two paragraphs later.

Why this matters for banking regulations:
  "This rule applies unless X, in which case Y."
  Paragraph chunk gets the rule. Hierarchy surfaces the exception.
```

### Chunk Size Decision Guide

```
< 128 tokens  → captures isolated facts, not context
                high precision on exact matches, poor on reasoning

256–512 tokens → sweet spot for policy documents (CHOSEN)

512–768 tokens → appropriate for playbooks (context matters more)

> 1024 tokens  → embedding averages out meaning
                 retrieval finds the document but not the specific section

Overlap: 10–15% of chunk size
  512-token chunks → 50-token overlap
  256-token chunks → 32-token overlap
```

---

## 2b — Embedding Model Choice

### What an Embedding Model Does

Takes a string of text, returns a fixed-length vector of floats (768–3072 dims).
Texts with similar meaning → vectors close in high-dimensional space.
Texts with different meaning → vectors far apart.
Retrieval quality is bounded by embedding quality. Bad embeddings =
semantically similar documents land far apart = ANN search misses them.

### General vs. Domain-Specific Models

```
General-purpose models (text-embedding-3-small, Cohere embed-v3):
  Trained on broad internet text.
  Excellent at everyday language.
  Struggle with domain-specific vocabulary.

Banking regulatory text example:
  "Pursuant to 12 CFR Part 1026 (Regulation Z), the creditor must
   provide required disclosures no later than three business days
   before consummation of a transaction..."

"Consummation of a transaction" in legal context = closing a loan.
Not what the word means in everyday language.
General model embedding will be imprecise for this text.
```

### Fine-Tuning Decision Framework

```
Fine-tuning IS worth it when:
  ✓ 10,000+ domain-specific (query, relevant_chunk) labeled pairs
  ✓ Domain vocabulary is genuinely specialized
  ✓ General model retrieval benchmarks below quality threshold
  ✓ MLOps infrastructure exists to retrain and evaluate

Fine-tuning is NOT worth it when:
  ✗ Fewer than 5,000 labeled pairs (won't generalize)
  ✗ Domain language close enough to general English
  ✗ No retrieval quality benchmarks to measure improvement
  ✗ No infrastructure to maintain a custom model

Generating labeled pairs without a large annotation team:
  Use an LLM to generate synthetic (query, relevant_chunk) pairs
  from existing KB documents.
  "Hardship Program Eligibility" document generates queries like:
  "what are the requirements for payment deferral?"
  automatically. Thousands of training pairs from documents you have.
```

### Embedding Dimensions Trade-off

```
text-embedding-3-small  : 1536 dims  ~5ms inference
text-embedding-3-large  : 3072 dims  ~25ms inference
Cohere embed-v3         : 1024 dims  ~8ms inference

More dimensions = more expressive = better quality (generally)
More dimensions = larger vectors = slower ANN = higher storage cost

At 50,000 KB chunks (typical enterprise banking platform scale):
  1536-dim : ~300MB storage — trivial
  3072-dim : ~600MB storage — trivial

At 100M customer queries per day, embedding inference latency
matters more than storage. text-embedding-3-small is 5x faster
than large with ~15% quality loss.
For financial policy retrieval, that tradeoff typically favors small.
Run offline benchmarks on labeled test set to confirm.
```

### Embedding Model Versioning — The Hidden Operational Problem

```
When you upgrade the embedding model (v1 → v2):
  New model produces DIFFERENT vectors for same text.
  v1 and v2 vectors are NOT comparable.
  Cannot mix them in the same index.

Consequence:
  Must re-embed the ENTIRE knowledge base on model upgrade.
  Cannot use new model for retrieval until re-embedding is complete.
  Re-embedding 50,000 chunks takes time and API cost.

Solution: version tracking + blue-green index cutover

chunk_record = {
    "chunk_id"        : "KB-HARD-001-chunk-3",
    "raw_text"        : "Customers with 2+ missed payments...",
    "vector"          : [...1536 floats...],
    "embedding_model" : "text-embedding-3-small-v1",  ← versioned
    "embedded_at"     : "2026-03-15T02:00:00Z"
}

Upgrade process:
  1. Populate new index (new model) in background
  2. Old index stays live — all queries served by old index
  3. Run quality validation on new index (precision@3 threshold)
  4. Cut over traffic atomically when validation passes
  5. Retire old index after 30-day grace period

Same principle as blue-green model deployment.
Never cut over until new version fully validated.
```

---

## 2c — Knowledge Base Update Pipeline

### The Problem

Policy documents change. A regulatory update might change the hardship
deferral threshold from $500 to $750. If that document isn't re-embedded
promptly, agents continue retrieving old policy. In a regulated environment,
this is not a quality issue — it's a compliance issue.

### Full Update Pipeline

```
TRIGGER: Policy document updated in source CMS
        │
        ▼
STEP 1: Change Detection
  Compare new version to previous — compute diff.
  Metadata-only update (no content change) → skip re-embedding.
  Content changed → trigger re-embedding pipeline.
        │
        ▼
STEP 2: Soft Deprecation
  Mark OLD chunks: ACTIVE → DEPRECATED (not DELETED)
  Old chunks still serve queries during re-embedding.
  Prevents a window where no policy is available.
        │
        ▼
STEP 3: Chunking
  New document version chunked (same strategy as initial indexing).
  Chunk IDs include document version:
    "KB-HARD-001-v2.4-chunk-3"  ← new
    "KB-HARD-001-v2.3-chunk-3"  ← old (deprecated)
        │
        ▼
STEP 4: Embedding
  New chunks → embedding model → new vectors.
  Stored in STAGING index — NOT production yet.
        │
        ▼
STEP 5: Quality Validation
  Run labeled test queries against new chunk vectors.
  precision@3 must be ≥ 85% on test set.
  If validation fails → alert, do NOT promote to production.
        │
        ▼
STEP 6: Atomic Cutover
  Promote new chunks to production index.
  Mark old chunks RETIRED (preserved for audit, not served).
  In-flight sessions (active Redis TTL) → served by old chunks
  until session expires (max 5 min TTL).
  New sessions → new chunks immediately.
        │
        ▼
STEP 7: Audit Log
  { document_id, old_version, new_version,
    chunks_added, chunks_retired, cutover_timestamp,
    embedding_model_version, validation_score }
        │
        ▼
STEP 8: Retirement (after 30 days)
  RETIRED chunks removed from index.
  Raw text + metadata archived to cold storage (S3).
  Vector deleted — no longer searchable.
  Audit log record permanently preserved.
```

### The In-Flight Session Problem

```
Session started:   10:42:33
Policy updated:    10:44:00
Session TTL ends:  10:47:33

For 3m 33s, that session retrieves old policy chunks.

This is INTENTIONAL:
  - Session context was assembled in the old-policy world
  - Switching policy mid-session creates reasoning inconsistency
  - Maximum inconsistency window is bounded by TTL (5 minutes)
  - Audit log records which KB version was used per retrieval

Design tradeoff: session consistency > instant policy propagation.
Acceptable because max staleness window = TTL duration.
```

### KB Version Tagging

```python
# Every retrieval event records the KB version active at that moment
audit_record = {
    "event_type"  : "VECTOR_RETRIEVAL",
    "session_id"  : "sess_C002_20260511_104233_f3a2b9",
    "kb_version"  : "2026-05-10",       # date-stamped daily snapshot
    "chunks_used" : [
        { "chunk_id": "KB-HARD-001-v2.3-chunk-3", "doc_version": "2.3" },
        { "chunk_id": "KB-PAY-007-v1.8-chunk-2",  "doc_version": "1.8" },
    ]
}
# Answers: "What policy was the agent following on May 11th?"
# → Pull doc version from audit record, retrieve from cold storage.
```

---

## 2d — Hybrid Search

### The Limitation of Pure Vector Search

Vector search finds semantically similar documents. It has one weakness:
**it can miss exact matches.**

```
Query: "CFPB Regulation E section 1005.11"

Vector search:
  Finds documents ABOUT Regulation E dispute resolution ✓
  May not rank the document CONTAINING the exact citation at top ✗
  (vector captures meaning — not exact string presence)

BM25 keyword search:
  Finds documents CONTAINING "1005.11" exactly ✓
  Misses documents about the same topic using different wording ✗

Hybrid: combines both — semantic understanding + exact term recall ✓
```

### Hybrid Architecture

```
Query string
    │
    ├────────────────────────────────────────┐
    │                                        │
    ▼                                        ▼
VECTOR SEARCH                           BM25 SEARCH
Query → embedding → ANN search          Tokenize query
→ top 20 by cosine similarity           → BM25 score each doc
(semantic relevance)                    → top 20 by term match
    │                                        │
    └──────────────────┬─────────────────────┘
                       │
                       ▼
            RECIPROCAL RANK FUSION (RRF)
            Score = Σ 1/(k + rank_in_list)   k=60
            Uses rank only — not raw scores
            (raw scores are on different scales — not directly comparable)

            Example: KB-HARD-001-chunk-3
              Vector rank: 1  → 1/(60+1) = 0.0164
              BM25 rank:   3  → 1/(60+3) = 0.0159
              RRF score:       0.0323

            A document in top 5 of BOTH lists beats
            a document that is #1 in only ONE list.
                       │
                       ▼
            TOP 20 MERGED CANDIDATES
                       │
                       ▼
            CROSS-ENCODER RE-RANKING
            → top 3–5 final results
```

### Why RRF and Not Score Averaging

```
Cosine similarity: 0.0 to 1.0
BM25 score:        0 to unbounded (corpus-size dependent)

Averaging requires normalization — brittle and scale-dependent.
RRF uses only rank — always comparable across any two lists.
Document ranked #1 in vector list gets same RRF contribution
whether its similarity score is 0.99 or 0.72.
RRF is robust, easy to implement correctly, and well-validated
in production retrieval systems.
```

### Modern Unified Approach — Sparse + Dense in One Index

```python
# Single query, hybrid-scored results — no separate merge step
results = vector_db.query(
    vector        = query_dense_vector,    # from embedding model
    sparse_vector = query_sparse_vector,   # from BM25 tokenizer
    alpha         = 0.7,   # 0=pure BM25, 1=pure vector, 0.7=mostly semantic
    top_k         = 20,
    filter        = { "product_line": "credit_card", "jurisdiction": "US" }
)

# alpha is tunable — sweep 0.3 to 0.9 on labeled test set
# For financial policy retrieval: 0.65–0.75 typically wins
# More semantic than keyword — but exact citations still matched
```

### When to Use Hybrid vs. Pure Vector

```
Use PURE VECTOR when:
  ✓ All queries are natural language (no exact terms to match)
  ✓ KB uses consistent normalized language
  ✓ Simplicity is a priority

Use HYBRID when:
  ✓ Queries may include exact regulatory citations (12 CFR 1005.11)
  ✓ KB contains product codes, account types, named programs
  ✓ Regulated domain where missing a specific rule is costly
  ✓ Retrieval benchmarks show vector search missing exact matches

For a regulated banking platform: HYBRID is the correct choice.
Agents construct queries from natural language customer signals +
KB contains regulatory citations and named policy programs.
Cost of missing a compliance rule > operational overhead of running both.
```

---

## Service Interface — Layer 2

```python
class VectorSearchService:

    def retrieve(
        self,
        session_id : str,       # reads customer profile from Redis
        scenario   : str,       # "payment_risk_intervention"
        top_k      : int = 3    # number of chunks to return
    ) -> RetrievalResult:
        """
        Constructs query from customer profile.
        Runs hybrid search against knowledge base.
        Returns top-k re-ranked policy chunks.
        Writes audit log entry.
        SLA: 60ms at p99.
        """

class RetrievalResult:
    session_id      : str
    query           : str               # constructed query (for audit)
    chunks          : list[PolicyChunk] # top-k re-ranked chunks
    kb_version      : str               # KB version active at retrieval time
    retrieval_ms    : int
    embedding_model : str
    reranker_model  : str

class PolicyChunk:
    chunk_id        : str
    document_id     : str
    document_title  : str
    document_type   : str   # POLICY | REGULATION | PLAYBOOK | COMPLIANCE
    doc_version     : str
    raw_text        : str
    rerank_score    : float
```

---

## Dynamic Query Construction

```python
def build_retrieval_query(profile: CustomerProfile, scenario: str) -> str:
    """
    Constructs semantically rich query from customer signals.
    Rich query → vectors close to relevant policy in embedding space.
    Static query → misses policy specificity.
    """

    if scenario == "payment_risk_intervention":
        risk_level = (
            "critical" if profile.signals.risk_score > 0.7
            else "high" if profile.signals.risk_score > 0.5
            else "moderate"
        )
        hardship_signals = []
        if profile.card.missed_pmts >= 2:
            hardship_signals.append(f"{profile.card.missed_pmts} missed payments")
        if profile.banking.checking < 500:
            hardship_signals.append(f"checking balance ${profile.banking.checking:.2f}")
        if not profile.banking.direct_dep:
            hardship_signals.append("no direct deposit")

        return (
            f"Customer with {risk_level} payment risk. "
            f"Signals: {', '.join(hardship_signals)}. "
            f"Card utilization {profile.card.utilization:.0%}. "
            f"Payment propensity {profile.signals.payment_propensity:.0%}. "
            f"Intervention options, hardship program eligibility, "
            f"payment deferral, contact strategy."
        )

# Marcus Webb produces:
# "Customer with critical payment risk. Signals: 2 missed payments,
#  checking balance $312.40, no direct deposit. Card utilization 76%.
#  Payment propensity 31%. Intervention options, hardship program
#  eligibility, payment deferral, contact strategy."
```

---

## Full Data Flow — Marcus Webb, Payment Risk Intervention

### Step 0 — Layer 2 Receives from Layer 1
```
Inputs: session_id "sess_C002_20260511_104233_f3a2b9", scenario "payment_risk_intervention"
Layer 2 reads CustomerProfile from Redis TTL store (consumer — never writes).
```

### Step 1 — Query Construction (T+0ms to T+2ms)
```
Profile signals extracted → dynamic query constructed:
"Customer with critical payment risk. Signals: 2 missed payments,
 checking balance $312.40, no direct deposit. Card utilization 76%.
 Payment propensity 31%. Intervention options, hardship program
 eligibility, payment deferral, contact strategy."
```

### Step 2 — Query Embedding (T+2ms to T+20ms)
```
Query string → embedding model API → 1536-dim dense vector
query_vector = [0.031, -0.412, 0.198, 0.067, -0.334, ...]
+ sparse BM25 vector computed from query tokens
Latency: ~18ms
```

### Step 3 — Metadata Pre-filter (T+20ms)
```
Filter: product_line="credit_card", jurisdiction="US"
KB total: 4,200 chunks → after filter: 847 chunks
ANN search runs on 847, not 4,200.
```

### Step 4 — Hybrid ANN + BM25 Search (T+20ms to T+25ms)
```
Dense vector ANN (HNSW) + sparse BM25 run in parallel against 847 chunks.
RRF merge produces unified top-20 candidate list. 5ms total.

Top 5 after RRF merge:
  1. KB-HARD-001-chunk-3  (Hardship Program Eligibility)
  2. KB-PAY-007-chunk-2   (Payment Intervention Playbook — High Risk)
  3. KB-COMP-003-chunk-1  (Contact Frequency Guidelines)
  4. KB-HARD-002-chunk-1  (Hardship Escalation Thresholds)
  5. KB-PAY-007-chunk-4   (Payment Propensity + Rate Reduction)
```

### Step 5 — Cross-Encoder Re-ranking (T+25ms to T+53ms)
```
Top 20 candidates re-scored by cross-encoder (full attention, query + chunk together).
More expensive but more precise than ANN proximity alone. 28ms for 20 candidates.

Re-ranked top 3:
  1. KB-HARD-001-chunk-3  score: 0.961
     "Customers with 2+ missed payments in 90 days AND checking balance
      below $500 are eligible for 90-day hardship deferral program..."

  2. KB-PAY-007-chunk-2   score: 0.934
     "For risk score > 0.65: recommended sequence is SMS reminder →
      hardship call → rate reduction offer. Payment propensity < 35%
      + utilization > 70% = structural constraint — rate reduction
      more effective than reminder alone..."

  3. KB-COMP-003-chunk-1  score: 0.918
     "Maximum 3 outbound contacts per customer per 7-day window.
      SMS, push, and phone each count as 1 contact..."

Note: KB-COMP-003 jumped from rank 5 (ANN) to rank 3 (re-ranked).
Cross-encoder recognized contact frequency compliance is highly
relevant given this is an intervention decision.
```

### Step 6 — Audit Log (T+53ms to T+54ms)
```python
{ "audit_id": "aud_vec_20260511_104233_C002",
  "event_type": "VECTOR_RETRIEVAL",
  "session_id": "sess_C002_20260511_104233_f3a2b9",
  "query": "Customer with critical payment risk...",
  "chunks_retrieved": [
    { "chunk_id": "KB-HARD-001-chunk-3", "score": 0.961, "doc_version": "2.3" },
    { "chunk_id": "KB-PAY-007-chunk-2",  "score": 0.934, "doc_version": "1.8" },
    { "chunk_id": "KB-COMP-003-chunk-1", "score": 0.918, "doc_version": "3.1" }
  ],
  "embedding_model": "text-embedding-3-small-v2",
  "reranker_model":  "cross-encoder-ms-marco-v3",
  "kb_version":      "2026-05-10",
  "retrieval_ms":    54 }
```

### Step 7 — Handoff to Orchestrator (T+55ms)
```
Policy context packaged (top 3 chunks + metadata) → handed to Orchestrator.
Orchestrator passes both session_id (→ customer profile) and policy context to agents.
```

### Timeline Summary
```
T+0ms    Layer 2 reads customer profile from Redis.
T+2ms    Dynamic query constructed from profile signals.
T+20ms   Query embedding complete (dense + sparse vectors).
T+20ms   Metadata pre-filter: 4,200 → 847 chunks.
T+25ms   Hybrid ANN + BM25 search complete. Top 20 via RRF.
T+53ms   Cross-encoder re-ranking complete. Top 3 selected.
T+54ms   Audit log written (KB version, chunk IDs, model versions).
T+55ms   Policy context handed to Orchestrator.

Layer 2 latency       : 55ms
Layer 1 latency       : 167ms
Cumulative so far     : 222ms
```

---

## Key Design Decisions — Layer 2

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Chunking strategy | Hierarchical (doc → section → paragraph) | Prevents orphaned facts. Surfaces exceptions alongside rules. Essential for compliance documents with conditional logic. |
| Chunk size | 256–512 tokens, 10% overlap | Sweet spot for policy docs. Too small = isolated facts. Too large = averaged meaning. |
| Embedding model | General model first, fine-tune if precision < 85% | Fine-tuning requires 10K+ labeled pairs. Validate need before investing. Use synthetic pairs from LLM to bootstrap. |
| Embedding versioning | Model version stored per chunk | Model upgrades require full re-embedding. Blue-green index cutover prevents serving mixed-version vectors. |
| Search strategy | Hybrid ANN + BM25 via RRF | Pure vector misses exact regulatory citations. Pure BM25 misses semantic paraphrase. Hybrid covers both. |
| Merge strategy | RRF not score averaging | Scores are on incomparable scales. RRF uses rank only — robust and scale-invariant. |
| Alpha tuning | 0.65–0.75 for policy retrieval | Sweep on labeled test set. Mostly semantic but exact citations still matched. |
| Re-ranking | Cross-encoder after ANN | ANN fast but approximate (recall). Cross-encoder slow but precise (precision). Two-stage gives both. |
| Query construction | Dynamic from profile signals | Static query misses policy specificity. Rich query puts embedding close to the right policy vectors. |
| KB update strategy | Soft deprecate → validate → atomic cutover | Never leave a gap where no policy is served. In-flight sessions use old chunks until TTL expires — bounded staleness. |
| In-flight session consistency | Old chunks until session TTL | Session started in old-policy world. Mid-session switch creates reasoning inconsistency. Bounded by 5min TTL. |
| KB version in audit log | Date-stamped snapshot per retrieval | Regulatory requirement. "What policy was active at decision time?" must be answerable months later. |

---

## Interview Talking Points — Layer 2

- "Vector search is not enough for a regulated banking platform. Regulatory
  citations, product codes, named programs — these need exact term matching
  that vector search alone doesn't guarantee. Hybrid search with BM25
  covers both semantic understanding and exact recall."

- "The query is the most underappreciated component. A static query
  like 'payment risk' retrieves generic policy. A dynamically constructed
  query from the customer's actual signals — 2 missed payments, $312
  checking balance, 76% utilization — puts the embedding vector precisely
  adjacent to hardship program eligibility criteria in the vector space."

- "Two-stage retrieval — ANN for recall, cross-encoder for precision —
  is the production pattern. ANN is fast but approximate. Cross-encoder
  is expensive but precise. You can't run cross-encoder on 50,000 chunks
  at query time. You run it on the 20 candidates ANN already filtered for you."

- "KB version is audit lineage — the same principle as model versions in
  the feature store. When a policy changes and an agent makes a different
  decision next week, you can prove exactly which version of the policy
  each decision was based on."

---

## Technology Mapping — Layer 2

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Vector Database | Pinecone / Weaviate / Qdrant | OpenSearch with k-NN plugin |
| Embedding Model | Any API (OpenAI, Cohere) | Amazon Titan Embeddings / Bedrock |
| Cross-Encoder | Hugging Face cross-encoder | SageMaker endpoint (custom model) |
| Knowledge Base Store | S3 + metadata DB | S3 + DynamoDB |
| Indexing Pipeline | Any batch job | AWS Glue or SageMaker Processing Job |
| Audit Log | Append-only store | DynamoDB + S3 |

---

*Layer 2 + deep dives (chunking, embedding, KB update, hybrid search) completed: May 2026*


---
---

# LAYER 3 — Multi-Agent Orchestration

## Problem This Layer Solves

Layers 1 and 2 have produced two things: a unified customer profile and
relevant policy context. The Orchestrator takes both, decides which agents
to invoke and in what order, passes each agent the right context, collects
their outputs, and manages pipeline state — including what happens when an
agent fails, times out, or returns an unexpected result.

The core architectural question: **hub-and-spoke or peer-to-peer?**

**Peer-to-peer:** agents call each other directly. Agent A decides it needs
more information and calls Agent B directly.

**Hub-and-spoke:** agents never call each other. Every inter-agent
communication routes through the Orchestrator. Agent A returns output to
the Orchestrator. The Orchestrator decides whether to invoke Agent B.

For a regulated environment, hub-and-spoke is the only defensible choice.

```
Peer-to-peer problems:
  → No central point where policy can be enforced between agent calls
  → Debugging a production failure requires tracing arbitrary agent calls
  → An agent can invoke another agent it should not have access to
  → Audit trail is distributed across agents — hard to reconstruct

Hub-and-spoke gives you:
  → Every inter-agent communication passes through one routing layer
  → Policy enforcement happens at the hub before any handoff
  → Full audit trail in one place — orchestrator logs every hop
  → Failure handling is centralized — one place to define fallback behavior
```

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Routing | Two agents always run sequentially | Static pipeline with conditional branches |
| Agent context | System prompt + customer summary string | Typed AgentContext object with authorized_tools |
| Tool use | Implicit in LLM call | Explicit tool registry with authorization enforcement |
| Prior outputs | Passed as prompt text | Typed AgentOutput objects in prior_outputs list |
| Failure handling | None — errors surface in UI | Timeout, schema validation, tool auth violation — all route to HumanReviewQueue |
| Pipeline state | None | Written to Redis after each step — recovery checkpoint |
| Audit log | Execution log panel only | DynamoDB record per agent hop, per tool call, per branch decision |

---

## Orchestrator's Four Responsibilities

**1. Routing** — which agent to invoke next, based on scenario and prior agent output.

**2. Context threading** — passing the right typed context to each agent:
session_id for customer profile, policy chunks from Layer 2, prior agent outputs.

**3. Tool authorization gate** — before any tool call executes, check that
the requesting agent has that tool in its authorized list. Enforced at the
tool registry level — not by the agent or by prompt.

**4. Failure handling** — timeout, schema validation failure, tool auth
violation. All route to HumanReviewQueue with full context. Never silent failure.

---

## Agent Context — Typed Contract

```python
@dataclass
class AgentContext:
    session_id       : str              # → read customer profile from Redis
    customer_id      : str
    scenario         : str
    pipeline_step    : int
    trace_id         : str              # distributed trace ID — follows every hop

    policy_chunks    : list[PolicyChunk]  # top 3 chunks from Layer 2
    prior_outputs    : list[AgentOutput]  # empty for first agent

    authorized_tools : list[str]   # enforced by tool registry — not by prompt
    max_tokens       : int
    timeout_ms       : int
```

---

## Agent Tool Authorization

Agents propose — they never execute. Execution is gated by Layer 4.
Tool authorization is enforced at the tool registry before any call
reaches a downstream system.

```python
AGENT_TOOLS = {
    "RiskScoringAgent": [
        "query_transaction_history",    # read-only
        "read_customer_profile",        # read-only
        "compute_risk_signals",         # compute-only
    ],
    "InterventionAgent": [
        "read_customer_profile",        # read-only
        "query_intervention_history",   # read-only
        "propose_intervention",         # propose — does NOT execute
    ],
    "ResolutionAgent": [
        "read_customer_profile",
        "query_dispute_history",
        "propose_resolution",           # propose — does NOT execute
    ]
}

# "propose" vs "execute" is a critical design distinction.
# No agent in Layer 3 writes to any customer-facing system.
# All proposed actions pass to Layer 4 (Guardrails) before execution.
```

---

## Static Routing with Conditional Branches

```
Scenario: payment_risk_intervention

Pipeline definition (pre-configured, not dynamic):

  Step 1: RiskScoringAgent
    timeout: 8000ms
    authorized_tools: [query_transaction_history,
                       read_customer_profile, compute_risk_signals]
    output_schema: RiskAssessment

  Step 2: BRANCH on risk_level  ← deterministic Orchestrator rule
    IF risk_level IN [HIGH, CRITICAL] → InterventionAgent
    ELSE                              → MonitoringAgent

  Step 3: InterventionAgent (or MonitoringAgent)
    timeout: 10000ms
    authorized_tools: [read_customer_profile,
                       query_intervention_history, propose_intervention]
    output_schema: InterventionProposal

  On any step failure: → HumanReviewQueue

Branch decisions are logged explicitly.
Not the agent deciding — the Orchestrator applying a deterministic rule.
```

---

## Failure Handling

```
Failure Type         Trigger                   Response
──────────────────────────────────────────────────────────────────
TIMEOUT              Agent exceeds timeout_ms   → Route to HumanReviewQueue
                                                  if step is critical.
                                                  Skip if step is optional.

SCHEMA_VALIDATION    Agent output missing        → Do NOT retry.
                     required field              → Route to HumanReviewQueue.
                                                  → Alert to platform team.

TOOL_AUTH_VIOLATION  Agent calls tool not in     → Block immediately.
                     authorized_tools list       → Security alert fires.
                                                  → Route to HumanReviewQueue.
                                                  → Flag agent for review.

TRANSIENT_ERROR      Network/infra error         → Retry once.
                                                  → If retry fails → HumanReviewQueue.

HumanReviewQueue always receives:
  full customer context (session_id → Redis),
  all prior agent outputs,
  failure reason and step,
  proposed actions if any were produced before failure.
```

---

## Full Data Flow — Marcus Webb, Payment Risk Intervention

### Entry State (T+222ms)
```
From Layer 1: session_id "sess_C002_20260511_104233_f3a2b9",
              partial_context=True, ttl_expires_at=10:47:33
From Layer 2: 3 policy chunks (KB-HARD-001, KB-PAY-007, KB-COMP-003)
Cumulative latency so far: 222ms
```

### Step 0 — Pipeline Initialization (T+222ms)
```
Orchestrator reads CustomerProfile from Redis using session_id.
Assigns trace_id: "trace_20260511_104233_C002"
Selects pipeline: payment_risk_intervention (static definition)
Logs: pipeline initialized, steps, policy_chunks_used, trace_id
```

### Step 1 — RiskScoringAgent (T+223ms to T+2,847ms)
```
AgentContext assembled:
  authorized_tools: [query_transaction_history, read_customer_profile,
                     compute_risk_signals]
  prior_outputs: []
  policy_chunks: [KB-HARD-001, KB-PAY-007, KB-COMP-003]

System prompt includes:
  - Role and output schema
  - Authorized tools only
  - Policy chunks verbatim
  - "Note: CRM unavailable. Do not assert NPS or tenure."
  - Full customer profile from Redis

Tool calls made:
  1. read_customer_profile(session_id) → Redis read ✓
  2. query_transaction_history(customer_id="C002", days=90)
     → 47 transactions, last payment 2026-04-01 (41 days ago),
       3 NSF events/30d, avg monthly spend $1,240 ✓

RiskAssessment output:
{
  risk_level     : "CRITICAL",
  risk_score     : 0.71,
  confidence     : 0.89,
  lower_confidence_reason: "CRM unavailable — NPS and tenure absent",

  primary_signals: [
    "2 missed payments in 90 days — meets hardship threshold",
    "Card utilization 76% — above 70% structural risk threshold",
    "Checking balance $312.40 — below $500 hardship eligibility threshold",
    "41 days since last payment — past due $420",
    "3 NSF events in last 30 days — acute cash flow stress",
    "No direct deposit — income instability signal"
  ],

  protective_signals: [
    "14 app logins in 30 days — customer engaged and aware",
    "SMS and push enabled — reachable",
    "0 interventions in last 7 days — contact cap not at risk"
  ],

  policy_match: {
    hardship_eligible: true,
    reason: "2+ missed payments AND checking < $500 — both criteria met",
    policy_ref: "KB-HARD-001-v2.3"
  },

  recommended_next: "InterventionAgent"
}

Schema validation: PASSED
Orchestrator logs: step 1 complete, risk_level=CRITICAL, latency=2,624ms,
                   tool_calls=[read_customer_profile, query_transaction_history]
```

### Step 2 — Branch Decision (T+2,848ms)
```
Condition: risk_level IN ["HIGH","CRITICAL"] → True (CRITICAL)
Route to: InterventionAgent ✓
Orchestrator logs: { step: BRANCH, condition: "risk_level=CRITICAL",
                     routed_to: "InterventionAgent" }
Branch decision is Orchestrator's deterministic rule — not agent's choice.
```

### Step 3 — InterventionAgent (T+2,848ms to T+6,291ms)
```
AgentContext assembled:
  authorized_tools: [read_customer_profile, query_intervention_history,
                     propose_intervention]
  prior_outputs: [RiskScoringAgent output from Step 1]

Tool calls made:
  1. read_customer_profile(session_id) → Redis read ✓
  2. query_intervention_history(customer_id="C002", days=90)
     → last intervention: SMS_REMINDER 2026-04-28, outcome: NO_RESPONSE
       total_90d: 2, intervention_7d: 0 ✓

  Insight: last SMS went unanswered → escalate per KB-PAY-007 playbook.

InterventionProposal output:
{
  intervention_type    : "HARDSHIP_PROGRAM_ENROLLMENT_OFFER",
  intervention_channel : "MOBILE_PUSH",

  customer_message     : "We noticed your account has some recent activity
    we want to help with. You may qualify for our Hardship Assistance
    Program — which could pause your minimum payment for up to 90 days.",

  internal_note        : "Customer meets KB-HARD-001-v2.3 eligibility:
    2 missed payments + checking $312.40 < $500. Prior SMS (2026-04-28)
    no response — playbook KB-PAY-007 escalates to mobile push + in-app
    deep link. NSF pattern + no direct deposit = structural constraint,
    not temporary — hardship more appropriate than rate reduction now.",

  proposed_actions: [
    { action_id: "ACT-001", action_type: "SEND_PUSH_NOTIFICATION",
      requires_approval: false },
    { action_id: "ACT-002", action_type: "CREATE_HARDSHIP_ENROLLMENT_CASE",
      case_type: "PAYMENT_DEFERRAL_90_DAY", amount: 420.00,
      requires_approval: true,
      approval_reason: "Deferral $420 — below $5000 supervisor threshold.
                        Standard approval queue." }
  ],

  policy_compliance: {
    contact_frequency_ok: true,
    reason: "0 contacts in last 7 days — under 3/7d cap",
    policy_ref: "KB-COMP-003-v3.1"
  },

  estimated_impact: "34% improvement in on-time payment probability
    per KB-PAY-007-v1.8 hardship effectiveness data",

  fallback_if_no_response: "If no engagement in 7 days, escalate to
    outbound call — schedule for 2026-05-18."
}

Schema validation: PASSED
Orchestrator logs: step 3 complete, intervention_type=HARDSHIP_PROGRAM_ENROLLMENT_OFFER,
                   requires_approval=true, latency=3,443ms
```

### Step 4 — Pipeline State Checkpoint (T+6,292ms)
```python
# Written to Redis — recovery point if Orchestrator crashes
redis.set(
    key   = "session:sess_C002_20260511_104233_f3a2b9:pipeline_state",
    value = {
        "status"          : "PENDING_GUARDRAILS",
        "steps_completed" : [step1_summary, branch_summary, step3_summary],
        "pending_actions" : [ACT-001, ACT-002]
    },
    ex = 300   # same TTL as customer profile
)
```

### Step 5 — Orchestration Audit Log (T+6,293ms)
```python
# DynamoDB — permanent record of every agent hop and tool call
{
  "audit_id"       : "aud_orch_20260511_104233_C002",
  "event_type"     : "ORCHESTRATION_COMPLETE",
  "trace_id"       : "trace_20260511_104233_C002",
  "pipeline_steps" : [
    { "step": 1, "agent": "RiskScoringAgent",
      "tool_calls": ["read_customer_profile", "query_transaction_history"],
      "risk_level": "CRITICAL", "latency_ms": 2624,
      "output_hash": "sha256:3d9f1a..." },
    { "step": "BRANCH", "condition": "risk_level=CRITICAL",
      "routed_to": "InterventionAgent" },
    { "step": 3, "agent": "InterventionAgent",
      "tool_calls": ["read_customer_profile", "query_intervention_history"],
      "intervention_type": "HARDSHIP_PROGRAM_ENROLLMENT_OFFER",
      "latency_ms": 3443, "output_hash": "sha256:7b2e4c..." }
  ],
  "total_latency_ms"       : 6293,
  "proposed_actions"       : ["SEND_PUSH_NOTIFICATION",
                               "CREATE_HARDSHIP_ENROLLMENT_CASE"],
  "requires_approval"      : true,
  "status"                 : "PENDING_GUARDRAILS"
}
```

### Step 6 — Handoff to Layer 4 (T+6,294ms)
```
OrchestratorOutput {
  trace_id        : "trace_20260511_104233_C002",
  session_id      : "sess_C002_20260511_104233_f3a2b9",
  proposed_actions: [ACT-001 (no approval), ACT-002 (approval required)],
  policy_compliance: { contact_frequency_ok: true },
  risk_assessment : { risk_level: CRITICAL, confidence: 0.89 },
  orchestration_ms: 6294
}
→ Passed to Layer 4 (Guardrails). No action executes until Layer 4 approves.
```

### Timeline Summary
```
T+222ms    Orchestrator init. Redis read. Pipeline selected.
T+223ms    RiskScoringAgent invoked.
T+2,847ms  RiskScoringAgent returns CRITICAL. Schema validated.
T+2,848ms  Branch: CRITICAL → InterventionAgent.
T+2,848ms  InterventionAgent invoked with prior output.
T+6,291ms  InterventionAgent returns proposal. Schema validated.
T+6,292ms  Pipeline state checkpoint written to Redis.
T+6,293ms  Orchestration audit log written to DynamoDB.
T+6,294ms  Handoff to Layer 4 (Guardrails).

Layer 3 latency       : 6,072ms (dominated by 2 LLM calls)
Cumulative so far     : 6,294ms
LLM breakdown         : RiskScoringAgent 2,624ms | InterventionAgent 3,443ms
```

---

## Key Design Decisions — Layer 3

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Routing pattern | Hub-and-spoke | Peer-to-peer has no central policy enforcement point. Audit trail is fragmented. Regulated environment requires central control. |
| Routing type | Static with conditional branches | Dynamic routing is hard to audit. Branching conditions are deterministic Orchestrator rules — not agent decisions. |
| Tool authorization | Registry-enforced allowlist per agent | Prompt-based tool restriction is bypassable. Registry enforcement is structural — cannot be prompt-injected away. |
| Agent action model | Propose only — never execute | Agents in Layer 3 never write to customer-facing systems. All proposed actions pass to Guardrails (Layer 4) before execution. |
| Context threading | Typed AgentContext with prior_outputs list | Freeform prompt assembly is brittle. Typed contract ensures every agent receives exactly what it needs and nothing more. |
| Pipeline state | Written to Redis after each step | Recovery checkpoint. If Orchestrator crashes mid-pipeline, resume from last completed step — don't re-run completed agents. |
| Schema validation | Reject invalid output — don't retry | Schema failure = agent logic issue, not transient error. Pass invalid output downstream = compounding errors. Reject and route to human. |
| Failure destination | HumanReviewQueue for all failures | No silent failures. Every pipeline that cannot complete cleanly lands in review with full context for a human to act on. |

---

## Interview Talking Points — Layer 3

- "Hub-and-spoke is the only defensible orchestration pattern in a regulated
  environment. Peer-to-peer means no central enforcement point, fragmented
  audit trail, and agents that can call other agents without any policy gate
  in between."

- "Agents in this platform propose — they never execute. The distinction is
  architectural, not just semantic. Every proposed action passes through the
  Guardrails layer before it touches a customer account. No agent output
  triggers a customer-facing action directly."

- "Tool authorization is enforced at the registry level — not by the agent
  prompt. An agent that tries to call a write tool it isn't authorized for
  gets blocked before the call reaches any downstream system. That's also
  your first defense against prompt injection — even if an attacker injects
  instructions through customer data, the tool the instructions target isn't
  in the agent's allowlist."

- "The pipeline state checkpoint written to Redis after each step is the
  recovery mechanism. If the Orchestrator crashes mid-pipeline, the platform
  resumes from the last completed step. You never re-run a completed agent
  hop — that would double the intervention risk."

---

## Technology Mapping — Layer 3

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Orchestrator Service | Any container runtime | ECS / EKS |
| Pipeline State Store | Redis | ElastiCache for Redis |
| Tool Registry | In-process registry + IAM | Lambda with IAM role per tool |
| LLM Agent Calls | Any LLM API | Amazon Bedrock (Claude) |
| Human Review Queue | Any message queue | SQS + internal review UI |
| Audit Log | Append-only store | DynamoDB + S3 |
| Distributed Tracing | Any tracing system | AWS X-Ray |

---

*Layer 3 completed: May 2026*


---
---

# LAYER 4 — Guardrails & Policy Enforcement

## Problem This Layer Solves

At the end of Layer 3, the Orchestrator has proposed actions for Marcus Webb —
send a push notification and create a hardship enrollment case. Neither has
executed yet. The Guardrails layer is the last gate before any action touches
a customer account.

Its job: answer one question for every proposed action — **should this execute,
be blocked, or be flagged for human review?**

Guardrails is not a quality filter. It is a **hard enforcement layer.**
A blocked action does not proceed — regardless of agent confidence,
regardless of policy match. In a regulated banking environment, this layer
is load-bearing compliance infrastructure. Missing a check that should have
blocked an action is a regulatory event.

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Check types | 6 hardcoded rule checks | Three-category check pipeline: Regulatory, Business Policy, Responsible AI |
| Rule storage | Hardcoded in JS | Versioned rule store (DynamoDB) — no deployment required for rule changes |
| Fairness check | None | BISG-based disparity analysis against 30-day historical decisions |
| Confidence check | None | Per-action-type thresholds, partial context modifier |
| Anomaly detection | None | Control chart monitoring of output distribution |
| Approval queue | UI status only | Full workflow with SLA tiers, escalation ladders, feedback routing |
| Audit log | Execution log panel | Per-action, per-rule evaluation record in DynamoDB |

---

## Three Check Categories — Sequence Matters

```
CATEGORY 1: Regulatory Compliance Checks   ← run first, hardest rules
  Source: Law and regulation (CFPB, ECOA, FCRA, UDAAP, TCPA)
  Failure outcome: BLOCKED — no exceptions, no appeal
  If any regulatory check blocks → stop immediately.
  Do not run business or AI checks.
  Do not route to approval queue.
  Log as regulatory block event.

CATEGORY 2: Business Policy Checks         ← run second
  Source: Bank internal policy (configurable by policy team)
  Failure outcome: BLOCKED (high severity) or FLAGGED (standard)
  All business checks run even if one flags — aggregate result.

CATEGORY 3: Responsible AI Checks          ← run last
  Source: ML team — confidence, fairness, anomaly detection
  Failure outcome: FLAGGED for human review (rarely BLOCKED)
  Requires human judgment — not auto-blocked.

Why this sequence:
  Running fairness checks on an action that violates Reg E is wasteful.
  Hard regulatory blocks stop the pipeline immediately.
  Softer policy and AI flags accumulate before final disposition.
```

---

## Three Action Outcomes

```
APPROVED  → All checks passed. Action authorized for execution.
            Logged in audit trail.

FLAGGED   → One or more checks flagged. Action held.
            Routed to approval queue with full context.
            Human reviews → approves or rejects.
            Logged with flag reasons.

BLOCKED   → Regulatory or severe business policy check failed.
            Action does not proceed. Period.
            No approval queue — blocked means blocked.
            Logged as compliance event. Alert may fire.
```

---

## 4a — Fairness Disparity Analysis

### The Core Problem

You cannot use protected class attributes (race, gender, age, national origin)
as inputs to credit or intervention decisions. ECOA and Fair Housing Act
prohibit it. But you don't need to use them explicitly to discriminate —
proxy variables (zip code, income stability, direct deposit status) can
correlate with protected class and produce disparate outcomes even when
the model never sees demographic data.

Layer 4 checks whether the model's **outputs** are systematically different
across demographic segments — regardless of inputs.

```
Disparate Treatment: explicitly using a protected attribute. Caught at
  model training and code review. Should never reach production.
  Layer 4 is not the primary defense here.

Disparate Impact: a facially neutral policy producing systematically
  different outcomes for different groups. Cannot be fully eliminated
  at training time — input distribution shifts after deployment.
  This is what Layer 4 monitors at runtime.
```

### How It Works — BISG Proxy Methodology

```
Step 1 — Cohort Construction (offline, updated daily)

Using census-level data + zip code + surname analysis, the bank
maintains a probabilistic demographic model:
  customer_id → P(group_A), P(group_B), P(group_C)
  These are probabilities, not labels.
  Never stored per customer. Never passed to agents.
  Used only in aggregate statistical analysis.

This is Bayesian Improved Surname Geocoding (BISG) —
the same methodology CFPB and OCC use in fair lending examinations.
Using the regulator's own methodology makes findings defensible in audit.

Step 2 — Decision Logging (real-time, per action)

Every proposed action logged with:
  action_type, customer_segment, risk_score_bucket,
  intervention_offered (yes/no), zip_code_bucket (not exact)

Protected class attributes NEVER logged per decision.
Only financial signal buckets + action type.

Step 3 — Disparity Detection (runs at guardrails check time)

For each proposed action, statistical query against last 30 days:

  "Among customers with risk_score 0.65–0.80, checking < $500,
   and 2 missed payments — what % received a hardship offer?"

  Returns:
    Group A (BISG prob > 0.7): offer_rate = 0.71
    Group B (BISG prob > 0.7): offer_rate = 0.69
    Group C (BISG prob > 0.7): offer_rate = 0.68

  Disparity ratio: highest/lowest = 0.71/0.68 = 1.044
  Threshold: FLAG if disparity ratio > 1.20
  1.044 < 1.20 → APPROVED ✓

  If > 1.20:
    FLAG action → route to fair lending team
    Do NOT block individual action (individual decision may be correct)
    Aggregate pattern needs investigation
    If pattern persists 7 days → escalate to model retraining
```

### Statistical Tests

```
Four-Fifths Rule (80% Rule):
  If offer rate for any group < 80% of highest-rate group → adverse impact.
  EEOC-endorsed. Adapted for credit interventions.

Z-Test for Proportions:
  Flag only if difference is:
    statistically significant (p < 0.05) AND
    practically significant (> 5% absolute difference)
  Avoids false positives from small sample noise.

Adverse Impact Ratio (AIR):
  AIR = selection_rate_protected / selection_rate_reference
  AIR < 0.80 → potential adverse impact → investigate
  CFPB standard for fair lending examinations.

Test selection by action type:
  Credit decisions, hardship enrollment → AIR + Z-test
  Communication offers (push, SMS)     → Four-fifths rule
```

### What Disparity Analysis Does NOT Tell You

```
It tells you: Group A receives hardship offers at a lower rate than Group B
              for customers with similar financial risk profiles.

It does NOT tell you: why the disparity exists, whether it is caused by
                      the model or real behavioral differences, whether
                      it constitutes illegal discrimination.

The guardrail flags the pattern. The fair lending team adjudicates.
The guardrail is the detection mechanism — not the judge.
```

---

## 4b — Responsible AI Runtime Checks

### Category A — Confidence and Certainty Checks

```python
CONFIDENCE_THRESHOLDS = {
    "SEND_PUSH_NOTIFICATION"          : 0.70,
    "SEND_SMS"                        : 0.70,
    "CREATE_HARDSHIP_ENROLLMENT_CASE" : 0.75,
    "APPLY_RATE_REDUCTION"            : 0.80,
    "ENROLL_PAYMENT_PLAN"             : 0.80,
    "ESCALATE_TO_COLLECTIONS"         : 0.85,
}

# Partial context modifier:
# If sources_degraded is non-empty → raise threshold by +0.05
# CRM unavailable → account action threshold: 0.75 + 0.05 = 0.80

def check_confidence(action_type, confidence, partial_context):
    threshold = CONFIDENCE_THRESHOLDS[action_type]
    if partial_context:
        threshold += 0.05
    if confidence >= threshold:
        return APPROVED
    return FLAGGED(f"Confidence {confidence:.2f} below threshold {threshold:.2f}")
```

### Category B — Output Anomaly Detection

```
What you track (rolling 24-hour window):

  Intervention type distribution:
    Normal:  push=40%, SMS=35%, call=20%, no_action=5%
    Anomaly: push=95%  → model over-recommending push → investigate

  Risk level distribution:
    Normal:  CRITICAL=5%
    Anomaly: CRITICAL=40%  → model over-triggering → feature drift?

  Approval rate:
    Normal:  85% of proposed actions approved by Guardrails
    Anomaly: 45% approval rate over 2 hours → recommendations diverging

  Confidence score distribution:
    Normal:  mean=0.84, std=0.06
    Anomaly: mean=0.71, std=0.14 → model less certain → input shift?

Detection: Shewhart X-bar control charts
  2-sigma breach: log + alert to ML team
  3-sigma breach: pause new pipeline invocations for that scenario
                  route all to human review during investigation
```

### Category C — Input Consistency Checks

```python
# Agent said CRITICAL but signals don't support it?
# Indicates hallucination or misread profile.

def check_output_consistency(agent_output, customer_profile):
    if agent_output.risk_level == "CRITICAL":
        supporting = 0
        if customer_profile.card.missed_pmts >= 2:    supporting += 1
        if customer_profile.card.utilization > 0.70:  supporting += 1
        if customer_profile.banking.checking < 500:   supporting += 1
        if customer_profile.signals.risk_score > 0.65: supporting += 1
        if customer_profile.signals.payment_propensity < 0.40: supporting += 1

        if supporting < 2:
            return FLAGGED(
                f"CRITICAL risk_level has only {supporting}/5 "
                f"supporting signals — possible hallucination"
            )
    return APPROVED

# Marcus Webb: 5/5 signals support CRITICAL → APPROVED ✓
```

---

## 4c — Approval Queue SLA Design

### SLA Tiers

```
Priority   Trigger                              SLA      Escalates To
───────────────────────────────────────────────────────────────────────
URGENT     Regulatory flag, fair lending flag   30 min   VP Compliance
HIGH       CRITICAL risk + account modification  2 hrs   Senior Manager
STANDARD   HIGH risk, amount < $5000             4 hrs   Team Manager
           Partial context on account action
LOW        MEDIUM risk, notification flags       24 hrs  Next business day
```

### Escalation Ladder

```
T+0:        Item enters queue. Assigned to reviewer (round-robin, capacity-balanced).

T+SLA/2:    Reminder notification → assigned reviewer.

T+SLA:      If unreviewed → auto-escalate to reviewer's manager.
            Audit log: SLA_MISSED event.

T+SLA×2:    If manager unreviewed → escalate to VP level.
            Compliance team notified (URGENT + HIGH only).

T+SLA×3:    Auto-disposition: REJECTED (conservative default).
            "Auto-rejected — SLA window exceeded."
            Customer enters alternative pathway.

Why auto-reject rather than auto-approve:
  A hardship case sitting unreviewed for 12 hours is more likely
  a problem than a routine approval. Conservative default protects
  the customer and the bank.
```

### Feedback Routing — Closing the Loop

```
Every approval queue decision feeds back into three systems:

1. Agent Model Feedback
   APPROVED  → positive signal for agent recommendation
   REJECTED  → reviewer selects rejection reason:
               [ ] Risk profile does not support this action
               [ ] Policy criteria not met
               [ ] Customer already has open case of this type
               [ ] Other (free text)

   Rejection reasons aggregated weekly.
   Single rejection reason > 10% of reviews → platform team investigates.
   May indicate agent prompt needs adjustment or KB doc needs updating.

2. Guardrails Rule Calibration
   Check type with > 90% approval rate → possibly too conservative.
               Consider auto-approving with just a log.
   Check type with > 30% rejection rate → possibly should be BLOCK.
               Calibration prevents rubber-stamp approvals and
               over-blocking of legitimate interventions.

3. MLOps Drift Signal
   Accumulating rejection rate = model performance signal.
   RiskScoringAgent recommendations rejected at increasing rates
   → churn model may be drifting → triggers retraining investigation.
```

### Approval Queue Item Schema

```python
ApprovalQueueItem {
    queue_id         : "appr_20260511_104239_ACT002",
    status           : "PENDING",   # → APPROVED | REJECTED | ESCALATED | AUTO_REJECTED
    priority         : "STANDARD",
    created_at       : "2026-05-11T10:42:39Z",
    sla_deadline     : "2026-05-11T14:42:39Z",
    escalation_at    : "2026-05-11T18:42:39Z",
    assigned_to      : "reviewer_007",

    action           : { ACT-002 full detail },
    flag_reasons     : ["B-002: threshold", "AI-002: partial context"],
    context          : { risk_assessment, intervention_rationale,
                         customer_profile_key, policy_match },

    decision         : null,
    decision_by      : null,
    decision_at      : null,
    rejection_reason : null,

    feedback_sent_to_agent  : false,
    feedback_sent_to_mlops  : false
}
```

---

## 4d — Guardrails as a Configurable Rule Engine

### Why Not Hardcoded Rules

```
Hardcoded rules require code change + code review + deployment to update.
A regulation changes January 1st → you are deploying December 31st.
Policy teams cannot update rules without engineering.
No version history → cannot answer "what rule was active on May 11th?"
```

### Rule Store Architecture

```python
# Each rule is a versioned DynamoDB record

{
    "rule_id"        : "B-002",
    "rule_name"      : "Supervisor Approval Threshold",
    "rule_category"  : "BUSINESS_POLICY",
    "version"        : "3.1",
    "effective_date" : "2026-01-01",
    "expires_date"   : null,          # null = currently active
    "created_by"     : "policy_team_user_42",
    "approved_by"    : "compliance_officer_7",

    "condition": {
        "action_type" : "CREATE_HARDSHIP_ENROLLMENT_CASE",
        "field"       : "amount",
        "operator"    : "GREATER_THAN",
        "value"       : 5000
    },
    "outcome"        : "FLAG",
    "severity"       : "MEDIUM",
    "flag_message"   : "Deferral exceeds $5,000 — supervisor approval required"
}

# Rule Loader:
#   Loads active rules at service startup.
#   Hot-reloads every 5 minutes — no restart required.
#   Rule effective on effective_date automatically.
#   Expired rules ignored automatically.
#   No deployment needed for routine rule changes.
```

### Rule Authoring Workflow

```
Step 1: Policy team drafts rule in admin UI (no code).
  - Select action_type from dropdown
  - Configure condition (field, operator, value)
  - Set outcome (BLOCK or FLAG)
  - Set effective date
  - Add justification note

Step 2: Compliance officer reviews and approves.
  - Sees diff against current active version
  - Approves or rejects with comment
  - On approval: new version written to Rule Store
  - Effective date determines when it activates automatically

Engineering team is NOT in this workflow.
Policy changes do not require sprint cycles.
Compliance officer is the gate.
```

### Rule Version History — The Audit Requirement

```
Rule B-002 version history (never deleted):
  v1.0  effective 2024-01-01  threshold: $10,000
  v2.0  effective 2025-03-15  threshold: $7,500
  v3.1  effective 2026-01-01  threshold: $5,000

Regulator asks: "What approval threshold was in effect May 11, 2026?"
  → Query Rule Store: B-002 where
      effective_date ≤ 2026-05-11 AND
      (expires_date IS NULL OR expires_date > 2026-05-11)
  → Returns v3.1: $5,000 threshold
  → Confirmed: Marcus Webb's $420 case correctly routed to standard queue.

Rule-level audit trail + decision-level audit trail together give:
  what rule was active + what decision was made + why.
```

### Rule Testing Before Activation

```
Simulation mode:
  New rule runs against last 30 days of production decisions.
  Report: how many decisions would have changed?
  Large unexpected change → review before activating.

Shadow mode:
  New rule runs alongside current rule in production.
  Current rule determines actual disposition.
  New rule disposition logged separately.
  After 7 days: compare shadow vs. real → confirm expected difference.

Activation:
  Policy team reviews simulation + shadow results.
  Compliance officer confirms difference is intended.
  Rule activates on effective_date.
```

### Rule Ownership by Category

```
Category          Owner             Change Process
────────────────────────────────────────────────────────────────
REGULATORY        Compliance+Legal  Dual approval — overrides sprint cycle
BUSINESS_POLICY   Policy team       Policy + Compliance — 2-week review
RESPONSIBLE_AI    ML team           ML + Compliance — requires model eval
CONFIDENCE        ML team only      ML team approval only — rapid updates

Admin UI enforces ownership boundaries.
Policy team cannot modify REGULATORY rules —
that category is locked to compliance + legal approvers.
```

---

## Full Data Flow — Marcus Webb (Two Proposed Actions)

### Inputs from Layer 3 (T+6,294ms)

```
ACT-001: SEND_PUSH_NOTIFICATION    requires_approval: false
ACT-002: CREATE_HARDSHIP_ENROLLMENT_CASE
         case_type: PAYMENT_DEFERRAL_90_DAY, amount: $420
         requires_approval: true
```

### ACT-001 — All 8 Checks APPROVED (T+6,294ms to T+6,340ms)

```
REGULATORY:
  R-001 UDAAP Communication: conditional language, no guaranteed outcome ✓
  R-002 TCPA Push Consent: behavioral.push_ok = true ✓
  R-003 Fair Lending: disparity ratio 1.044 < 1.20 threshold ✓

BUSINESS POLICY:
  B-001 Contact Frequency: 0 + 1 = 1 ≤ 3/7d cap ✓
  B-002 Duplicate Intervention: last was SMS_REMINDER — different type ✓
  B-003 Approval Threshold: push notification — no monetary action ✓

RESPONSIBLE AI:
  AI-001 Confidence: 0.89 ≥ 0.70 threshold ✓
  AI-002 Partial Context: low-stakes action — CRM absence doesn't change risk ✓
  AI-003 Consistency: CRITICAL + hardship_eligible → push notification correct ✓

Disposition: APPROVED → executes immediately after audit log written.
```

### ACT-002 — 2 Flags, Routed to Approval Queue (T+6,340ms to T+6,381ms)

```
REGULATORY:
  R-001 CFPB Hardship Disclosure: case creation ≠ enrollment, no disclosure obligation ✓
  R-002 Fair Lending: disparity ratio within threshold ✓
  R-003 FCRA Adverse Action: 90-day deferral offer is not adverse action ✓

BUSINESS POLICY:
  B-001 Contact Frequency: case creation is internal — not a customer contact ✓
  B-002 Supervisor Threshold: $420 < $5,000 — standard queue applies ✓
        → FLAGGED: standard approval required (requires_approval=true from agent)
  B-003 Duplicate Case: no open hardship case exists ✓

RESPONSIBLE AI:
  AI-001 Confidence: 0.89 ≥ 0.80 (account action + partial context = 0.75+0.05) ✓
  AI-002 Partial Context: CRM unavailable on account modification
         → FLAGGED: "CRM unavailable — verify tenure/NPS before approving"
  AI-003 Consistency: CRITICAL + hardship_eligible → hardship case correct ✓

Check summary: 7 APPROVED, 2 FLAGGED, 0 BLOCKED
Disposition: FLAGGED → routed to approval queue
  flag_reasons: [B-002: standard approval, AI-002: partial context]
  priority: STANDARD | SLA: 4 hours | reviewer: reviewer_007
```

### Guardrails Audit Log (T+6,381ms)

```python
{
  "audit_id"     : "aud_guard_20260511_104239_C002",
  "event_type"   : "GUARDRAILS_EVALUATION",
  "trace_id"     : "trace_20260511_104233_C002",
  "timestamp"    : "2026-05-11T10:42:39.600Z",

  "actions_evaluated": [
    { "action_id": "ACT-001", "disposition": "APPROVED",
      "checks_run": 8, "checks_passed": 8 },
    { "action_id": "ACT-002", "disposition": "FLAGGED",
      "checks_run": 9, "checks_passed": 7, "checks_flagged": 2,
      "flag_reasons": ["B-002: standard approval threshold",
                       "AI-002: CRM unavailable on account action"],
      "approval_queue_id": "appr_20260511_104239_ACT002",
      "sla_respond_by"   : "2026-05-11T14:42:39Z" }
  ],

  "guardrails_latency_ms": 87,

  "rule_versions_used": {
    "B-002": "3.1",   ← exact rule version active at evaluation
    "R-002": "2.0",
    "AI-002": "1.4"
  }
}
```

### Layer 4 Timeline

```
T+6,294ms   Guardrails receives OrchestratorOutput.
T+6,340ms   ACT-001: 8/8 checks APPROVED. Authorized.
T+6,381ms   ACT-002: 7/9 checks passed, 2 flagged. Routed to queue.
T+6,381ms   Guardrails audit log written (rule versions included).
T+6,382ms   ACT-001 → execution (push notification fires).
T+6,382ms   ACT-002 → approval queue (4-hour SLA).

Layer 4 latency       : 88ms
Cumulative so far     : 6,382ms

Note: 88ms is low because most checks are rule-based lookups.
Fairness disparity analysis (~40ms) is the most expensive check —
statistical query against rolling historical data.
All other checks are policy lookups < 5ms each.
```

---

## Key Design Decisions — Layer 4

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Check sequencing | Regulatory → Business → AI | Hard regulatory blocks stop pipeline immediately. No wasted computation on actions that violate law. |
| Blocked vs. flagged | BLOCK for regulatory, FLAG for policy + AI | Regulatory violations have no gray area. Business and AI findings need human judgment. |
| Fairness methodology | BISG proxy + AIR/Z-test | CFPB uses the same methodology in fair lending exams. Defensible in regulatory audit by design. |
| Individual vs. aggregate | Flag at aggregate, approve individual | Individual decision may be correct even if aggregate pattern has disparity. Human investigates pattern — not individual. |
| Rule storage | Versioned DynamoDB rule store | Policy teams update rules without code deployment. Every rule change has version history. Regulators can query what rule was active on any date. |
| Rule activation | Effective date in rule record | Regulatory deadlines can be met without emergency deployments. Rule activates automatically on the configured date. |
| Rule ownership | Category-level access control | Compliance owns regulatory rules. Policy owns business rules. ML owns AI thresholds. Admin UI enforces this — engineering not in policy update workflow. |
| Confidence thresholds | Per-action-type, partial context modifier | Higher-consequence actions require higher confidence. Degraded context raises the bar. Runtime enforcement of "worse data = less autonomous action." |
| Anomaly detection | Control charts on output distribution | Not just per-decision confidence. Sustained distribution shifts indicate model drift before it becomes visible in business metrics. |
| Auto-reject on SLA miss | Conservative default | Stale unreviewed actions are more likely problems than routine approvals. Conservative default protects customer and bank. |
| Feedback loop | Rejections → agent feedback + MLOps | Approval queue is not a dead end. Reviewer decisions are training signals for agent calibration and model drift detection. |

---

## Interview Talking Points — Layer 4

- "Guardrails is not a quality filter — it's hard compliance infrastructure.
  Three check categories in sequence: regulatory first (any failure = immediate
  block, no exceptions), business policy second (configurable thresholds that
  policy teams update without touching code), responsible AI third (confidence,
  fairness, anomaly detection)."

- "Fairness disparity analysis uses BISG proxy methodology — the same approach
  the CFPB uses in fair lending examinations. We run statistical tests against
  rolling historical decisions to detect if offer rates are diverging across
  demographic cohorts. We never use protected class attributes per customer —
  we detect patterns in aggregate outputs."

- "The rule engine is fully configurable through an admin UI with version
  history on every rule. When a regulator asks what threshold was in effect
  on a specific date, we query the rule store — not git blame."

- "The approval queue is a feedback loop, not a dead end. Reviewer rejections
  aggregate into signals for agent prompt calibration and MLOps retraining
  triggers. A rising rejection rate on RiskScoringAgent recommendations is
  an early warning of model drift — caught here before it shows up in
  business metrics."

---

## Technology Mapping — Layer 4

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Guardrails Service | Any container runtime | ECS / EKS |
| Rule Store | Versioned document store | DynamoDB (versioned records) |
| Rule Loader | In-process cache, hot reload | ElastiCache + DynamoDB streams |
| Fairness Analysis | Any statistical compute | SageMaker Processing Job (batch) |
| Historical Decision Store | Append-only log | S3 + Athena (queryable) |
| Approval Queue | Any message queue + workflow | SQS + Step Functions |
| Approval UI | Internal web app | Internal tooling on ECS |
| Audit Log | Append-only store | DynamoDB + S3 |
| Alerting | Any alerting system | CloudWatch Alarms + SNS |

---

*Layer 4 + deep dives (fairness analysis, responsible AI checks,
approval queue SLA, configurable rule engine) completed: May 2026*


---
---

# LAYER 5 — A/B Evaluation & Model Governance

## Problem This Layer Solves

Layer 4 has authorized ACT-001 for execution. Before it fires, one more
question: **which version of the intervention is most effective?**

The push notification is approved — but should it use Message Variant A
(soft framing: "you may qualify for our Hardship Program") or Variant B
(direct framing: "your account may be at risk")? And how do we know which
works better for customers with Marcus Webb's profile?

Layer 5 has two distinct jobs — do not conflate them:

**Job 1 — A/B Experimentation:** at execution time, route the approved
action to the winning variant based on statistical evidence from historical
experiments. Real-time variant selection.

**Job 2 — Model Governance:** continuously monitor every model in the
platform (risk, churn, payment propensity) for drift, degradation, and
bias — and trigger retraining when signals cross thresholds. Background
MLOps loop that keeps the platform's intelligence current.

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Variant selection | Two static variants, random confidence scores | Hash-based assignment, statistical significance gate, winner promotion |
| Experiment tracking | None — display only | Versioned experiment store, continuous result accumulation |
| Outcome capture | None | Async outcome API — customer actions feed back into experiment results |
| Drift detection | None | Three-type drift monitoring: feature, prediction, performance |
| Retraining | None | Signal-based triggers — not calendar-based |
| Model versioning | None | Champion/Challenger pattern with 5% challenger traffic |

---

## Job 1 — A/B Experimentation

### Experiment Schema

```python
@dataclass
class Experiment:
    experiment_id    : str       # "exp_payment_message_v3"
    name             : str
    scenario         : str       # "payment_risk_intervention"
    action_type      : str       # "SEND_PUSH_NOTIFICATION"
    status           : str       # RUNNING | CONCLUDED | PAUSED
    variants         : list[Variant]
    traffic_split    : dict      # {"A": 0.50, "B": 0.50}

    # Success metrics
    primary_metric   : str       # "payment_made_7d"
    guardrail_metrics: list[str] # ["opt_out_rate", "complaint_rate"]
                                 # guardrail metric degradation → pause

    # Statistical parameters
    min_sample_size  : int       # minimum per variant before results valid
    confidence_level : float     # 0.95
    mde              : float     # minimum detectable effect (0.05 = 5% lift)

    variant_results  : dict      # updated continuously
    winner           : Optional[str]
    concluded_at     : Optional[datetime]
```

### Variant Assignment — Hash-Based

```python
def select_variant(experiment_id, customer_profile) -> Variant:

    experiment = load_experiment(experiment_id)

    # Experiment concluded → always use winner
    if experiment.winner:
        return experiment.variants[experiment.winner]

    # Running → check if leader is statistically significant
    if experiment.variant_results:
        leader = get_current_leader(experiment)
        if (leader.confidence >= 0.95 and
                leader.sample_count >= experiment.min_sample_size):
            return experiment.variants[leader.variant_id]

    # Default: hash-based assignment
    # Same customer always sees same variant — clean measurement
    bucket = hash(customer_profile.customer_id + experiment_id) % 100
    cumulative = 0
    for variant_id, split_pct in experiment.traffic_split.items():
        cumulative += split_pct * 100
        if bucket < cumulative:
            return experiment.variants[variant_id]

# Why hash and not random:
# Random → same customer sees different variants on repeat contact.
# Cannot attribute their behavior to either variant cleanly.
# Hash → customer_id + experiment_id always produces same bucket.
# Customer A always sees Variant A. Clean measurement. Consistent experience.
```

### Marcus Webb Variant Assignment

```
experiment_id: "exp_payment_message_v3"
customer_id:   "C002"

hash("C002" + "exp_payment_message_v3") % 100 = 34
Traffic split: A=50%, B=50%
Bucket 34 < 50 → Variant A

Current leader: Variant A, confidence 0.9998, n=8,420
Confidence ≥ 0.95 AND n ≥ 5,000 → use leader
→ Variant A confirmed (leader matches hash assignment)

Variant A message: "We noticed your account has some recent activity
  we want to help with. You may qualify for our Hardship Assistance
  Program — which could pause your minimum payment for up to 90 days."
```

### Experiment Conclusion Logic

```
Current results (exp_payment_message_v3):
  Variant A (soft framing):   n=8,420,  payment_7d_rate=0.41
  Variant B (direct framing): n=8,380,  payment_7d_rate=0.34

Lift: (0.41 - 0.34) / 0.34 = 20.6% improvement for Variant A
Z-score: 6.8 (above 1.96 threshold for p < 0.05) ✓
Confidence: 0.9998 ✓
Sample size: 8,420 ≥ 5,000 minimum ✓

Guardrail metrics:
  opt_out_rate:    A=0.8%, B=1.2%  → A better ✓
  complaint_rate:  A=0.1%, B=0.3%  → A better ✓

Conclusion: Variant A wins. Experiment concluded.
All future assignments → Variant A automatically.
ML team notified: consider making Variant A the default KB template.
```

---

## Job 2 — Model Governance and Drift Detection

### Three Types of Drift

```
1. FEATURE DRIFT (input drift)
   Distribution of input features changing.
   Example: checking balance distribution shifts — customers' financial
            profiles different from training data.
   Detection: KS test on feature distributions vs. training baseline.
   Response: alert ML team. Investigate model validity.

2. PREDICTION DRIFT (output drift)
   Distribution of model outputs changing.
   Example: risk_score distribution shifts — more CRITICAL scores
            even with similar input features.
   Detection: control charts on output score distributions.
   Response: compare to feature drift → decide if retraining needed.

3. PERFORMANCE DRIFT (accuracy degradation)
   Model accuracy against labeled ground truth degrading.
   Example: HIGH risk customers paying on time at rates above prediction.
   Detection: compare predictions to actual payment outcomes
              (requires 30-day feedback lag).
   Response: if below threshold → trigger retraining.
```

### The Delayed Label Problem

```
Risk model predicts today: "Marcus Webb has 0.71 risk of missing payment."
You won't know if correct until his payment is due — 30 days from now.

That 30-day lag means:
  Model could be drifting for 30 days before outcome-based detection.
  By the time you detect it, 30 days of decisions on degraded model.

Solutions:

1. Proxy metrics (leading indicators):
   Behavioral signals that correlate with eventual payment behavior
   appear before the payment event.
   App logins, account access, contact response rates shift first.
   Monitor proxies daily as early warning.

2. Population Stability Index (PSI):
   Measures whether customer distribution in each risk bucket is stable.
   PSI < 0.10 : no significant change
   PSI 0.10–0.25: moderate — investigate
   PSI > 0.25 : major shift — likely retraining needed
   PSI computed immediately — no outcome data required.

3. Outcome tracking with lag:
   Nightly batch: for each prediction made 30 days ago,
   compare predicted risk bucket to actual payment outcome.
   Precision and recall tracked in rolling 30-day windows.
   Alert when recall drops below threshold.
```

### Retraining Triggers

```python
RETRAINING_TRIGGERS = {
    "risk_model": {
        "feature_drift_ks_pvalue"  : 0.01,   # KS test p < 0.01 → alert
        "prediction_drift_psi"     : 0.25,   # PSI > 0.25 → investigate
        "recall_30d_threshold"     : 0.75,   # recall < 75% → retrain
        "bias_drift_air_threshold" : 0.80,   # AIR < 0.80 → retrain + compliance
    },
    "churn_model": {
        "recall_30d_threshold"     : 0.72,
        "prediction_drift_psi"     : 0.20,
    },
    "payment_propensity_model": {
        "recall_30d_threshold"     : 0.70,
        "prediction_drift_psi"     : 0.25,
    }
}

# Retraining triggered by signals — not by calendar.
# Calendar-based retraining is dangerous: model might be fine or broken.
# Trigger on measured degradation.
```

### Champion / Challenger Pattern

```
Every new model version deployed as CHALLENGER (5% of traffic).
Current model remains CHAMPION (95% of traffic).
Challenger monitored 7 days vs. same metrics.
  If challenger matches or beats champion → promote to champion.
  If challenger degrades → retire challenger, keep champion.

Model Registry record:
{
  model_id      : "risk_model",
  version       : "risk-v4.2.1",
  champion      : true,
  trained_at    : "2026-04-15T02:00:00Z",
  training_data : "2024-04-01 to 2026-04-14",
  metrics       : { recall: 0.831, precision: 0.794,
                    auc_roc: 0.891, bias_air: 0.92 },
  rollback_to   : "risk-v4.1.8"  ← always pinned, ready in < 30 min
}

Rollback is always < 30 minutes — previous champion is pinned,
not rebuilt from scratch.
```

---

## Full Data Flow — Marcus Webb, Layer 5

```
T+6,382ms   Layer 5 receives: ACT-001 authorized for execution.
T+6,383ms   Experiment lookup: action_type=SEND_PUSH_NOTIFICATION
              active experiment: "exp_payment_message_v3"
T+6,384ms   Hash assignment: hash("C002"+"exp_payment_message_v3")%100 = 34
              Bucket 34 → Variant A
T+6,384ms   Leader check: Variant A, confidence 0.9998, n=8,420
              Both thresholds met → use leader (Variant A confirmed)
T+6,385ms   Final action assembled with Variant A message + metadata
T+6,386ms   A/B audit log written:
              { experiment_id, variant_id: "A",
                assignment_method: "hash+leader",
                customer_id, trace_id }
T+6,387ms   Action passed to Layer 6 (SDK Surface) for execution.

Layer 5 latency  : 5ms   (experiment lookup + hash = trivial)
Cumulative       : 6,387ms
```

---

## Key Design Decisions — Layer 5

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Variant assignment | Hash-based (customer_id + experiment_id) | Consistent per customer per experiment. Clean measurement. Same customer never sees different variants on repeat contact. |
| Experiment conclusion | Statistical significance + minimum sample size | Both required. Prevents early false winners on small samples. |
| Guardrail metrics | Opt-out + complaint tracked alongside primary | An intervention improving payment rate but spiking opt-outs is not a success. Guardrail metrics prevent harmful optimization. |
| Drift detection | Three separate types | Each detects different failure modes. Feature drift ≠ prediction drift ≠ performance drift. All three required for full coverage. |
| Delayed label handling | Proxy metrics + PSI as leading indicators | 30-day outcome lag means ground truth alone is insufficient. Early warning via distribution metrics. |
| Retraining trigger | Signal-based — not calendar | Calendar-based is dangerous. Model might be fine or broken — you don't know until you measure. |
| Champion/Challenger | 5% challenger traffic before promotion | Never deploy untested model to 100% traffic. 7-day challenger period is production validation. |
| Rollback | Previous champion always pinned | < 30 min rollback. Not a rebuild — previous champion stays in registry until challenger is proven. |

---

## Interview Talking Points — Layer 5

- "A/B experimentation and model governance are two separate jobs.
  Experimentation is real-time variant selection at execution time.
  Governance is continuous background monitoring of model health.
  These run on completely different cadences and must not be conflated."

- "Hash-based variant assignment is non-negotiable for clean measurement.
  Random assignment means the same customer sees different messages on
  repeat contacts. You cannot attribute their behavior to either variant.
  Hash is deterministic, consistent, and reproducible."

- "The delayed label problem is the hardest thing in production MLOps for
  banking. You predict risk today but don't know if you were right for
  30 days. Proxy leading indicators and PSI give you early warning.
  Outcome-based recall is your ground truth — but always lagging."

- "Champion/Challenger with 5% challenger traffic is the only safe way
  to deploy a retrained model. Never push to 100% without production
  validation. The challenger period catches issues before full exposure."

---

## Technology Mapping — Layer 5

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Experiment Store | Any document store | DynamoDB |
| Variant Assignment | In-process hash | Same (language-level) |
| Statistical Engine | Any stats library | SageMaker Processing Job |
| Feature Drift Monitor | Any stats compute | SageMaker Model Monitor |
| Model Registry | MLflow / any registry | SageMaker Model Registry |
| Retraining Pipeline | Any ML pipeline | SageMaker Pipelines |
| A/B Audit Log | Append-only store | DynamoDB + S3 |
| Outcome Tracking | Batch job + event store | Glue ETL + S3 + Athena |

---

*Layer 5 completed: May 2026*


---
---

# LAYER 6 — SDK Surface & Product Team Interface

## Problem This Layer Solves

At this point the platform has done everything hard. The output is a fully
authorized, variant-selected action ready to execute. Now a different
problem: **who actually sends the push notification? Who creates the hardship
case? Who routes to a human associate?**

The answer is product teams — mobile app, CRM, associate servicing tool.
These teams did not build the AI platform. They should not need to understand
how it works internally. They should consume its outputs through a clean,
stable interface and plug those outputs into their own systems.

That interface is the **SDK Surface.**

Layer 6 has three responsibilities:

**1. Execution** — actually firing the authorized action (send the push,
create the case, route to associate queue).

**2. SDK abstraction** — giving product teams a clean interface to compose
AI-powered experiences without touching platform internals.

**3. Outcome capture** — recording what happened after the action fired,
so it feeds back into A/B experiments, model governance, and approval queue
feedback loop.

---

## Prototype vs. Production

| Aspect | Prototype | Production |
|--------|-----------|------------|
| Output surface | JSON in UI panel | Typed SDK with versioned API |
| Execution | None — display only | Channel-specific adapters (push, SMS, CRM, associate queue) |
| Product team interface | None — platform is opaque | SDK + Blueprint catalog — integration in 2-3 days |
| Outcome capture | None | Async outcome API — customer actions flow back to A/B and model governance |
| Delivery vs. outcome | Not distinguished | Separate — delivery is synchronous, outcome is async customer-driven |
| SDK versioning | None | Major/minor/patch with 6-month deprecation window |

---

## The Audience for Layer 6

```
Internal platform (Layers 1–5):
  Context Assembly, Vector Search, Orchestration,
  Guardrails, A/B Evaluation — owned by the AI platform team.
  Product teams never touch these layers.

External consumers (Layer 6 surface):
  Mobile App team       → send push notifications, render in-app flows
  CRM team              → create hardship cases, update account flags
  Associate Tooling     → route tasks to human reviewers, surface AI
                          recommendations in the associate UI
  Data / Analytics      → action outcomes for reporting and attribution

Layer 6 must be:
  Stable    — product teams cannot absorb breaking changes
  Simple    — no AI expertise required to use it
  Safe      — guardrails cannot be bypassed through the SDK
  Observable — every execution logged for audit and feedback
```

---

## SDK Surfaces

### Surface 1 — Action Execution API

```python
class ActionClient:

    def execute(
        self,
        trace_id  : str,    # links to full pipeline state
        action_id : str,    # "ACT-001"
        caller_id : str,    # "mobile_app_team" — for audit
    ) -> ExecutionResult:
        """
        Executes an authorized action.
        Action must have passed Guardrails (Layer 4) — enforced internally.
        Product team does not manage guardrails — platform does.
        Returns delivery confirmation + outcome_tracking_id.
        """

    def get_recommendation(
        self,
        trace_id  : str,
    ) -> AIRecommendation:
        """
        Returns AI recommendation for display in a UI.
        Includes: intervention rationale, customer message,
        confidence level, experiment variant metadata.
        Product team renders experience — decisions were made in Layers 3–5.
        """
```

### Surface 2 — Outcome Capture API

```python
    def record_outcome(
        self,
        trace_id     : str,
        action_id    : str,
        outcome_type : str,     # "PUSH_OPENED" | "ENROLLED" | "IGNORED"
                                # | "OPT_OUT" | "COMPLAINT"
        outcome_ts   : datetime,
        metadata     : dict
    ) -> None:
        """
        Records outcome of an executed action.
        Feeds back into A/B experiment tracking (Layer 5).
        Feeds back into model governance outcome store (Layer 5).
        Product team calls this — SDK handles routing internally.
        """
```

### Surface 3 — Blueprint Compositions

```python
# Product team uses a blueprint — not raw API calls
result = ActionBlueprint.PAYMENT_RISK_INTERVENTION.run(
    customer_id = "C002",
    trigger     = "payment_risk_scheduler",
    caller_id   = "payment_risk_team"
)

# Blueprint internally handles all 6 layers:
#   Layer 1: context assembly
#   Layer 2: vector search
#   Layer 3: agent orchestration
#   Layer 4: guardrails
#   Layer 5: A/B variant selection
#   Layer 6: action execution + outcome tracking setup

# Product team result:
#   result.action_executed     → bool
#   result.customer_message    → what the customer will see
#   result.outcome_tracking_id → for recording outcomes later
#   result.pending_actions     → actions in approval queue
```

---

## Blueprint Catalog

```python
class ActionBlueprint(Enum):

    PAYMENT_RISK_INTERVENTION = Blueprint(
        scenario  = "payment_risk_intervention",
        agents    = [RiskScoringAgent, InterventionAgent],
        channels  = [MOBILE_PUSH, SMS, IN_APP_MESSAGE],
        description = "Detect payment risk, intervene with hardship offer"
    )

    BILLING_DISPUTE_RESOLUTION = Blueprint(
        scenario  = "billing_dispute_resolution",
        agents    = [DisputeTriageAgent, ResolutionAgent],
        channels  = [IN_APP_MESSAGE, EMAIL, ASSOCIATE_QUEUE],
        description = "Autonomous dispute triage and resolution"
    )

    CHURN_PREVENTION = Blueprint(
        scenario  = "churn_prevention",
        agents    = [ChurnSignalAgent, RetentionOfferAgent],
        channels  = [MOBILE_PUSH, EMAIL, ASSOCIATE_QUEUE],
        description = "Identify churn signals, generate retention offer"
    )

    FRAUD_ALERT = Blueprint(
        scenario  = "fraud_alert",
        agents    = [FraudDetectionAgent, AlertAgent],
        channels  = [SMS, MOBILE_PUSH, ASSOCIATE_QUEUE],
        description = "Detect anomalous transaction, alert customer"
    )

# New blueprints added by AI platform team as use cases are validated.
# Product teams never build new pipelines.
# Guardrails centrally maintained — inherited automatically.
```

---

## Channel Adapters

```python
CHANNEL_ADAPTERS = {
    "MOBILE_PUSH"    : MobilePushAdapter,      # FCM / APNS
    "SMS"            : SMSAdapter,             # Twilio / internal gateway
    "IN_APP_MESSAGE" : InAppAdapter,           # mobile app messaging API
    "EMAIL"          : EmailAdapter,           # SendGrid / internal SMTP
    "ASSOCIATE_QUEUE": AssociateQueueAdapter,  # internal task routing
    "CRM_CASE"       : CRMAdapter,             # creates case in CRM system
    "ACCOUNT_FLAG"   : AccountSystemAdapter,   # writes flag to account record
}

class ChannelAdapter:
    def send(self, action: AuthorizedAction) -> DeliveryReceipt:
        """
        Executes action on the channel.
        Returns delivery receipt — not confirmation of customer action.
        Push delivered ≠ push opened ≠ customer enrolled.
        """
```

### Delivery vs. Outcome — Critical Distinction

```
Delivery receipt (synchronous — Layer 6 returns this immediately):
  "Push notification delivered to Marcus Webb's device at 10:42:39"
  Confirmable. Logged before returning to caller.

Outcome (asynchronous — captured via Outcome API, later):
  "Marcus Webb opened the push notification at 10:48:12"
  "Marcus Webb completed hardship enrollment at 10:51:07"

These are separate events at separate times.
Outcome flows back through the Outcome API.
Layer 5 A/B and Model Governance consume these outcomes.
Conflating delivery and outcome produces completely wrong metrics.
```

---

## Product Team Integration — Without vs. With SDK

```
Without SDK — Mobile App team building payment risk intervention:
  1. Call Context Assembly service
  2. Trigger agent orchestration
  3. Understand what guardrails apply
  4. Select A/B variant
  5. Integrate push notification delivery
  6. Build outcome tracking back to platform
  7. Handle all failure cases across all layers
  Timeline: 3–4 months. Guardrails reimplemented per team. No consistency.

With SDK:
  from action_sdk import ActionBlueprint, OutcomeType

  result = ActionBlueprint.PAYMENT_RISK_INTERVENTION.run(
      customer_id = customer_id,
      trigger     = "payment_risk_scheduler",
      caller_id   = "mobile_app_team"
  )

  if result.action_executed:
      show_notification(result.customer_message)
      store_locally(result.outcome_tracking_id)

  def on_notification_opened(outcome_tracking_id):
      ActionClient().record_outcome(
          trace_id     = outcome_tracking_id,
          action_id    = result.action_id,
          outcome_type = OutcomeType.PUSH_OPENED,
          outcome_ts   = datetime.now()
      )

  Total: ~50 lines. Timeline: 2–3 days.
  Guardrails: automatically applied — cannot be bypassed.
  A/B: automatically handled — team never touches it.
```

---

## Outcome Feedback Architecture

```
Outcome event (customer tapped push, enrolled, ignored):
        │
        ▼
Outcome API receives event
        │
        ├── → A/B Experiment Store (Layer 5)
        │     Update variant result: Variant A +1 conversion
        │     Recalculate conversion rate and confidence
        │
        ├── → Model Governance Outcome Store (Layer 5)
        │     Record: C002 predicted HIGH risk 2026-05-11
        │     Actual: enrolled in hardship program
        │     Used 30 days later for recall calculation
        │
        ├── → Approval Queue Feedback (Layer 4)
        │     If ACT-002 was approved by reviewer:
        │     Did the approved action lead to predicted result?
        │     Feeds reviewer calibration loop
        │
        └── → Audit Log (DynamoDB)
              Permanent record: what customer did, when,
              linked to original pipeline trace_id
              Full journey reconstructable for regulatory review
```

---

## SDK Versioning — The Stability Guarantee

```
Major version (v1 → v2): breaking changes allowed.
  6-month deprecation notice minimum.
  v1 and v2 supported simultaneously during migration window.

Minor version (v1.2 → v1.3): new features, no breaking changes.
  Additive only. Existing integrations unaffected.

Patch version (v1.2.1 → v1.2.2): bug fixes only.
  No API surface changes.

Version pinning:
  from action_sdk import ActionClient      # always latest
  from action_sdk.v1 import ActionClient  # pinned to v1

Fast-moving teams use latest.
Long release cycle teams pin to major version.
Both supported.
```

---

## Full Data Flow — Marcus Webb, Layer 6

```
T+6,387ms   Layer 6 receives from Layer 5:
              action_type: SEND_PUSH_NOTIFICATION
              message: "[Variant A — soft framing]"
              deep_link: "banking://hardship-enrollment"
              experiment_id: "exp_payment_message_v3", variant_id: "A"
              trace_id: "trace_20260511_104233_C002"

T+6,388ms   Channel resolution:
              SEND_PUSH_NOTIFICATION → MobilePushAdapter
              behavioral.push_ok = true ✓
              behavioral.channel = MOBILE ✓

T+6,390ms   MobilePushAdapter.send():
              Payload:
              { device_token: "[C002 token]",
                title: "A message from your bank",
                body: "We noticed your account has some recent activity
                       we want to help with...",
                deep_link: "banking://hardship-enrollment",
                ttl: 86400 }
              → Sent to FCM / APNS

T+6,441ms   Delivery receipt returned:
              { delivery_id: "del_20260511_104239_C002",
                status: "DELIVERED",
                delivered_at: "2026-05-11T10:42:41.441Z",
                channel: "MOBILE_PUSH" }

T+6,442ms   Execution audit log written:
              { audit_id: "aud_exec_20260511_104239_C002",
                event_type: "ACTION_EXECUTED",
                trace_id: "trace_20260511_104233_C002",
                action_id: "ACT-001",
                channel: "MOBILE_PUSH",
                variant_id: "A",
                experiment_id: "exp_payment_message_v3",
                delivered_at: "2026-05-11T10:42:41.441Z",
                outcome_tracking_id: "otk_C002_20260511_ACT001" }

T+6,443ms   ExecutionResult returned to caller:
              { action_executed: true, action_id: "ACT-001",
                delivery_status: "DELIVERED",
                customer_message: "[Variant A message]",
                outcome_tracking_id: "otk_C002_20260511_ACT001",
                pending_actions: ["ACT-002 in approval queue — 4hr SLA"] }

Layer 6 latency       : 57ms  (push delivery round-trip ~50ms)
Cumulative end-to-end : 6,444ms
```

### End-to-End Timeline Summary — All Layers

```
Layer 1 (Context Assembly)  :   167ms
Layer 2 (Vector Search)     :    55ms
Layer 3 (Orchestration)     : 6,072ms  ← 2 LLM calls dominate
Layer 4 (Guardrails)        :    88ms
Layer 5 (A/B Evaluation)    :     5ms
Layer 6 (SDK + Execution)   :    57ms
─────────────────────────────────────
Total end-to-end            : 6,444ms
```

---

## Outcome Capture — 6–11 Minutes Later

```
T+6min   Customer opens push notification.
         Mobile app fires:
           record_outcome(trace_id, "ACT-001", "PUSH_OPENED", ...)
         → A/B store: Variant A +1 open
         → Audit log: PUSH_OPENED recorded

T+9min   Customer begins hardship enrollment.
         Mobile app fires:
           record_outcome(trace_id, "ACT-001", "ENROLLMENT_STARTED", ...)

T+11min  Customer completes enrollment.
         Mobile app fires:
           record_outcome(trace_id, "ACT-001", "ENROLLED", ...)
         → A/B store: Variant A +1 ENROLLED conversion.
                      Recalculates conversion rate.
         → Model Governance: prediction CRITICAL for C002 2026-05-11.
                             Outcome: ENROLLED.
                             Stored for 30-day recall calculation.
         → Audit log: full journey recorded.

Full audit trail reconstructable from trace_id:
  10:42:33  Context assembled (CRM degraded)
  10:42:33  Policy retrieved (hardship eligibility, intervention playbook)
  10:42:36  Risk assessed: CRITICAL, confidence 0.89
  10:42:39  Intervention proposed: hardship enrollment offer
  10:42:39  Guardrails: push APPROVED, case FLAGGED (pending review)
  10:42:39  A/B: Variant A selected (soft framing)
  10:42:41  Push delivered to mobile device
  10:48:44  Push opened by customer
  10:51:07  Hardship enrollment completed
```

---

## Key Design Decisions — Layer 6

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SDK abstraction | Blueprints + typed API | Product teams compose pre-validated blueprints. Guardrails centrally maintained — not reimplemented per team. |
| Delivery vs. outcome | Separate APIs, separate events | Delivery is synchronous and confirmable. Outcome is async and customer-driven. Conflating produces false metrics. |
| Outcome routing | SDK handles internally | Product team calls record_outcome(). Platform routes to A/B, model governance, approval feedback. Product team owns none of this routing. |
| Channel adapters | One per channel | Channel-specific logic isolated. Adding a new channel adds one adapter — no changes to rest of platform. |
| Blueprint catalog | Platform team owns new blueprints | Product teams cannot build pipelines that bypass guardrails. New use cases go through the platform team — governance applied correctly. |
| SDK versioning | Major/minor/patch, 6-month deprecation window | Product teams build on SDK. Breaking changes without notice break production integrations. |
| trace_id threading | Single ID from Layer 1 through outcome | Full journey reconstructable from one ID. Regulatory replay starts with trace_id and unwinds every step. |

---

## Interview Talking Points — Layer 6

- "Layer 6 is where the platform stops being an internal system and becomes
  a product. The SDK is what makes the platform mandate real — the highest-leverage
  infrastructure that multiplies the output of dozens of product teams.
  Mobile app team integrates in 2–3 days. Without the SDK, they'd need 3–4
  months and would reimplement guardrails incorrectly every time."

- "Delivery and outcome are fundamentally different events. Push notification
  delivered at 10:42 — synchronous, confirmable. Customer enrolled at 10:51
  — asynchronous, customer-driven, the actual signal that feeds A/B experiments
  and model governance. Conflating them produces completely wrong metrics."

- "The blueprint catalog is how you enforce governance at scale. Product teams
  cannot build pipelines that bypass guardrails — they compose pre-validated
  blueprints. When compliance requirements change, you update the blueprint
  once. Every product team inherits the change automatically."

- "The trace_id threads from context assembly through push delivery through
  customer enrollment. One ID reconstructs the complete journey: what data
  the agent had, what policy it applied, what variant was shown, what the
  customer did, and when. That is your regulatory audit trail."

---

## Technology Mapping — Layer 6

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| SDK | Language SDK (Python, Java, JS) | Published to internal package registry |
| Execution Service | Any container runtime | ECS / EKS |
| Mobile Push Adapter | FCM / APNS | AWS SNS (mobile push) |
| SMS Adapter | Twilio / gateway | Amazon SNS or Pinpoint |
| CRM Adapter | REST client | Lambda + internal CRM API |
| Associate Queue Adapter | Any task queue | SQS + internal tooling |
| Outcome Event Bus | Any event streaming | Amazon EventBridge |
| Audit Log | Append-only store | DynamoDB + S3 |

---

*Layer 6 completed: May 2026*

---
---

---

# CROSS-CUTTING — Observability & Audit Trail

## Why Cross-Cutting

Observability is not a layer — it is the infrastructure that runs alongside
every layer simultaneously. Every layer writes to it. Every layer is monitored
by it. It answers three distinct questions for three distinct audiences:

```
Question 1: Is the platform healthy right now?
  Audience: On-call engineers, platform team
  Tooling:  CloudWatch metrics + alarms + dashboards
  Pattern:  SLOs per layer, error budgets, real-time alerts

Question 2: Why did a specific pipeline behave the way it did?
  Audience: Engineers debugging a production issue
  Tooling:  AWS X-Ray (distributed tracing)
  Pattern:  trace_id waterfall, span hierarchy, root-cause analysis

Question 3: What exactly happened during a customer interaction?
  Audience: Compliance officers, legal team, regulators
  Tooling:  DynamoDB (hot) + S3 Object Lock (cold)
  Pattern:  Structured audit records, regulatory replay, 7-year retention

These are three separate systems. Each optimized for its audience.
Conflating them is a common mistake — a logging system designed for
debugging is not an audit trail designed for regulatory replay.
```

---

## 1. Operational Observability — SLOs, Metrics, Alerts

### SLOs Per Layer

```
Layer 1 — Context Assembly
  p99 latency         ≤ 200ms
  availability        ≥ 99.9%
  adapter success     ≥ 95% per adapter
  Alert: p99 > 180ms → warning | p99 > 200ms → page on-call
  Alert: any adapter 0% for 60s → critical

Layer 2 — Vector Search
  p99 latency         ≤ 80ms
  retrieval precision ≥ 85% (weekly labeled test)
  KB freshness        ≤ 48hr staleness
  Alert: p99 > 70ms → warning | p99 > 80ms → page on-call
  Alert: KB version stale > 48hr → critical

Layer 3 — Orchestration
  p99 latency         ≤ 15,000ms (LLM calls dominate — wider budget)
  schema failure rate ≤ 1%
  human review rate   ≤ 5%
  Alert: schema failures > 2% in 10min → warning
  Alert: human review routing > 8% → page on-call

Layer 4 — Guardrails
  p99 latency         ≤ 150ms
  approval SLA breach ≤ 2%
  fairness AIR        monitored continuously (not a perf SLO — compliance metric)
  Alert: p99 > 130ms → warning
  Alert: fairness disparity ratio > 1.15 → alert compliance team
  Alert: approval queue backlog > 50 items → page on-call

Layer 5 — A/B + Model Governance
  variant assignment  ≤ 10ms
  PSI check completion within 1hr of scheduled run
  Alert: any model PSI > 0.20 → alert ML team
  Alert: any model recall 30d < 0.78 → alert ML team

Layer 6 — SDK + Execution
  p99 execution       ≤ 20ms (excluding delivery channel)
  push delivery rate  ≥ 98%
  outcome processing  ≤ 5s lag
  Alert: push delivery < 95% in 5min → warning
  Alert: outcome lag > 30s → warning
```

### SLO Error Budget

```
SLO: 99.9% availability = 43.8 minutes downtime allowed per month

Error budget as a change management tool:

If 30 of 43.8 budget minutes consumed by week 2:
  → Slow down deployments. Protect remaining 13.8 minutes.

If only 2 of 43.8 budget minutes consumed by week 2:
  → Budget intact. Deployments and experiments can proceed.

Error budget makes "how much risk can we take?" a data question,
not an opinion. Platform team and product teams share the same budget.
```

---

## 2. Debugging Observability — Distributed Tracing

### Trace Structure — Marcus Webb

```
trace_id: "trace_20260511_104233_C002"
│
├── SPAN: context_assembly                          [0ms → 167ms]
│     ├── SPAN: card_adapter_fetch                 [0ms → 38ms]    OK
│     ├── SPAN: banking_adapter_fetch              [0ms → 61ms]    OK
│     ├── SPAN: crm_adapter_fetch                  [0ms → 150ms]   TIMEOUT ⚠
│     ├── SPAN: behavioral_adapter_fetch           [0ms → 89ms]    OK
│     ├── SPAN: feature_store_pull                 [155ms → 162ms] OK
│     ├── SPAN: schema_normalization               [151ms → 154ms] OK
│     ├── SPAN: profile_merge                      [163ms → 164ms] OK
│     ├── SPAN: redis_write                        [165ms → 165ms] OK
│     └── SPAN: dynamodb_audit_write               [166ms → 166ms] OK
│
├── SPAN: vector_search                             [167ms → 222ms]
│     ├── SPAN: query_construction                 [167ms → 169ms]
│     ├── SPAN: query_embedding                    [169ms → 187ms]
│     ├── SPAN: metadata_prefilter                 [187ms → 188ms]
│     ├── SPAN: ann_search                         [188ms → 193ms]
│     ├── SPAN: cross_encoder_reranking            [193ms → 221ms]
│     └── SPAN: dynamodb_audit_write               [221ms → 222ms]
│
├── SPAN: orchestration                             [222ms → 6,294ms]
│     ├── SPAN: redis_read_profile                 [222ms → 223ms]
│     ├── SPAN: agent:RiskScoringAgent             [223ms → 2,847ms]
│     │     ├── SPAN: tool:read_customer_profile   [230ms → 235ms]
│     │     ├── SPAN: tool:query_transaction_hist  [240ms → 290ms]
│     │     └── SPAN: llm_call                     [290ms → 2,847ms]
│     ├── SPAN: branch_decision                    [2,847ms → 2,848ms]
│     ├── SPAN: agent:InterventionAgent            [2,848ms → 6,291ms]
│     │     ├── SPAN: tool:read_customer_profile   [2,850ms → 2,855ms]
│     │     ├── SPAN: tool:query_intervention_hist [2,860ms → 2,910ms]
│     │     └── SPAN: llm_call                     [2,910ms → 6,291ms]
│     ├── SPAN: redis_write_pipeline_state         [6,292ms → 6,292ms]
│     └── SPAN: dynamodb_audit_write               [6,293ms → 6,293ms]
│
├── SPAN: guardrails                                [6,294ms → 6,382ms]
│     ├── SPAN: act001_regulatory_checks           [6,294ms → 6,310ms]
│     ├── SPAN: act001_business_policy_checks      [6,310ms → 6,325ms]
│     ├── SPAN: act001_responsible_ai_checks       [6,325ms → 6,340ms]
│     ├── SPAN: act002_regulatory_checks           [6,340ms → 6,355ms]
│     ├── SPAN: act002_business_policy_checks      [6,355ms → 6,368ms]
│     ├── SPAN: act002_responsible_ai_checks       [6,368ms → 6,381ms]
│     └── SPAN: dynamodb_audit_write               [6,381ms → 6,381ms]
│
├── SPAN: ab_evaluation                             [6,382ms → 6,387ms]
│     ├── SPAN: experiment_lookup                  [6,382ms → 6,383ms]
│     ├── SPAN: variant_assignment                 [6,383ms → 6,384ms]
│     └── SPAN: dynamodb_audit_write               [6,386ms → 6,386ms]
│
└── SPAN: sdk_execution                             [6,387ms → 6,444ms]
      ├── SPAN: channel_resolution                 [6,387ms → 6,388ms]
      ├── SPAN: push_delivery:FCM                  [6,390ms → 6,441ms]
      └── SPAN: dynamodb_audit_write               [6,442ms → 6,442ms]

Total: 6,444ms
```

### Span Schema

```python
@dataclass
class Span:
    trace_id      : str     # same across all spans in one pipeline run
    span_id       : str     # unique to this span
    parent_span_id: str     # enables hierarchical reconstruction
    service_name  : str     # "context_assembly" | "vector_search" | ...
    operation     : str     # "crm_adapter_fetch" | "llm_call" | ...
    start_time    : datetime
    end_time      : datetime
    duration_ms   : int
    status        : str     # OK | ERROR | TIMEOUT
    tags          : dict    # structured metadata — customer_id, adapter, etc.
    logs          : list    # events within the span

# Example — crm_adapter_fetch (the timeout span):
Span {
    trace_id      : "trace_20260511_104233_C002",
    span_id       : "span_crm_001",
    parent_span_id: "span_context_assembly",
    operation     : "crm_adapter_fetch",
    duration_ms   : 150,
    status        : "TIMEOUT",
    tags          : { "customer_id": "C002", "timeout_ms": 150 },
    logs          : [{ "ts": "10:42:33.150",
                       "msg": "CRMAdapter exceeded 150ms timeout" }]
}
```

### Root-Cause Analysis in Practice

```
Report: "The hardship offer message looked wrong for C002 on May 11th."

Step 1: Find trace.
  Query X-Ray: customer_id="C002", date="2026-05-11"
  → trace_id: "trace_20260511_104233_C002"

Step 2: Open trace waterfall.
  CRM span immediately visible: 150ms, status=TIMEOUT ⚠

Step 3: Check downstream impact.
  context_assembly span: sources_degraded=["crm"]
  RiskScoringAgent span log: "CRM unavailable. Proceeding without tenure/NPS."
  Agent output: lower_confidence_reason="CRM unavailable"

Step 4: Root cause confirmed.
  CRM timeout → partial profile → agent reasoned without NPS/tenure.
  Not a model problem. A data availability problem.

Without tracing: 15–30 minutes cross-referencing separate log streams.
With tracing:    < 2 minutes — single waterfall view.
```

---

## 3. Regulatory Observability — Unified Audit Trail

### Audit Record — Unified Base Schema

```python
@dataclass
class AuditRecord:
    # Shared linkage fields — every layer uses these
    audit_id     : str      # globally unique
    event_type   : str      # CONTEXT_ASSEMBLY | VECTOR_RETRIEVAL |
                            # ORCHESTRATION_COMPLETE | GUARDRAILS_EVALUATION |
                            # AB_ASSIGNMENT | ACTION_EXECUTED | OUTCOME_CAPTURED
    trace_id     : str      # links all records for one pipeline run
    session_id   : str
    customer_id  : str
    timestamp    : datetime
    layer        : str      # "1" through "6"

    # Layer-specific fields added per event_type
    # Full schemas defined in each layer's section
```

### Complete Audit Trail — Marcus Webb

```
trace_id query → DynamoDB → all records sorted by timestamp:

event_type                  timestamp       key facts
────────────────────────────────────────────────────────────────────────────
CONTEXT_ASSEMBLY            10:42:33.166Z   sources_degraded: [crm]
                                            partial_context: true
                                            model_versions: {risk: v4.2.1}
                                            profile_hash: sha256:8f3a...

VECTOR_RETRIEVAL             10:42:33.220Z   chunks: [KB-HARD-001-v2.3,
                                                      KB-PAY-007-v1.8,
                                                      KB-COMP-003-v3.1]
                                            kb_version: 2026-05-10

ORCHESTRATION_COMPLETE      10:42:39.515Z   agents: [RiskScoringAgent,
                                                     InterventionAgent]
                                            risk_level: CRITICAL
                                            tool_calls: 4
                                            output_hashes: [sha256:3d9f, sha256:7b2e]

GUARDRAILS_EVALUATION       10:42:39.600Z   ACT-001: APPROVED (8/8 checks)
                                            ACT-002: FLAGGED (7/9 checks)
                                            rule_versions: {B-002: 3.1}
                                            queue_id: appr_...ACT002

AB_ASSIGNMENT               10:42:39.608Z   experiment: exp_payment_msg_v3
                                            variant: A
                                            method: hash+leader

ACTION_EXECUTED             10:42:41.442Z   channel: MOBILE_PUSH
                                            status: DELIVERED
                                            outcome_tracking_id: otk_...

OUTCOME_CAPTURED            10:48:44.000Z   outcome: PUSH_OPENED
                                            lag_from_delivery: 363s

OUTCOME_CAPTURED            10:51:33.000Z   outcome: ENROLLED
                                            lag_from_delivery: 532s
```

### Regulatory Replay

```python
def regulatory_replay(customer_id: str, date: str) -> ReplayReport:

    # Query all audit records for this customer on this date
    records = dynamodb.query(
        index     = "customer_id-date-index",
        condition = "customer_id = :cid AND begins_with(timestamp, :date)",
        values    = { ":cid": customer_id, ":date": date }
    )

    records.sort(key=lambda r: r.timestamp)

    # Reconstruct state from each record
    for record in records:
        if record.event_type == "CONTEXT_ASSEMBLY":
            # What data did the agent have?
            # What was missing and why?
            # Which model versions scored this customer?

        elif record.event_type == "VECTOR_RETRIEVAL":
            # What policy was the agent following?
            # Which KB version was active?

        elif record.event_type == "GUARDRAILS_EVALUATION":
            # What compliance checks ran?
            # What were the outcomes?
            # Which rule versions were active?
            # Retrieve exact rule text from Rule Store:
            #   rule_id + version → exact rule that ran

    # Answers any regulatory question:
    # Q: What data did the agent have?   A: card+banking+behavioral. CRM unavailable.
    # Q: What policy was it following?   A: KB-HARD-001 v2.3 (2026-05-10 snapshot)
    # Q: What compliance checks ran?     A: 9 checks. Rule B-002 v3.1 active.
    # Q: What did the customer do?       A: Opened push 6min later. Enrolled 11min later.
```

---

## 4. Audit Trail Storage Architecture

### Two-Tier Storage

```
HOT STORAGE (DynamoDB):
  Recent 90 days. Millisecond query.
  Indexed by: customer_id, trace_id, date, event_type.
  Used for: active investigations, real-time compliance checks.
  Auto-archived to S3 after 90 days.

COLD STORAGE (S3 + Athena):
  All records beyond 90 days. Parquet format.
  Partitioned by: date + customer_id_prefix.
  Queried via Athena for ad-hoc analysis.
  Retention: 7 years minimum (banking regulatory requirement).
  Used for: regulatory reviews, historical analysis.

Query pattern:
  Active investigation     → DynamoDB (milliseconds)
  Regulatory review        → Athena on S3 (seconds to minutes)
  Acceptable: regulatory reviews are never real-time operations.
```

### Immutability Enforcement

```
DynamoDB:
  Written with condition: attribute_not_exists(audit_id)
  Write fails if audit_id already exists → no overwrites.
  Deletion requires IAM privilege no application service has.

S3 Object Lock (COMPLIANCE mode):
  Records cannot be deleted or overwritten by anyone —
  including account root user — for the retention period.
  Strongest immutability guarantee S3 provides.
  Meets SEC Rule 17a-4 requirements for electronic records.

Why both:
  DynamoDB condition = defense against accidental overwrite in hot storage.
  S3 Object Lock = regulatory-grade immutability in cold storage.
  Defense in depth for the most sensitive data in the platform.
```

---

## 5. The trace_id — Single Thread Through Everything

```
Generated: Layer 1, pipeline entry point.
Format:    "trace_{customer_id}_{timestamp}_{random_6}"

Where it appears:
  Redis session key value        (context store)
  Every X-Ray span               (debugging)
  Every DynamoDB audit record    (compliance)
  Every CloudWatch log line      (operational)
  Every SQS message              (approval queue)
  Every outcome event            (mobile app → outcome API)
  ExecutionResult returned       (to product team)
  Push notification deep link    (to customer's device)

What it enables:
  Search any log system by trace_id → everything for that pipeline run
  Query DynamoDB by trace_id → full audit trail
  Open X-Ray by trace_id → full trace waterfall
  Find SQS approval queue item by trace_id
  When customer opens push and enrolls → outcome event carries
  original trace_id → outcome linked back to originating pipeline

Without threading discipline:
  Six disconnected log streams. Manual correlation by timestamp.
  Root-cause analysis: 30 minutes.
  Regulatory replay: incomplete.

With threading:
  One trace_id reconstructs the complete customer journey.
  Root-cause analysis: 2 minutes.
  Regulatory replay: fully automated.
```

---

## 6. Observability Tooling Stack

```
METRICS    → CloudWatch
  Per-layer SLO metrics (latency, error rate, success rate)
  Published every 60 seconds
  Alarms → PagerDuty → on-call engineer
  Dashboards: one per layer + unified platform dashboard

TRACES     → AWS X-Ray (or Jaeger if cloud-agnostic)
  Every span published
  Trace waterfall view
  Service dependency map
  Audience: engineers

APP LOGS   → CloudWatch Logs + OpenSearch
  Verbose operational logs (INFO, WARN, ERROR)
  Searchable by trace_id, customer_id, error type
  Retention: 30 days
  Audience: engineers

AUDIT TRAIL → DynamoDB (hot) + S3 Object Lock (cold)
  Structured compliance records
  Schema-validated at write time
  Immutable, 7-year retention
  Audience: compliance, legal, regulators — NOT engineers

The separation is deliberate.
Each system optimized for its audience and retention requirement.
Engineers never query the audit trail for debugging.
Compliance never reads application logs for regulatory review.
```

---

## Key Design Decisions — Observability

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Three separate systems | Metrics + Traces + Audit Trail | Each optimized for its audience. Conflating them produces systems that serve none well. |
| SLO error budgets | Shared budget drives deployment decisions | Makes "how much risk?" a data question. Not opinion. Platform and product teams share accountability. |
| trace_id threading | Single ID from L1 through outcome | Full journey reconstructable from one ID. Regulatory replay, debugging, and audit all start here. |
| Audit trail immutability | DynamoDB condition + S3 Object Lock COMPLIANCE | Defense in depth. Application cannot overwrite. Even root user cannot delete during retention period. |
| Two-tier storage | DynamoDB (90d hot) + S3 (7yr cold) | Recent investigations need millisecond queries. Regulatory reviews need bulk storage and Athena queries — not real-time. |
| Audit trail schema | Unified base + layer-specific extension | Consistent linkage fields across all layers. trace_id, customer_id, timestamp always present — queryable across all event types. |
| Audience separation | Engineers → X-Ray + CloudWatch. Compliance → DynamoDB + Athena | Different retention, different access controls, different query patterns. One system cannot serve both. |

---

## Interview Talking Points — Observability

- "Observability has three audiences and requires three systems. Engineers
  use distributed tracing and metrics dashboards. Compliance uses the
  structured audit trail. Regulators use the seven-year immutable record
  in S3. These are not the same system — each is optimized for its
  audience, retention requirement, and query pattern."

- "The trace_id is the single instrument that connects everything —
  from context assembly at 10:42 through push delivery to customer
  enrollment at 10:51. One ID reconstructs the complete journey across
  every layer, every tool call, every compliance check. That is your
  regulatory audit trail and your debugging tool simultaneously."

- "SLO error budgets turn 'should we deploy?' from an opinion into a
  data question. If you've consumed 30 of your 43.8 monthly budget minutes
  by week two, you slow down. If you've consumed 2, you move fast. The
  budget is shared between the platform team and the product teams — which
  means everyone has skin in the reliability game."

- "Audit trail immutability is not just a design preference in banking —
  it is a regulatory requirement. S3 Object Lock in compliance mode means
  no one — not the application, not the DBA, not the account root user —
  can delete or overwrite a record during the retention period. SEC Rule
  17a-4 compliance is built into the storage choice."

---

## Technology Mapping — Observability

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Metrics | Prometheus + Grafana | CloudWatch Metrics + Dashboards |
| Alerting | PagerDuty / Opsgenie | CloudWatch Alarms + SNS + PagerDuty |
| Distributed Tracing | Jaeger / Zipkin | AWS X-Ray |
| Application Logs | ELK Stack | CloudWatch Logs + OpenSearch |
| Audit Trail (hot) | Any document store | DynamoDB (condition writes) |
| Audit Trail (cold) | Any object store | S3 + Object Lock COMPLIANCE mode |
| Historical Queries | Any SQL engine | Athena on S3 Parquet |
| Structured Logging | Any JSON logger | AWS Lambda Powertools / structlog |

---

*Observability & Audit Trail completed: May 2026*

*Then: Full Platform Architecture Diagram*

---
---

---

# CROSS-CUTTING — MLOps & Drift Detection

## Why Cross-Cutting — Not Just Layer 5

Layer 5 asked: *is this model's output trustworthy enough to act on right now?*
This section asks: *how do we ensure every model in the platform is built,
deployed, monitored, retrained, and retired in a way that maintains accuracy,
fairness, and regulatory defensibility over its entire lifetime?*

These are different questions. Layer 5 is runtime signal. MLOps is lifecycle governance.

---

## Models in Active Production

```
Model                     Served by      Update cadence  Used in
──────────────────────────────────────────────────────────────────────
risk_model                Feature Store  Hourly batch    Layer 1 signals
churn_model               Feature Store  Nightly batch   Layer 1 signals
clv_model                 Feature Store  Nightly batch   Layer 1 signals
payment_propensity_model  Feature Store  Hourly batch    Layer 1 signals
embedding_model           Vector Search  On KB update    Layer 2
cross_encoder_model       Vector Search  On KB update    Layer 2
```

---

## Full MLOps Lifecycle

```
STAGE 1: Data Management       Training data governance, feature versioning
STAGE 2: Training              Pipeline execution, hyperparameter tuning
STAGE 3: Evaluation Gate       All 4 gates must pass before deployment
STAGE 4: Champion/Challenger   5% challenger, 7-day window, promote or retire
STAGE 5: Production Monitoring Three-type drift detection, fairness monitoring
STAGE 6: Retraining Triggers   Signal-based + scheduled baseline
STAGE 7: Retirement            Archive artifacts, update model card, preserve audit
```

---

## Stage 1 — Data Management

### Training-Serving Skew — The Most Common MLOps Failure

```
Example of skew:
  Training: utilization = balance/limit from end-of-day batch warehouse.
  Serving:  utilization = balance/limit from real-time CardSystem API.

  Customer pays $500 at 11:59pm.
  Batch captured pre-payment balance. Live API returns post-payment.
  Utilization differs. Scores drift for no model reason.

Prevention:
  Feature store is single source of truth for ALL features.
  Training pipeline reads from feature store.
  Serving pipeline reads from feature store.
  Feature computation logic lives once — not duplicated.

Feature versioning:
  "card_utilization_v1" = end-of-day balance / limit
  "card_utilization_v2" = real-time balance / limit

  Model trained on v1 must serve on v1.
  Transition to v2 managed through Champion/Challenger.
  Training dataset records which feature version was used.
```

### Training Data Window

```
Too short (< 6 months):
  Model hasn't seen seasonal patterns.
  Holiday spending, tax refunds, summer travel affect payment behavior.
  3-month window misses all of them.

Too long (> 36 months):
  COVID-era payment behavior ≠ 2026 behavior.
  Structurally different economic periods contaminate training.

Sweet spot for payment risk: 12–24 months rolling window.
  Captures seasonal patterns. Excludes non-representative history.
  Window slides forward on each retrain.

Label engineering:
  Label: binary, 1 = missed next scheduled payment
  Horizon: 30 days (intervention timing — not 90 days too late)
  Label lag: 30 days from prediction to label availability.
```

---

## Stage 3 — Evaluation Gate (All 4 Must Pass)

```
Gate 1 — Accuracy Metrics (risk_model thresholds):
  Recall    ≥ 0.80   (catch ≥ 80% of customers who will miss payment)
  Precision ≥ 0.75
  AUC-ROC   ≥ 0.88

  Why recall > precision threshold:
    False negative (missed at-risk) = no intervention = missed payment.
    False positive (flagged non-at-risk) = unnecessary intervention.
    Cost of false negative > false positive in credit risk.
    Recall threshold set higher than precision threshold.

Gate 2 — Fairness (hard gate — no exceptions):
  AIR ≥ 0.80 across all protected cohorts for all risk buckets.
  Any cohort below 0.80 → model does NOT deploy.
  No business case overrides a fairness gate failure.
  If model cannot be made fair → investigate training data bias.

Gate 3 — Inference Performance:
  p99 latency     ≤ 5ms (feature store lookup)
  Batch throughput ≥ 500,000 customers/hour
  Model file size within deployment budget

Gate 4 — Segment Regression Test:
  Run candidate against 90-day holdout set.
  Compare per-segment vs. current champion.
  Candidate must NOT degrade any segment vs. champion — even if
  overall metrics improve.

  Why this matters:
    Model improving average recall 0.80 → 0.83 while degrading
    low-income segment recall 0.82 → 0.71 passes aggregate metrics.
    Segment regression test catches what averages hide.
    Hidden bias surfaces here before it reaches production.
```

---

## Stage 5 — Production Drift Monitoring

### Three Drift Types (from Layer 5 — applied systematically)

```
FEATURE DRIFT (input shift):
  For each feature in each model:
    Daily: compute mean, std, p25, p75, p95 vs training baseline
    KS test: p < 0.01 → statistically significant drift
    PSI: > 0.20 → major shift → investigate
  Implementation: SageMaker Model Monitor nightly on feature store.

PREDICTION DRIFT (output shift):
  For each model's score distribution:
    Daily: histogram of output score buckets vs rolling 30-day baseline
    Control chart: 3-sigma breach → alert
  Catches: sudden feature bugs (same day), gradual concept drift (weeks).

PERFORMANCE DRIFT (accuracy degradation — 30-day lag):
  Nightly batch: match predictions from 30 days ago to actual outcomes
  Rolling 30-day: recall, precision, AUC-ROC vs champion evaluation metrics
  If recall drops 5+ ppts → investigate and possibly retrain
  If AIR drops below 0.82 → alert compliance + ML team simultaneously
```

---

## Stage 6 — Retraining Triggers

```python
RETRAINING_TRIGGERS = {
    "risk_model": {
        "feature_drift_ks_pvalue"  : 0.01,
        "prediction_drift_psi"     : 0.25,
        "recall_30d_threshold"     : 0.75,
        "bias_drift_air_threshold" : 0.80,
        "scheduled_cadence_days"   : 60
    },
    "churn_model": {
        "recall_30d_threshold"     : 0.72,
        "prediction_drift_psi"     : 0.20,
        "scheduled_cadence_days"   : 90
    },
    "payment_propensity_model": {
        "recall_30d_threshold"     : 0.70,
        "prediction_drift_psi"     : 0.25,
        "scheduled_cadence_days"   : 60
    }
}

# TRIGGER TYPES:
# 1. Signal-triggered: PSI breach → within 48hr
#                      Recall drops → within 24hr
#                      AIR drops → immediately + compliance review
# 2. Scheduled baseline: every N days regardless of signals
#    Catches slow drift that signals don't detect
# 3. Manual: major economic event, known data quality incident

# RETRAIN PIPELINE:
# Step 1: Pull training data (versioned feature store snapshot)
# Step 2: Same preprocessing as prior run
# Step 3: Train + hyperparameter tuning
# Step 4: Run all 4 evaluation gates
# Step 5: If passes → register as challenger in Model Registry
# Step 6: Deploy challenger at 5% traffic
# Step 7: Monitor 7 days
# Step 8: Promote or retire

# RETRAIN AUDIT RECORD (permanent):
{
  "retrain_id"        : "rt_risk_20260511",
  "model_id"          : "risk_model",
  "trigger_type"      : "SIGNAL",
  "trigger_reason"    : "PSI=0.27 on card_utilization feature",
  "training_data"     : { "start": "2024-05-01", "end": "2026-05-01",
                          "version": "feat_snapshot_20260511" },
  "gate_results"      : { "recall": 0.834, "precision": 0.801,
                          "auc": 0.892, "air": 0.91 },
  "challenger_version": "risk-v4.3.0",
  "deployed_at"       : "2026-05-12T06:00:00Z",
  "outcome"           : "PROMOTED"
}
```

---

## Model Card — Governance Artifact

```
MODEL CARD: risk_model v4.2.1

Intended use:
  Score payment risk for credit card customers of a banking platform.
  Output: risk_score (0.0–1.0) used in payment_risk_intervention pipeline.
  NOT for: credit origination, limit change decisions.

Training data:
  Window: 2024-04-01 to 2026-04-14 (24 months)
  Label: missed next scheduled payment (binary, 30-day horizon)
  Sample: 4,200,000 customer-months

Performance:
  Recall: 0.831 | Precision: 0.794 | AUC-ROC: 0.891

Fairness:
  AIR Group A: 0.92 | AIR Group B: 0.89 | AIR Group C: 0.91
  All cohorts ≥ 0.80 ✓

Known limitations:
  CRM unavailability degrades score quality (NPS/tenure absent).
  Customers < 6 months history have wider confidence intervals.
  No behavioral signal for customers not using mobile app.

Deployment: 2026-04-16 (promoted from challenger after 7 days)
Rollback target: risk-v4.1.8

Compliance approved by: [name], 2026-04-16

The model card is what compliance officers and regulators review.
Not the code. Not the weights. The model card.
```

---

## Connecting MLOps to All Layers

```
Layer 1 (Context Assembly):
  Feature store outputs are model signals in the unified profile.
  Model versions in the profile = audit lineage for regulatory replay.
  MLOps keeps those signals from validated, current models.

Layer 3 (Orchestration):
  Agents use feature store signals in context.
  Drifted risk model → agents reason on stale risk scores → wrong recommendations.
  MLOps retraining keeps agent inputs current.

Layer 4 (Guardrails):
  Confidence thresholds assume model confidence is calibrated.
  Model overconfidence detected → ML team adjusts thresholds.
  AIR drift detected in guardrails → triggers MLOps retraining.

Layer 5 (A/B + Model Governance):
  A/B outcome data (enrolled, ignored, opted out) is training signal.
  What interventions worked → what features predicted success.
  Closes the loop: intervention outcomes improve prediction models.

Layer 6 (SDK + Execution):
  Outcome events flow to outcome store.
  30 days later → labeled training examples for next retrain.
  Platform generates its own training data through production use.
  Models improve with every intervention cycle.
```

---

## Key Design Decisions — MLOps

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Feature store as single source | Training and serving read from same store | Eliminates training-serving skew. Logic lives once. |
| Feature versioning | New version on computation change | Model trained on v1 serves on v1. Transition via Champion/Challenger. |
| Training window | 12–24 months rolling | Seasonal coverage without non-representative history contamination. |
| Label horizon | 30-day binary | Matches intervention timing. Clean. Actionable. |
| Evaluation gate | All 4 must pass | No exceptions for fairness gate. Segment regression test prevents hidden degradation. |
| Recall > Precision weighting | Higher recall threshold | Asymmetric cost: false negative > false positive in credit risk. |
| Retrain trigger | Signal-based + scheduled baseline | Signal catches drift fast. Scheduled catches slow drift signals miss. |
| Champion/Challenger | 5% challenger, 7-day window | Production validation required regardless of offline results. |
| Model Card | Required per version | Compliance artifact. Regulators review the card — not the code. |
| Outcome loop | Production outcomes → training data | Platform generates its own labeled data. Compounding improvement over time. |

---

## Interview Talking Points — MLOps

- "The most common MLOps failure is training-serving skew. The feature store
  prevents it by being the single source of truth for all feature computation.
  Training reads from it. Serving reads from it. The logic lives once."

- "Fairness is a hard gate — not a recommendation. AIR below 0.80 for any
  cohort and the model does not deploy. No business case overrides it."

- "Segment-level regression testing is what prevents aggregate metrics from
  hiding population-level degradation. A model can improve average recall
  while degrading recall for low-income segments. Gate 4 catches this
  before it reaches production."

- "The platform generates its own training data through production use.
  Every outcome — enrolled, ignored, opted out — becomes a labeled example
  30 days later. The models improve with every intervention cycle."

---

## Technology Mapping — MLOps

| Component | Cloud Agnostic | AWS Native |
|-----------|---------------|------------|
| Feature Store | Feast / Tecton / custom | SageMaker Feature Store |
| Training Pipeline | Kubeflow / MLflow | SageMaker Pipelines |
| Model Registry | MLflow Model Registry | SageMaker Model Registry |
| Drift Monitoring | Evidently AI / custom | SageMaker Model Monitor |
| Experiment Tracking | MLflow / W&B | SageMaker Experiments |
| Batch Scoring | Spark / Ray | SageMaker Batch Transform |
| Outcome Store | Event store + batch ETL | EventBridge + S3 + Glue + Athena |
| Model Card Store | Any document store | S3 + DynamoDB |

---

*MLOps & Drift Detection completed: May 2026*
*All sections complete. Next: Full Platform Architecture Diagram.*

---
---

---

# FULL PLATFORM ARCHITECTURE DIAGRAM

## ASCII Diagram — Complete Platform

```
INBOUND TRIGGER
  payment_risk_scheduler · customer_event · API call
  { customer_id, session_id, scenario }
        │
        ▼
═══════════════════════════════════════════════════════════════════════════
  LAYER 1 — CONTEXT ASSEMBLY                                    [167ms]
───────────────────────────────────────────────────────────────────────────
  Parallel Source Fetch (timeout: 150ms each)
  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────┐
  │ CardSystem      │ │ CoreBanking     │ │ CRM Adapter     │ │ Behavioral       │
  │ Adapter         │ │ Adapter         │ │ (DEGRADED ⚠)    │ │ Adapter          │
  │ T+38ms ✓        │ │ T+61ms ✓        │ │ T+150ms TIMEOUT │ │ T+89ms ✓         │
  └─────────────────┘ └─────────────────┘ └─────────────────┘ └──────────────────┘
        │                   │                    │ (null)              │
        └───────────────────┴────────────────────┴─────────────────────┘
                                     │
                             Schema Normalization
                             (canonical CustomerProfile)
                                     │
                             Feature Store Pull ←── SageMaker Feature Store
                             risk_score · churn_prob · CLV · payment_propensity
                             + model_versions (audit lineage)
                                     │
                             Profile Merge
                             UnifiedCustomerProfile { partial_context: true }
                                     │
                    ┌────────────────┴─────────────────┐
                    │                                  │
              Redis TTL Write                   DynamoDB Audit
              session:{id}:profile              CONTEXT_ASSEMBLY record
              EX=300, NX=true                  sources_degraded, profile_hash
              (immutable after write)           model_versions_used
                    │
                    ▼
          AssemblyResult { session_id, partial_context: true }
═══════════════════════════════════════════════════════════════════════════
  LAYER 2 — VECTOR SEARCH                                        [55ms]
───────────────────────────────────────────────────────────────────────────
  Read CustomerProfile from Redis (consumer — never writes)
        │
  Dynamic Query Construction (from profile signals)
  "Customer with critical payment risk. 2 missed payments,
   checking $312.40, no direct deposit. Utilization 76%..."
        │
  Query Embedding (text-embedding-3-small-v2)
  Dense vector (1536-dim) + Sparse vector (BM25)
        │
  Metadata Pre-filter: product_line=credit_card, jurisdiction=US
  4,200 chunks → 847 chunks in search space
        │
  Hybrid ANN + BM25 Search (HNSW index) → RRF merge → top 20
        │
  Cross-Encoder Re-ranking (28ms for 20 candidates)
        │
  Top 3 chunks:
  KB-HARD-001-v2.3 (0.961) · KB-PAY-007-v1.8 (0.934) · KB-COMP-003-v3.1 (0.918)
        │
  DynamoDB Audit: VECTOR_RETRIEVAL (chunks, kb_version, model versions)
═══════════════════════════════════════════════════════════════════════════
  LAYER 3 — MULTI-AGENT ORCHESTRATION                         [6,072ms]
───────────────────────────────────────────────────────────────────────────
  HUB-AND-SPOKE PATTERN — agents never call each other directly

  Orchestrator reads profile from Redis + receives policy chunks from L2
        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  STEP 1: RiskScoringAgent                            [2,624ms]  │
  │  authorized_tools: [read_customer_profile,                      │
  │                     query_transaction_history,                  │
  │                     compute_risk_signals]                       │
  │  Tool calls: read_profile ✓, query_transactions ✓              │
  │  Output: risk_level=CRITICAL, confidence=0.89                  │
  │  Schema validated ✓                                             │
  └─────────────────────────────────────────────────────────────────┘
        │
  BRANCH: risk_level=CRITICAL → InterventionAgent
  (Orchestrator deterministic rule — not agent decision)
        │
  ┌─────────────────────────────────────────────────────────────────┐
  │  STEP 3: InterventionAgent                           [3,443ms]  │
  │  authorized_tools: [read_customer_profile,                      │
  │                     query_intervention_history,                 │
  │                     propose_intervention]                       │
  │  Tool calls: read_profile ✓, query_interventions ✓             │
  │  Prior SMS (2026-04-28) no response → escalate                 │
  │  Output: HARDSHIP_PROGRAM_ENROLLMENT_OFFER                     │
  │    ACT-001: SEND_PUSH_NOTIFICATION (no approval needed)        │
  │    ACT-002: CREATE_HARDSHIP_CASE (approval required, $420)     │
  │  Schema validated ✓                                             │
  └─────────────────────────────────────────────────────────────────┘
        │
  Pipeline state checkpoint → Redis (recovery point)
  DynamoDB Audit: ORCHESTRATION_COMPLETE (agents, tool_calls, hashes)
        │
  Failure handling:
    TIMEOUT → HumanReviewQueue
    SCHEMA_FAIL → reject + alert, HumanReviewQueue
    TOOL_AUTH_VIOLATION → block + security alert
═══════════════════════════════════════════════════════════════════════════
  LAYER 4 — GUARDRAILS & POLICY ENFORCEMENT                      [88ms]
───────────────────────────────────────────────────────────────────────────
  Configurable Rule Engine (YAML + mtime polling locally; DynamoDB target)
  Three check categories in sequence:

  ┌────────────────────────────────────────────────────────────────┐
  │  ACT-001: SEND_PUSH_NOTIFICATION                               │
  │  REGULATORY:     R-001 UDAAP ✓  R-002 TCPA ✓  R-003 Fair ✓  │
  │  BUSINESS:       B-001 Contact ✓  B-002 Dup ✓  B-003 Auth ✓ │
  │  RESPONSIBLE AI: AI-001 Conf ✓  AI-002 Partial ✓  AI-003 ✓  │
  │  DISPOSITION: APPROVED (8/8) → executes immediately           │
  └────────────────────────────────────────────────────────────────┘

  ┌────────────────────────────────────────────────────────────────┐
  │  ACT-002: CREATE_HARDSHIP_ENROLLMENT_CASE ($420)               │
  │  REGULATORY:     R-001 ✓  R-002 BISG fair ✓  R-003 ✓         │
  │  BUSINESS:       B-001 ✓  B-002 ⚠ FLAGGED (std approval)    │
  │                  B-003 ✓                                       │
  │  RESPONSIBLE AI: AI-001 ✓  AI-002 ⚠ FLAGGED (CRM absent)    │
  │                  AI-003 ✓                                       │
  │  DISPOSITION: FLAGGED (7/9) → approval queue, 4hr SLA         │
  └────────────────────────────────────────────────────────────────┘

  DynamoDB Audit: GUARDRAILS_EVALUATION (rule_versions_used)
  SQS Approval Queue: appr_20260511_104239_ACT002
═══════════════════════════════════════════════════════════════════════════
  LAYER 5 — A/B EVALUATION & MODEL GOVERNANCE                     [5ms]
───────────────────────────────────────────────────────────────────────────
  Job 1: Variant Selection (real-time)
  experiment: exp_payment_message_v3
  hash("C002" + experiment_id) % 100 = 34 → Variant A (50% split)
  Leader check: Variant A, confidence 0.9998, n=8,420 → use leader
  Result: Variant A (soft framing) selected

  Job 2: Model Governance (background, continuous)
  ┌──────────────────────────────────────────────────────────────┐
  │  Three-type drift monitoring (all models):                   │
  │  Feature drift   → KS test vs training baseline             │
  │  Prediction drift → Control charts on output distribution   │
  │  Performance drift → Rolling 30d recall vs champion metrics  │
  │                                                              │
  │  Retraining: signal-based + scheduled baseline              │
  │  Champion/Challenger: 5% challenger, 7-day window           │
  │  Evaluation gate: recall + precision + fairness (AIR≥0.80)  │
  │                 + segment regression (no segment degrades)   │
  └──────────────────────────────────────────────────────────────┘

  DynamoDB Audit: AB_ASSIGNMENT (experiment_id, variant, method)
═══════════════════════════════════════════════════════════════════════════
  LAYER 6 — SDK SURFACE & EXECUTION                              [57ms]
───────────────────────────────────────────────────────────────────────────
  Blueprint: ActionBlueprint.PAYMENT_RISK_INTERVENTION
  Product team sees: 50 lines. Platform handles all 6 layers.

  ACT-001: MobilePushAdapter.send()
  Payload: { body: "[Variant A message]",
             deep_link: "banking://hardship-enrollment", ttl: 86400 }
  → FCM / APNS → DELIVERED at T+6,441ms

  ExecutionResult returned to caller:
    action_executed: true
    outcome_tracking_id: "otk_C002_20260511_ACT001"
    pending_actions: ["ACT-002 in approval queue — 4hr SLA"]

  DynamoDB Audit: ACTION_EXECUTED (channel, variant, tracking_id)
═══════════════════════════════════════════════════════════════════════════

              TOTAL END-TO-END: 6,444ms
  ┌──────────────────────────────────────────────────────────────┐
  │  L1  167ms  ████                                             │
  │  L2   55ms  █                                                │
  │  L3 6072ms  ████████████████████████████████████████ (94%)  │
  │  L4   88ms  ██                                               │
  │  L5    5ms  ▌                                                │
  │  L6   57ms  █                                                │
  └──────────────────────────────────────────────────────────────┘
  Note: L3 dominates — 2 LLM calls at ~3s each.
  L1+L2+L4+L5+L6 combined = 372ms (6% of total).

═══════════════════════════════════════════════════════════════════════════
  CROSS-CUTTING — OBSERVABILITY & AUDIT TRAIL (all layers)
───────────────────────────────────────────────────────────────────────────
  trace_id: "trace_20260511_104233_C002"
  Threads through: every Redis key, every X-Ray span, every audit record,
                   every SQS message, every outcome event

  THREE SYSTEMS FOR THREE AUDIENCES:

  Engineers  → CloudWatch (SLOs, alerts) + AWS X-Ray (trace waterfall)
               Per-layer SLOs: L1≤200ms L2≤80ms L3≤15s L4≤150ms L5≤10ms L6≤20ms

  Compliance → DynamoDB (hot, 90 days, condition writes)
  & Legal      8 audit record types: CONTEXT_ASSEMBLY · VECTOR_RETRIEVAL ·
               ORCHESTRATION_COMPLETE · GUARDRAILS_EVALUATION · AB_ASSIGNMENT ·
               ACTION_EXECUTED · OUTCOME_CAPTURED · APPROVAL_DECISION

  Regulators → S3 + Object Lock COMPLIANCE mode (7 years, immutable)
               Athena for ad-hoc replay queries
               Answers: what data → what policy → what compliance checks →
                        what rule versions → what action → what outcome

═══════════════════════════════════════════════════════════════════════════
  CROSS-CUTTING — MLOPS & DRIFT DETECTION (all models)
───────────────────────────────────────────────────────────────────────────
  6 models in production: risk · churn · clv · payment_propensity ·
                          embedding · cross_encoder

  Feature Store (single source of truth — eliminates training-serving skew)
        │
  Training Pipeline → 4-gate evaluation gate
  (accuracy + fairness AIR≥0.80 + perf + segment regression)
        │
  Champion/Challenger deployment (5% traffic, 7-day window)
        │
  Production monitoring:
    Feature drift   (KS test, daily)
    Prediction drift (control charts, daily)
    Performance drift (recall, 30-day lag, nightly batch)
    Fairness drift   (AIR monitoring, daily)
        │
  Signal-based retraining + scheduled baseline
        │
  Outcome loop: L6 outcomes → labeled training data → next retrain
  Platform generates its own training data through production use.

═══════════════════════════════════════════════════════════════════════════

OUTCOME — 11 MINUTES AFTER TRIGGER:
  Marcus Webb opened push at T+6min → enrolled in hardship program at T+11min
  Outcome feeds: A/B experiment (Variant A +1 conversion)
               + Model governance (prediction validated, 30-day label)
               + Approval queue (reviewer feedback signal)
               + Audit trail (complete journey, trace_id linkage)

FULL REGULATORY AUDIT TRAIL:
  10:42:33  Context assembled (CRM degraded, partial_context=true)
  10:42:33  Policy retrieved (KB-HARD-001 v2.3, kb_version: 2026-05-10)
  10:42:36  Risk: CRITICAL, confidence 0.89 (risk-v4.2.1)
  10:42:39  Proposed: HARDSHIP_PROGRAM_ENROLLMENT_OFFER
  10:42:39  Guardrails: ACT-001 APPROVED, ACT-002 FLAGGED (rule B-002 v3.1)
  10:42:39  A/B: Variant A (exp_payment_message_v3)
  10:42:41  Push DELIVERED
  10:48:44  PUSH_OPENED
  10:51:33  ENROLLED
```

---

## Interactive Diagram

See the architecture diagram React component with three views:
- **Architecture**: all layers expandable with Marcus Webb examples and tech stack
- **Data Flow**: full timeline from T+0ms through enrollment
- **Tech Stack**: cloud-agnostic vs AWS-native mapping per layer

---

## Design Principles Summary

```
1. Live context over cached snapshots      → Layer 1: parallel fetch, TTL store
2. Governance as runtime capability        → Layer 4: guardrails before execution
3. Hub-and-spoke orchestration             → Layer 3: all routing through orchestrator
4. Graceful degradation over hard failure  → Layer 1: partial_context, not failed
5. Full lineage for regulatory replay      → trace_id + 8 audit record types
6. Cloud-agnostic architecture             → patterns universal, AWS is deployment choice
7. One writer, many readers                → Redis NX writes, agents are consumers
8. Immutable audit trail                   → DynamoDB condition + S3 Object Lock
```

---

*Document version: 1.0 — COMPLETE*
*All layers, cross-cutting concerns, and architecture diagram recorded.*
*Last updated: May 2026*
*Banking Agentic AI Platform — Architecture Specification v1.0*
