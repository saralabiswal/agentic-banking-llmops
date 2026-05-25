# Logical Architecture Diagram

Author: Sarala Biswal

This diagram shows the logical runtime shape of the Banking Agentic AI Platform.
It is intentionally not a deployment diagram: the boxes describe platform
responsibilities, service boundaries, data movement, and governance checkpoints.

```mermaid
flowchart TB
  %% Logical architecture for the local reference implementation.
  %% The same boundaries map cleanly to managed cloud services in production.

  actor["Product Teams / Operators"]
  ui["React UI\nAbout, Pipeline, Architecture,\nAudit, Evaluation, Experiments,\nDrift, Guardrails, Models, Settings"]
  sdk["Layer 6 SDK Surface\nBlueprints, BankingAgenticAIClient,\nChannel Adapters"]
  api["FastAPI Platform API\npipeline, audit, guardrails,\nmodels, experiments, config, SSE"]
  evalApi["Evaluation API\nmodel options, run gates,\nhistory, judge results"]
  runner["Blueprint Runner\nTrace/session creation,\n6-layer orchestration,\nstatus tracking"]
  sse["SSE Event Bus\nlayer_started, layer_completed,\npipeline_done"]

  actor --> ui
  actor --> sdk
  ui --> api
  ui --> evalApi
  sdk --> runner
  api --> runner
  runner --> sse
  sse --> ui

  subgraph pipeline["Six-Layer Decision Pipeline"]
    direction TB

    l1["L1 Context Assembly\nParallel source fetch,\nML scoring,\nlong-term memory,\nTTL profile write"]
    l2["L2 Vector Search\nDynamic query,\nhybrid dense + BM25,\npolicy reranking"]
    l3["L3 Orchestration\nHub-and-spoke agents,\nrouted LLM inference,\ntyped propose-only actions"]
    l4["L4 Guardrails\nREGULATORY -> BUSINESS -> AI,\nblock/flag/approve,\napproval queue"]
    l5["L5 A/B + Model Governance\nDeterministic variant assignment,\noutcome attribution,\ndrift + evaluation gates"]
    l6["L6 Execution + Outcome Routing\nMock push/SMS/CRM delivery,\nreceipts,\noutcome + memory capture"]

    l1 -->|"session_id + profile key"| l2
    l2 -->|"policy chunks"| l3
    l3 -->|"proposed actions"| l4
    l4 -->|"approved actions"| l5
    l5 -->|"variant-tagged actions"| l6
  end

  runner --> l1
  l6 --> runner

  subgraph sourceSystems["Customer + Policy Inputs"]
    direction LR
    card["Card System Adapter"]
    banking["Core Banking Adapter"]
    crm["CRM Adapter\ncan degrade on timeout"]
    behavior["Behavioral Signals Adapter"]
    features["Feature Store Signals"]
    mlArtifacts["Local ML Artifacts\npayment risk + churn\npickle models"]
    kb["Knowledge Base YAML\npolicies, regulations,\nplaybooks"]
    rules["Guardrail Rule Store\nYAML versioned checks"]
    llmProviders["LLM Providers\nMock, Ollama, LiteLLM API"]
  end

  card --> l1
  banking --> l1
  crm --> l1
  behavior --> l1
  features --> l1
  mlArtifacts --> l1
  kb --> l2
  rules --> l4
  llmProviders --> l3

  subgraph stateStores["Runtime State + Evidence"]
    direction LR
    context["Valkey / Redis\nTTL customer profile"]
    qdrant["Qdrant\npolicy vectors +\ncustomer memory"]
    postgres["PostgreSQL Application DB\nfeature_store, audit_log,\napproval_queue, experiments,\noutcomes, evaluation history"]
    audit["Audit Log\ntrace_id-linked replay"]
    queue["Approval Queue\nSLA + reviewer decision"]
    exp["Experiment Store\nvariants, samples,\nconversions"]
    evalHistory["Evaluation History\nreports + judge results"]
    registry["Model Registry / MLflow\nchampion, challenger,\ngates"]
  end

  l1 --> context
  l1 --> qdrant
  context --> l2
  context --> l3
  context --> l4
  qdrant --> l1
  qdrant --> l2
  postgres --> l1
  l1 --> audit
  l2 --> audit
  l3 --> audit
  l4 --> audit
  l5 --> audit
  l6 --> audit
  l4 --> queue
  queue --> ui
  l5 --> exp
  l5 --> registry
  evalApi --> evalHistory
  evalApi --> registry
  evalHistory --> ui
  exp --> ui
  registry --> ui
  audit --> postgres
  queue --> postgres
  exp --> postgres
  evalHistory --> postgres

  subgraph observability["Cross-Cutting Observability"]
    direction LR
    logs["structlog\ntrace_id on logs"]
    traces["OpenTelemetry -> Jaeger\nper-layer spans"]
    metrics["Prometheus -> Grafana\nlatency, checks,\nthroughput"]
  end

  pipeline -. emits .-> logs
  pipeline -. emits .-> traces
  pipeline -. emits .-> metrics
  api -. exposes .-> metrics

  subgraph feedback["Learning + Governance Feedback Loop"]
    direction LR
    receipts["Delivery Receipts"]
    outcomes["Outcome Events\nopened, enrolled,\nignored, complaint"]
    review["Reviewer Decisions\napprove/reject"]
    memory["Customer Memory\ncross-session outcome signals"]
    drift["Drift Signals\nPSI, recall, AIR"]
  end

  l6 --> receipts
  l6 --> outcomes
  l6 --> memory
  outcomes --> l5
  memory --> qdrant
  review --> l4
  review --> l5
  l5 --> drift
  drift --> registry
```

## How To Read It

- **Northbound surfaces:** product teams use the SDK/API, while operators use
  the React UI for live runs, audit replay, offline evaluation, approvals,
  experiments, drift, model governance, architecture walkthroughs, and runtime
  LLM settings.
- **Decision flow:** the six layers run in strict order. Agents only propose;
  routed LLM inference produces typed agent outputs; guardrails authorize;
  Layer 6 executes.
- **Evidence flow:** every layer writes audit evidence tied to the same
  `trace_id`, while PostgreSQL keeps durable audit, approval, outcome,
  experiment, and evaluation history.
- **Feedback loop:** outcomes, reviewer decisions, customer memory, evaluation
  results, and drift signals feed Layer 5 governance so interventions can
  improve without bypassing compliance.

## Key Boundaries

| Boundary | Responsibility | Why It Exists |
| --- | --- | --- |
| UI/API boundary | Operators interact through typed API calls and SSE streams. | Keeps frontend state separate from platform orchestration. |
| Layer 1 context boundary | Source adapters, ML scoring, and memory normalize into one customer profile. | Agents never depend on upstream system schemas or raw memory/vector payloads. |
| Layer 3 inference boundary | Agents use routed LLM inference with schema validation, timeout budgets, fallback, and metadata. | Keeps provider behavior observable and prevents untyped LLM output from leaking downstream. |
| Layer 3/4 governance boundary | Agents propose actions; guardrails authorize actions. | Prevents prompt behavior from becoming the control plane. |
| Layer 5/6 execution boundary | Experiments tag approved actions before delivery and outcomes are routed back into governance/memory. | Keeps measurement and execution coupled but auditable. |
| Audit/observability boundary | Audit proves decisions; metrics/traces operate the system. | Separates regulatory replay from engineering telemetry. |

## Current Persistent Stores

| Store | Tables or Collections | Used By |
| --- | --- | --- |
| PostgreSQL | `feature_store`, `audit_log`, `approval_queue`, `experiments`, `experiment_variants`, `experiment_results`, `outcome_events`, `evaluation_reports`, `evaluation_judge_results` | Layer 1 signals, audit replay, approvals, experiments, outcomes, durable evaluation history |
| Valkey / Redis | `session:{session_id}:customer_profile`, Layer 3 checkpoints | Short-lived context handoff and orchestration recovery |
| Qdrant | `knowledge_base`, `customer_memory` | Policy retrieval and cross-session memory |
| MLflow | local or remote tracking URI | Training lineage, evaluation metrics, champion/challenger governance |

## Current Model and LLM Paths

- **Layer 1 ML scoring:** `MLScoringService` loads local payment-risk and
  churn-propensity artifacts when available and falls back to feature-store
  signals when scoring degrades.
- **Layer 3 LLM inference:** agents call `RoutedLLMInferenceService`, which
  routes to mock, Ollama, or LiteLLM API backends, applies backend-appropriate
  latency budgets, records primary/served model metadata, and falls back to the
  mock-safe backend on timeout or provider/schema failures.
- **Offline evaluation:** the Evaluation UI/API supports `payment_risk_model`
  and `churn_propensity_model`, discovers versions from MLflow plus prior
  evaluation history, runs benchmark/fairness/regression gates, and stores
  durable reports in PostgreSQL.
