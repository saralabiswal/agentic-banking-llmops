/**
 * Author: Sarala Biswal
 */
import type { LayerStatus } from "../api/types";

export type ArchitectureSectionId = "L1" | "L2" | "L3" | "L4" | "L5" | "L6" | "OBS" | "MLOPS";

export interface DecisionRow {
  decision: string;
  choice: string;
  rationale: string;
}

export interface ArchitectureSection {
  id: ArchitectureSectionId;
  number: string;
  name: string;
  subtitle: string;
  problem: string[];
  architecture: string[];
  decisions: DecisionRow[];
  tech: string[];
}

export const layerOrder: ArchitectureSectionId[] = ["L1", "L2", "L3", "L4", "L5", "L6", "OBS", "MLOPS"];

export const sections: Record<ArchitectureSectionId, ArchitectureSection> = {
  L1: {
    id: "L1",
    number: "01",
    name: "Context Assembly",
    subtitle: "Parallel source fetch, normalization, feature merge, TTL profile",
    problem: [
      "Banking customer context lives in separate systems with different schemas and different reliability profiles. Layer 1 gives agents one canonical CustomerProfile without making upstream APIs part of agent logic.",
      "The layer favors graceful degradation over hard failure. For Marcus Webb, CRM can time out at 150ms while card, banking, behavioral, and model signals still produce a partial_context profile."
    ],
    architecture: ["Card, banking, CRM, and behavioral adapters fetch in parallel", "Normalizer maps source fields into canonical schemas", "Feature store adds risk, churn, CLV, and payment propensity", "Valkey stores session:{id}:customer_profile with EX=300 and NX=true"],
    decisions: [
      { decision: "Parallel fetch", choice: "async adapter fan-out", rationale: "Slow systems do not block faster systems." },
      { decision: "Hard timeout", choice: "150ms per source", rationale: "Layer 1 stays under the 200ms SLA." },
      { decision: "Partial context", choice: "mark degraded, continue", rationale: "Customer interventions should degrade safely instead of disappearing." },
      { decision: "One writer", choice: "Valkey NX write", rationale: "Session profiles are immutable for a run." },
      { decision: "Canonical schema", choice: "CustomerProfile", rationale: "All downstream layers share exact field names." },
      { decision: "Audit lineage", choice: "profile hash + model versions", rationale: "Regulatory replay can prove what data was used." }
    ],
    tech: ["Valkey", "PostgreSQL audit", "asyncio", "Pydantic"]
  },
  L2: {
    id: "L2",
    number: "02",
    name: "Vector Search",
    subtitle: "Dynamic query, hybrid dense/BM25 retrieval, cross-encoder rerank",
    problem: [
      "Agents need policy context at decision time, not stale prompt stuffing. Layer 2 turns the assembled profile into a dynamic query and retrieves the most relevant policy chunks.",
      "The retrieval path combines dense semantic matching with sparse exact matching, then reranks candidates so hard policy references like KB-HARD-001 are not lost."
    ],
    architecture: ["Read CustomerProfile from Valkey", "Build scenario-aware query from profile signals", "Run dense and sparse retrieval in parallel", "Merge ranks with RRF and rerank top candidates"],
    decisions: [
      { decision: "Hierarchical chunks", choice: "document -> section -> paragraph", rationale: "Agents get precise paragraphs while lineage stays intact." },
      { decision: "Hybrid search", choice: "dense + BM25", rationale: "Semantic and exact policy matches both matter." },
      { decision: "RRF merge", choice: "rank fusion", rationale: "Avoids brittle score calibration between retrievers." },
      { decision: "Metadata filters", choice: "product_line + jurisdiction", rationale: "Banking policies are scoped by product and market." },
      { decision: "Reranking", choice: "cross-encoder fallback", rationale: "Final top-k favors policy relevance over recall noise." }
    ],
    tech: ["sentence-transformers", "rank_bm25", "Qdrant", "RRF"]
  },
  L3: {
    id: "L3",
    number: "03",
    name: "Multi-Agent Orchestration",
    subtitle: "Hub-and-spoke agent routing, tool authorization, schema validation",
    problem: [
      "Specialized agents are useful only if their boundaries are enforced. Layer 3 routes work through a deterministic orchestrator so agents never call each other directly.",
      "Agents propose actions, validate outputs against schemas, and route failures to human review. Tool authorization happens in code before any tool call."
    ],
    architecture: ["Orchestrator reads profile and policy chunks", "RiskScoringAgent assesses customer risk", "Branch logic routes high risk to InterventionAgent", "Pipeline checkpoints state after each step"],
    decisions: [
      { decision: "Hub-and-spoke", choice: "orchestrator-owned routing", rationale: "Agent collaboration stays deterministic and auditable." },
      { decision: "Agents propose", choice: "no execution tools", rationale: "Layer 4 must gate every customer-facing action." },
      { decision: "Tool registry", choice: "code authorization", rationale: "Prompt instructions are not a security boundary." },
      { decision: "Schema validation", choice: "Pydantic outputs", rationale: "Downstream guardrails receive typed action proposals." },
      { decision: "Failure routing", choice: "human review queue", rationale: "Timeouts and schema errors do not silently disappear." }
    ],
    tech: ["Mock/LiteLLM", "Static pipeline registry", "Valkey checkpoints", "HumanReviewQueue"]
  },
  L4: {
    id: "L4",
    number: "04",
    name: "Guardrails & Policy",
    subtitle: "Regulatory, business, and responsible AI checks before execution",
    problem: [
      "The platform cannot let product teams or agents bypass compliance. Layer 4 is the runtime policy gate between proposed actions and execution.",
      "Checks run in strict order: regulatory, business policy, then responsible AI. A regulatory block stops all later evaluation immediately."
    ],
    architecture: ["Load versioned YAML rule files", "Evaluate regulatory checks first", "Evaluate business policy and AI checks for non-blocked actions", "Queue flagged actions with SLA deadlines"],
    decisions: [
      { decision: "Strict sequence", choice: "REGULATORY -> BUSINESS -> AI", rationale: "Compliance blocks should stop the action immediately." },
      { decision: "YAML rules", choice: "versioned rule store", rationale: "Policy teams can update rules without code changes." },
      { decision: "Approval queue", choice: "SLA-backed items", rationale: "Flagged actions become trackable human workflow." },
      { decision: "Fairness checks", choice: "AIR monitoring", rationale: "Policy outcomes need protected-class disparity controls." },
      { decision: "Audit all checks", choice: "rule_id + version + status", rationale: "Regulators can replay exact policy decisions." }
    ],
    tech: ["PyYAML", "RuleLoader", "ApprovalQueueService", "BISG fairness"]
  },
  L5: {
    id: "L5",
    number: "05",
    name: "A/B Evaluation",
    subtitle: "Deterministic assignment, outcomes, drift, champion/challenger governance",
    problem: [
      "Even approved actions need measurable learning loops. Layer 5 assigns variants deterministically and records outcomes back into experiment results.",
      "The same layer owns model governance: drift monitoring, registry metadata, and outcome processing that turns production behavior into future training signal."
    ],
    architecture: ["Select variant by stable customer + experiment bucket", "Record assignment and outcome counters", "Monitor feature, prediction, and performance drift", "Register champion and challenger model versions"],
    decisions: [
      { decision: "Stable assignment", choice: "hash bucket", rationale: "The same customer always sees the same variant." },
      { decision: "Leader promotion", choice: "confidence + sample threshold", rationale: "Winning variants require statistical support." },
      { decision: "Three drift types", choice: "feature, prediction, performance", rationale: "Each catches a different model failure mode." },
      { decision: "Outcome loop", choice: "Layer 6 feedback", rationale: "Production actions create labeled governance data." },
      { decision: "Registry wrapper", choice: "MLflow", rationale: "Model lineage remains inspectable and portable." }
    ],
    tech: ["MLflow", "NumPy", "SciPy", "Evidently-style reports"]
  },
  L6: {
    id: "L6",
    number: "06",
    name: "SDK + Execution",
    subtitle: "Blueprint catalog, channel adapters, delivery receipts, outcome capture",
    problem: [
      "Product teams should not need to understand six internal AI layers to send a push notification or create a case. Layer 6 exposes a stable SDK surface.",
      "Delivery and outcome are separate events. A push can be delivered synchronously while customer enrollment arrives minutes later through the outcome API."
    ],
    architecture: ["BlueprintRunner executes approved platform blueprints", "Channel adapters send approved actions", "ExecutionResult returns delivery and tracking IDs", "OutcomeRouter feeds A/B, governance, approval feedback, and audit"],
    decisions: [
      { decision: "Blueprint catalog", choice: "platform-owned compositions", rationale: "Teams cannot assemble pipelines that bypass guardrails." },
      { decision: "Typed SDK", choice: "BankingAgenticAIClient", rationale: "Product integration stays stable and simple." },
      { decision: "Channel adapters", choice: "one adapter per channel", rationale: "Execution systems stay isolated." },
      { decision: "Separate outcome API", choice: "async customer events", rationale: "Delivery is not conversion." },
      { decision: "Trace threading", choice: "one trace_id", rationale: "Execution links back to every prior decision." }
    ],
    tech: ["FastAPI", "SSE", "Channel adapters", "Outcome API"]
  },
  OBS: {
    id: "OBS",
    number: "OBS",
    name: "Observability",
    subtitle: "Logs, metrics, traces, and immutable audit trail across every layer",
    problem: ["Operational debugging, SLO monitoring, and regulatory replay are separate audiences and separate systems.", "The trace_id threads logs, metrics, spans, audit records, queue items, outcomes, and execution results into one customer journey."],
    architecture: ["structlog contextvars", "OpenTelemetry spans to Jaeger", "Prometheus metrics per layer", "Audit records by event type"],
    decisions: [
      { decision: "Separate systems", choice: "metrics + traces + audit", rationale: "Each audience gets the right retention and query model." },
      { decision: "trace_id threading", choice: "single ID", rationale: "Root-cause analysis starts from one identifier." },
      { decision: "Immutable audit", choice: "append-only writer", rationale: "Regulatory records cannot be edited." }
    ],
    tech: ["structlog", "OpenTelemetry", "Prometheus", "Grafana"]
  },
  MLOPS: {
    id: "MLOPS",
    number: "ML",
    name: "MLOps & Drift",
    subtitle: "Feature store, drift detection, retraining signals, model registry",
    problem: ["Models drift after deployment, and agent quality depends on model freshness.", "Outcome events from Layer 6 close the loop by feeding governance and future training data."],
    architecture: ["Feature store lineage", "Champion/challenger registry", "Feature/prediction/performance drift", "Signal-based retraining"],
    decisions: [
      { decision: "Feature store", choice: "single source of truth", rationale: "Prevents training-serving skew." },
      { decision: "Retraining signals", choice: "outcomes + drift", rationale: "Retraining is triggered by evidence." },
      { decision: "Evaluation gate", choice: "accuracy + fairness + segment checks", rationale: "A model cannot ship by aggregate accuracy alone." }
    ],
    tech: ["MLflow", "Feature store", "Drift reports", "OutcomeProcessor"]
  }
};

export const edgeLabels: Record<string, string> = {
  "trigger-L1": "customer_id + session_id + scenario",
  "L1-L2": "session_id: sess_...",
  "L2-L3": "3 policy chunks",
  "L3-L4": "ACT-001 + ACT-002 proposed",
  "L4-L5": "ACT-001 APPROVED",
  "L5-L6": "Variant A selected",
  "L6-outcome": "delivery + outcome_tracking_id"
};

export const timeline = [
  { t: "T+0ms", layer: "L1", event: "Context Assembly starts. 4 adapters fire in parallel." },
  { t: "T+150ms", layer: "L1", event: "CRM timeout. Profile marked partial_context=true." },
  { t: "T+222ms", layer: "L2", event: "Hybrid ANN+BM25 retrieves KB-HARD-001 top." },
  { t: "T+2,847ms", layer: "L3", event: "RiskScoringAgent returns CRITICAL risk." },
  { t: "T+6,381ms", layer: "L4", event: "ACT-002 flagged into 4hr approval queue." },
  { t: "T+6,387ms", layer: "L5", event: "Variant A selected for payment message." },
  { t: "T+6,441ms", layer: "L6", event: "Push delivered and outcome tracking ID issued." }
];

export function statusRank(status: LayerStatus): number {
  return status === "error" ? 3 : status === "active" ? 2 : status === "complete" ? 1 : 0;
}

export interface LayerColorSet {
  border: string;
  borderIdle: string;
  bg: string;
  text: string;
  badgeBg: string;
  badgeText: string;
  shadow: string;
  tabActive: string;
}

export const LAYER_COLORS: Record<string, LayerColorSet> = {
  L1: {
    border: "border-blue-400",
    borderIdle: "border-blue-900",
    bg: "bg-blue-500/10",
    text: "text-blue-300",
    badgeBg: "bg-blue-500/25",
    badgeText: "text-blue-200",
    shadow: "shadow-[0_0_18px_rgba(59,130,246,0.35)]",
    tabActive: "bg-blue-500"
  },
  L2: {
    border: "border-purple-400",
    borderIdle: "border-purple-900",
    bg: "bg-purple-500/10",
    text: "text-purple-300",
    badgeBg: "bg-purple-500/25",
    badgeText: "text-purple-200",
    shadow: "shadow-[0_0_18px_rgba(168,85,247,0.35)]",
    tabActive: "bg-purple-500"
  },
  L3: {
    border: "border-emerald-400",
    borderIdle: "border-emerald-900",
    bg: "bg-emerald-500/10",
    text: "text-emerald-300",
    badgeBg: "bg-emerald-500/25",
    badgeText: "text-emerald-200",
    shadow: "shadow-[0_0_18px_rgba(52,211,153,0.35)]",
    tabActive: "bg-emerald-500"
  },
  L4: {
    border: "border-red-400",
    borderIdle: "border-red-900",
    bg: "bg-red-500/10",
    text: "text-red-300",
    badgeBg: "bg-red-500/25",
    badgeText: "text-red-200",
    shadow: "shadow-[0_0_18px_rgba(239,68,68,0.35)]",
    tabActive: "bg-red-500"
  },
  L5: {
    border: "border-amber-400",
    borderIdle: "border-amber-900",
    bg: "bg-amber-500/10",
    text: "text-amber-300",
    badgeBg: "bg-amber-500/25",
    badgeText: "text-amber-200",
    shadow: "shadow-[0_0_18px_rgba(245,158,11,0.35)]",
    tabActive: "bg-amber-500"
  },
  L6: {
    border: "border-cyan-400",
    borderIdle: "border-cyan-900",
    bg: "bg-cyan-500/10",
    text: "text-cyan-300",
    badgeBg: "bg-cyan-500/25",
    badgeText: "text-cyan-200",
    shadow: "shadow-[0_0_18px_rgba(34,211,238,0.35)]",
    tabActive: "bg-cyan-500"
  },
  OBS: {
    border: "border-orange-400",
    borderIdle: "border-orange-900",
    bg: "bg-orange-500/10",
    text: "text-orange-300",
    badgeBg: "bg-orange-500/25",
    badgeText: "text-orange-200",
    shadow: "shadow-[0_0_18px_rgba(251,146,60,0.35)]",
    tabActive: "bg-orange-500"
  },
  MLOPS: {
    border: "border-violet-400",
    borderIdle: "border-violet-900",
    bg: "bg-violet-500/10",
    text: "text-violet-300",
    badgeBg: "bg-violet-500/25",
    badgeText: "text-violet-200",
    shadow: "shadow-[0_0_18px_rgba(139,92,246,0.35)]",
    tabActive: "bg-violet-500"
  },
  TRIGGER: {
    border: "border-slate-600",
    borderIdle: "border-slate-700",
    bg: "bg-slate-800/60",
    text: "text-slate-400",
    badgeBg: "bg-slate-700",
    badgeText: "text-slate-300",
    shadow: "",
    tabActive: "bg-slate-600"
  },
  OUTCOME: {
    border: "border-emerald-600",
    borderIdle: "border-emerald-900",
    bg: "bg-emerald-900/20",
    text: "text-emerald-400",
    badgeBg: "bg-emerald-900/40",
    badgeText: "text-emerald-300",
    shadow: "",
    tabActive: "bg-emerald-600"
  }
};
