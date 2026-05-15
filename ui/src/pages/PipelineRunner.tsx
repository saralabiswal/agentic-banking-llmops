/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import { Copy, ExternalLink, Play } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { useState } from "react";
import { api } from "../api/client";
import type { ExecutionResult, LayerState, Scenario } from "../api/types";
import LatencyBar from "../components/LatencyBar";
import LayerStatusBadge from "../components/LayerStatusBadge";
import { usePipelineEvents } from "../hooks/usePipelineEvents";
import { usePipelineStore } from "../hooks/usePipelineStore";

const customers = [
  { id: "C001", name: "Alexandra Chen", profile: "Prime, low risk" },
  { id: "C002", name: "Marcus Webb", profile: "Standard, high risk" },
  { id: "C003", name: "Priya Sharma", profile: "Affluent, very low risk" }
];

const scenarios: { id: Scenario; label: string }[] = [
  { id: "payment_risk_intervention", label: "Payment Risk Intervention" },
  { id: "billing_dispute_resolution", label: "Billing Dispute Resolution" },
  { id: "churn_prevention", label: "Churn Prevention" }
];

const layerIds = ["L1", "L2", "L3", "L4", "L5", "L6"];

/**
 * Renders the interactive pipeline launcher and live execution log.
 */
export default function PipelineRunner(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryTraceId = searchParams.get("trace_id") ?? searchParams.get("traceId");
  const activeTraceId = usePipelineStore((store) => store.activeTraceId);
  const reset = usePipelineStore((store) => store.reset);
  const setActiveTraceId = usePipelineStore((store) => store.setActiveTraceId);
  const eventLog = usePipelineStore((store) => store.eventLog);
  const [customerId, setCustomerId] = useState("C002");
  const [scenario, setScenario] = useState<Scenario>("payment_risk_intervention");
  const [copied, setCopied] = useState(false);
  const traceId = activeTraceId ?? queryTraceId;
  const { layers, isComplete } = usePipelineEvents(traceId);
  const layerList = layerIds.map((id) => layers[id]);
  const config = useQuery({
    queryKey: ["config"],
    queryFn: api.getConfig,
    retry: false
  });
  const status = useQuery({
    queryKey: ["pipeline-status", traceId],
    queryFn: () => api.getPipelineStatus(traceId ?? ""),
    enabled: traceId !== null,
    refetchInterval: isComplete ? false : 750
  });
  const executionResult = status.data?.executionResult ?? null;
  const summary = buildSummary(layers, executionResult, traceId);

  async function runPipeline(): Promise<void> {
    setSearchParams({});
    reset();
    const response = await api.runPipeline({
      customerId,
      scenario,
      callerId: "pipeline_runner",
      trigger: "ui"
    });
    setActiveTraceId(response.traceId);
    setSearchParams({ trace_id: response.traceId });
  }

  async function copyTraceId(): Promise<void> {
    if (traceId === null) {
      return;
    }
    await navigator.clipboard.writeText(traceId);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1200);
  }

  return (
    <section className="space-y-4">
      <div className="rounded-md border border-slate-800 bg-slate-900 p-6">
        <div className="grid gap-4 xl:grid-cols-[minmax(220px,1fr)_minmax(260px,1fr)_auto] xl:items-end">
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Customer
            </span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
              data-testid="customer-selector"
              onChange={(event) => setCustomerId(event.target.value)}
              value={customerId}
            >
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.id} - {customer.name} ({customer.profile})
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Scenario
            </span>
            <select
              className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
              data-testid="scenario-selector"
              onChange={(event) => setScenario(event.target.value as Scenario)}
              value={scenario}
            >
              {scenarios.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <span className="inline-flex h-10 items-center justify-center rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 text-xs font-semibold text-emerald-200">
            {config.data?.llmModeLabel ?? "Mock LLM"}
          </span>
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-white">Pipeline Runner</h2>
            <p className="mt-1 truncate text-sm text-slate-400">{traceId ?? "No active trace"}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <LayerStatusBadge status={isComplete ? "complete" : traceId === null ? "idle" : "active"} />
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-500 px-3 text-sm font-semibold text-white hover:bg-blue-400"
              onClick={() => void runPipeline()}
              type="button"
            >
              <Play className="h-4 w-4" />
              Run
            </button>
            <Link
              className={[
                "inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold",
                traceId === null
                  ? "pointer-events-none border-slate-800 text-slate-600"
                  : "border-slate-700 text-slate-100 hover:border-slate-500"
              ].join(" ")}
              to={traceId === null ? "#" : `/architecture?trace_id=${encodeURIComponent(traceId)}`}
            >
              Watch in Architecture View
              <ExternalLink className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="rounded-md border border-slate-800 bg-slate-900 p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Execution Log</h3>
            <span className="text-xs text-slate-500">{eventLog.length} events</span>
          </div>
          <div className="h-[360px] overflow-y-auto rounded-md border border-slate-800 bg-slate-950 p-3" data-testid="execution-log">
            {eventLog.length === 0 ? (
              <div className="text-sm text-slate-500">Run a pipeline to stream layer events.</div>
            ) : (
              <div className="space-y-2">
                {eventLog.map((entry) => (
                  <div
                    className="grid grid-cols-[88px_44px_minmax(0,1fr)] gap-3 text-sm"
                    key={entry.id}
                  >
                    <span className="font-mono text-xs text-slate-500">{formatTime(entry.timestamp)}</span>
                    <span className="text-xs font-semibold text-blue-300">[{entry.layer}]</span>
                    <span className={logLevelClass(entry.level)}>{entry.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="mt-4 grid gap-3">
            {layerList.map((layer) => (
              <div
                key={layer.id}
                className="grid grid-cols-[72px_120px_minmax(0,1fr)] items-center gap-4 rounded-md border border-slate-800 bg-slate-950 px-4 py-3"
              >
                <span className="text-sm font-semibold text-slate-200">{layer.id}</span>
                <LayerStatusBadge status={layer.status} />
                <LatencyBar latencyMs={layer.latencyMs} />
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-md border border-slate-800 bg-slate-900 p-4" data-testid="results-summary">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-white">Results Summary</h3>
            <button
              className="inline-flex h-8 items-center gap-2 rounded-md border border-slate-700 px-2 text-xs font-semibold text-slate-200 hover:border-slate-500 disabled:cursor-not-allowed disabled:text-slate-600"
              disabled={traceId === null}
              onClick={() => void copyTraceId()}
              type="button"
            >
              <Copy className="h-3.5 w-3.5" />
              {copied ? "Copied" : "Copy Trace"}
            </button>
          </div>
          <dl className="space-y-3 text-sm">
            <SummaryRow label="Risk Level" value={summary.riskLevel} />
            <SummaryRow label="Intervention" value={summary.intervention} />
            <SummaryRow label="ACT-001" value={summary.act001} />
            <SummaryRow label="ACT-002" value={summary.act002} />
            <SummaryRow label="Variant" value={summary.variant} />
            <SummaryRow label="Total Latency" value={summary.totalLatency} />
            <SummaryRow label="Trace ID" value={traceId ?? "-"} />
          </dl>
          <div className="mt-5 rounded-md border border-slate-800 bg-slate-950 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Layer Outputs
            </div>
            <div className="space-y-2">
              {layerList.map((layer) => (
                <div className="flex items-start justify-between gap-3 text-xs" key={layer.id}>
                  <span className="font-semibold text-slate-300">{layer.id}</span>
                  <span className="text-right text-slate-400">{outputLabel(layer)}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </section>
  );
}

function SummaryRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="grid grid-cols-[112px_minmax(0,1fr)] gap-3">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-100">{value}</dd>
    </div>
  );
}

function buildSummary(
  layers: Record<string, LayerState>,
  executionResult: ExecutionResult | null,
  traceId: string | null
): {
  riskLevel: string;
  intervention: string;
  act001: string;
  act002: string;
  variant: string;
  totalLatency: string;
} {
  const l3 = parseSummary(layers.L3);
  const l4 = parseSummary(layers.L4);
  const l5 = parseSummary(layers.L5);
  const risk = riskOutput(l3);
  const intervention = interventionOutput(l3);
  const approvedActions = arrayValue(l4?.approved_actions);
  const flaggedActions = arrayValue(l4?.flagged_actions);
  const pendingForTrace = (executionResult?.pendingActions ?? []).filter((item) => {
    const contextTraceId = stringValue(item.context.traceId);
    return traceId === null || contextTraceId === traceId;
  });
  const latency = Object.values(layers).reduce(
    (total, layer) => total + (layer.latencyMs ?? 0),
    0
  );

  return {
    riskLevel:
      risk === null ? "-" : `${stringValue(risk.risk_level) ?? "-"} (confidence ${numberValue(risk.confidence) ?? "-"})`,
    intervention: stringValue(intervention?.intervention_type) ?? "-",
    act001: actionStatus("ACT-001", approvedActions, flaggedActions, executionResult),
    act002:
      pendingForTrace.length > 0
        ? "FLAGGED -> Approval queue (4hr SLA)"
        : actionStatus("ACT-002", approvedActions, flaggedActions, executionResult),
    variant: variantLabel(l5),
    totalLatency: latency > 0 ? `${latency}ms` : "-"
  };
}

function actionStatus(
  actionId: string,
  approvedActions: unknown[],
  flaggedActions: unknown[],
  executionResult: ExecutionResult | null
): string {
  const approved = approvedActions.some((action) => stringValue(asRecord(action)?.action_id) === actionId);
  const flagged = flaggedActions.some((action) => stringValue(asRecord(action)?.action_id) === actionId);
  if (actionId === executionResult?.actionId && executionResult.deliveryReceipt !== null) {
    return `APPROVED -> ${executionResult.deliveryReceipt.channel} ${executionResult.deliveryReceipt.status.toLowerCase()}`;
  }
  if (approved) {
    return "APPROVED";
  }
  if (flagged) {
    return "FLAGGED -> Approval queue";
  }
  return "-";
}

function variantLabel(summary: Record<string, unknown> | null): string {
  const items = arrayValue(summary?.items);
  for (const item of items) {
    const metadata = asRecord(asRecord(item)?.metadata);
    const variant = stringValue(metadata?.variant_id);
    if (variant !== null) {
      return `${variant} - soft framing`;
    }
  }
  return "-";
}

function outputLabel(layer: LayerState): string {
  const summary = parseSummary(layer);
  if (layer.status === "idle") {
    return "waiting";
  }
  if (layer.status === "active") {
    return "running";
  }
  if (layer.status === "error") {
    return layer.error ?? "error";
  }
  if (layer.id === "L1") {
    return arrayValue(summary?.sources_degraded).length > 0 ? "DEGRADED profile" : "profile assembled";
  }
  if (layer.id === "L2") {
    return `${arrayValue(summary?.chunks).length} chunks`;
  }
  if (layer.id === "L3") {
    return stringValue(riskOutput(summary)?.risk_level) ?? "agent outputs";
  }
  if (layer.id === "L4") {
    return `${arrayValue(summary?.approved_actions).length} approved / ${arrayValue(summary?.flagged_actions).length} flagged`;
  }
  if (layer.id === "L5") {
    return variantLabel(summary);
  }
  if (layer.id === "L6") {
    return stringValue(summary?.status) ?? "executed";
  }
  return "complete";
}

function parseSummary(layer: LayerState | undefined): Record<string, unknown> | null {
  if (layer?.summary === null || layer?.summary === undefined) {
    return null;
  }
  try {
    return asRecord(JSON.parse(layer.summary));
  } catch {
    return null;
  }
}

function riskOutput(summary: Record<string, unknown> | null): Record<string, unknown> | null {
  return agentOutput(summary, "RiskScoringAgent");
}

function interventionOutput(summary: Record<string, unknown> | null): Record<string, unknown> | null {
  return agentOutput(summary, "InterventionAgent");
}

function agentOutput(
  summary: Record<string, unknown> | null,
  agentName: string
): Record<string, unknown> | null {
  for (const item of arrayValue(summary?.agent_outputs)) {
    const record = asRecord(item);
    if (stringValue(record?.agent_name) === agentName) {
      return asRecord(record?.output);
    }
  }
  return null;
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "--:--:--";
  }
  return new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

function logLevelClass(level: "info" | "success" | "warning" | "error"): string {
  if (level === "success") {
    return "text-emerald-200";
  }
  if (level === "warning") {
    return "text-blue-200";
  }
  if (level === "error") {
    return "text-red-200";
  }
  return "text-slate-300";
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function numberValue(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
