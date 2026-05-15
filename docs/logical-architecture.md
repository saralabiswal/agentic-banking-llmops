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
  ui["React UI\nPipeline, Architecture, Audit,\nGuardrails, Experiments, Models"]
  sdk["Layer 6 SDK Surface\nBlueprints, ActionClient,\nChannel Adapters"]
  api["FastAPI Platform API\npipeline, audit, guardrails,\nmodels, experiments, config, SSE"]
  runner["Blueprint Runner\nTrace/session creation,\n6-layer orchestration,\nstatus tracking"]
  sse["SSE Event Bus\nlayer_started, layer_completed,\npipeline_done"]

  actor --> ui
  actor --> sdk
  ui --> api
  sdk --> runner
  api --> runner
  runner --> sse
  sse --> ui

  subgraph pipeline["Six-Layer Decision Pipeline"]
    direction TB

    l1["L1 Context Assembly\nParallel source fetch,\nnormalization,\nTTL profile write"]
    l2["L2 Vector Search\nDynamic query,\nhybrid dense + BM25,\npolicy reranking"]
    l3["L3 Orchestration\nHub-and-spoke agents,\ntyped outputs,\npropose-only actions"]
    l4["L4 Guardrails\nREGULATORY -> BUSINESS -> AI,\nblock/flag/approve,\napproval queue"]
    l5["L5 A/B + Model Governance\nDeterministic variant assignment,\noutcome attribution,\ndrift/model gates"]
    l6["L6 Execution + Outcome Routing\nMock push/SMS/CRM delivery,\nreceipts,\noutcome capture"]

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
    kb["Knowledge Base YAML\npolicies, regulations,\nplaybooks"]
    rules["Guardrail Rule Store\nYAML versioned checks"]
  end

  card --> l1
  banking --> l1
  crm --> l1
  behavior --> l1
  features --> l1
  kb --> l2
  rules --> l4

  subgraph stateStores["Runtime State + Evidence"]
    direction LR
    context["Valkey / Redis\nTTL customer profile"]
    audit["Audit Records\ntrace_id-linked replay"]
    queue["Approval Queue\nSLA + reviewer decision"]
    exp["Experiment Store\nvariants, samples,\nconversions"]
    registry["Model Registry / MLflow\nchampion, challenger,\ngates"]
  end

  l1 --> context
  context --> l2
  context --> l3
  context --> l4
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
  exp --> ui
  registry --> ui

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
    drift["Drift Signals\nPSI, recall, AIR"]
  end

  l6 --> receipts
  l6 --> outcomes
  outcomes --> l5
  review --> l4
  review --> l5
  l5 --> drift
  drift --> registry
```

## How To Read It

- **Northbound surfaces:** product teams use the SDK/API, while operators use
  the React UI for live runs, audit replay, approvals, experiments, and model
  governance.
- **Decision flow:** the six layers run in strict order. Agents only propose;
  guardrails authorize; Layer 6 executes.
- **Evidence flow:** every layer writes audit evidence tied to the same
  `trace_id`, which is what makes regulatory replay possible.
- **Feedback loop:** outcomes, reviewer decisions, and drift signals feed Layer
  5 governance so interventions can improve without bypassing compliance.

## Key Boundaries

| Boundary | Responsibility | Why It Exists |
| --- | --- | --- |
| UI/API boundary | Operators interact through typed API calls and SSE streams. | Keeps frontend state separate from platform orchestration. |
| Layer 1 context boundary | Source adapters normalize data into one customer profile. | Agents never depend on upstream system schemas. |
| Layer 3/4 governance boundary | Agents propose actions; guardrails authorize actions. | Prevents prompt behavior from becoming the control plane. |
| Layer 5/6 execution boundary | Experiments tag approved actions before delivery. | Keeps measurement and execution coupled but auditable. |
| Audit/observability boundary | Audit proves decisions; metrics/traces operate the system. | Separates regulatory replay from engineering telemetry. |

