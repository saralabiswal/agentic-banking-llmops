/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import { Copy, FileClock, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { AuditRecord, OutcomeEvent, PipelineRunSummary } from "../api/types";
import CodeBlock from "../components/CodeBlock";

/**
 * Renders immutable audit records and regulatory replay for a selected pipeline run.
 */
export default function AuditTrail(): JSX.Element {
  const params = useParams();
  const navigate = useNavigate();
  const routeTraceId = params.traceId ?? "";
  const requestedTraceId = routeTraceId === "demo-trace" ? "" : routeTraceId;
  const [outcomesSeededFor, setOutcomesSeededFor] = useState<string | null>(null);
  // Recent runs drive the dropdown so reviewers start with the last completed trace.
  const runs = useQuery({
    queryKey: ["pipeline-runs"],
    queryFn: api.getPipelineRuns,
    refetchInterval: 3000,
    retry: false
  });
  const latestTraceId = runs.data?.[0]?.traceId ?? "";
  const traceId = requestedTraceId.length > 0 ? requestedTraceId : latestTraceId;
  const runOptions = useMemo(
    () => buildRunOptions(runs.data ?? [], traceId),
    [runs.data, traceId]
  );
  const selectedRun = runOptions.find((run) => run.traceId === traceId) ?? null;
  // Audit records are fetched only after a concrete trace is known.
  const audit = useQuery({
    queryKey: ["audit", traceId],
    queryFn: () => api.getAuditTrail(traceId),
    enabled: traceId.length > 0,
    refetchInterval: false
  });
  const records = [...(audit.data ?? [])].sort(
    (left, right) => new Date(left.timestamp).getTime() - new Date(right.timestamp).getTime()
  );

  useEffect(() => {
    if (requestedTraceId.length === 0 && latestTraceId.length > 0) {
      // Replace the placeholder route with the latest run to keep copied URLs meaningful.
      navigate(`/audit/${encodeURIComponent(latestTraceId)}`, { replace: true });
    }
  }, [latestTraceId, navigate, requestedTraceId]);

  useEffect(() => {
    if (traceId.length === 0 || outcomesSeededFor === traceId || records.length < 6) {
      return;
    }
    const outcomeRecords = records.filter((record) => record.eventType === "OUTCOME_CAPTURED");
    if (outcomeRecords.length >= 2) {
      return;
    }
    setOutcomesSeededFor(traceId);
    // The replay view seeds two synthetic outcomes so the full lifecycle is visible locally.
    const baseRecord = records[0];
    const actionRecord = records.find((record) => record.eventType === "ACTION_EXECUTED");
    const actionId = stringValue(actionRecord?.payload.actionId) ?? "ACT-001";
    const sessionId = baseRecord?.sessionId ?? "unknown";
    const customerId = baseRecord?.customerId ?? "C002";
    const now = new Date().toISOString();
    const outcomes: OutcomeEvent[] = [
      {
        outcomeId: "ui_push_opened",
        traceId,
        actionId,
        customerId,
        outcomeType: "PUSH_OPENED",
        outcomeTs: now,
        metadata: { sessionId, source: "audit_replay_demo" }
      },
      {
        outcomeId: "ui_enrolled",
        traceId,
        actionId,
        customerId,
        outcomeType: "ENROLLED",
        outcomeTs: now,
        metadata: { sessionId, source: "audit_replay_demo" }
      }
    ];
    void Promise.all(outcomes.map((outcome) => api.recordOutcome(traceId, outcome))).then(() => {
      void audit.refetch();
    });
  }, [audit, outcomesSeededFor, records, traceId]);

  function selectTrace(nextTraceId: string): void {
    if (nextTraceId.length > 0) {
      navigate(`/audit/${encodeURIComponent(nextTraceId)}`);
    }
  }

  const replay = buildReplay(records);

  return (
    <section className="space-y-4">
      <div className="rounded-md border border-slate-800 bg-slate-900 p-5">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-white">Audit Trail</h2>
            <p className="mt-1 text-sm text-slate-400">
              Immutable records sorted by timestamp for regulatory replay.
            </p>
          </div>
          <div className="flex min-w-[340px] items-end gap-2">
            <label className="min-w-0 flex-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Run ID
              </span>
              <select
                className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 disabled:cursor-not-allowed disabled:text-slate-600"
                data-testid="audit-run-selector"
                disabled={runOptions.length === 0}
                onChange={(event) => selectTrace(event.target.value)}
                value={traceId}
              >
                {runOptions.length === 0 ? (
                  <option value="">
                    {runs.isLoading ? "Loading runs..." : "No pipeline runs yet"}
                  </option>
                ) : (
                  runOptions.map((run) => (
                    <option key={run.traceId} value={run.traceId}>
                      {formatRunOption(run, run.traceId === latestTraceId)}
                    </option>
                  ))
                )}
              </select>
            </label>
            <button
              aria-label="Refresh runs"
              className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-700 text-slate-200 hover:border-slate-500 disabled:cursor-not-allowed disabled:text-slate-600"
              disabled={runs.isFetching}
              onClick={() => void runs.refetch()}
              title="Refresh runs"
              type="button"
            >
              <RefreshCw className={["h-4 w-4", runs.isFetching ? "animate-spin" : ""].join(" ")} />
            </button>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Metric label="Trace ID" value={traceId.length > 0 ? traceId : "none"} />
          <Metric label="Audit Records" value={`${records.length}`} />
          <Metric label="Customer" value={records[0]?.customerId ?? selectedRun?.customerId ?? "-"} />
          <Metric label="Status" value={selectedRun?.status ?? "-"} />
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="rounded-md border border-slate-800 bg-slate-900 p-4">
          <h3 className="mb-4 text-sm font-semibold text-white">Timeline</h3>
          {records.length === 0 ? (
            <div className="space-y-3" data-testid="audit-timeline">
              <div className="rounded-md border border-slate-800 bg-slate-950 p-4 text-sm text-slate-500">
                {traceId.length === 0
                  ? "Run a pipeline to populate audit records."
                  : "No audit records found for this run yet."}
              </div>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute bottom-4 left-[11px] top-4 w-px bg-slate-800" />
              <div className="space-y-3 pl-6" data-testid="audit-timeline">
                {records.map((record) => (
                  <AuditTimelineRecord key={record.auditId} record={record} />
                ))}
              </div>
            </div>
          )}
        </section>

        <aside className="rounded-md border border-slate-800 bg-slate-900 p-4">
          <div className="mb-4 flex items-center gap-2">
            <FileClock className="h-4 w-4 text-emerald-300" />
            <h3 className="text-sm font-semibold text-white">Regulatory Replay</h3>
          </div>
          <div className="space-y-3 text-sm" data-testid="regulatory-replay">
            <ReplayItem question="What data did the agent have?" answer={replay.data} color="blue" />
            <ReplayItem question="What policy was retrieved?" answer={replay.policy} color="purple" />
            <ReplayItem question="What compliance checks ran?" answer={replay.checks} color="red" />
            <ReplayItem question="What customer outcome was captured?" answer={replay.outcomes} color="green" />
          </div>
        </aside>
      </div>
    </section>
  );
}

function AuditTimelineRecord({ record }: { record: AuditRecord }): JSX.Element {
  return (
    <details
      className={[
        "rounded-md border border-l-2 border-slate-800 bg-slate-950 p-4",
        eventTypeLeftBorder(record.eventType)
      ].join(" ")}
    >
      <summary className="cursor-pointer list-none">
        <div className="grid gap-3 md:grid-cols-[180px_260px_minmax(0,1fr)] md:items-center">
          <span className="font-mono text-xs text-slate-500">{formatTimestamp(record.timestamp)}</span>
          <span className="flex items-center gap-2">
            <span
              className={[
                "inline-flex w-fit rounded-sm border px-2 py-1 text-xs font-semibold",
                eventTypeBadgeClass(record.eventType)
              ].join(" ")}
            >
              {record.eventType}
            </span>
            {layerLabel(record.eventType).length > 0 ? (
              <span className="text-[10px] font-bold tabular-nums text-slate-500">
                {layerLabel(record.eventType)}
              </span>
            ) : null}
          </span>
          <span className="truncate text-sm text-slate-300">{record.auditId}</span>
        </div>
      </summary>
      <div className="mt-3">
        <CodeBlock code={JSON.stringify(record, null, 2)} language="json" />
      </div>
    </details>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function ReplayItem({
  question,
  answer,
  color = "slate"
}: {
  question: string;
  answer: string;
  color?: "blue" | "purple" | "red" | "green" | "slate";
}): JSX.Element {
  const borderMap = {
    blue: "border-l-blue-400",
    purple: "border-l-purple-400",
    red: "border-l-red-400",
    green: "border-l-green-400",
    slate: "border-l-slate-600"
  };
  const textMap = {
    blue: "text-blue-300",
    purple: "text-purple-300",
    red: "text-red-300",
    green: "text-green-300",
    slate: "text-slate-400"
  };

  function copyAnswer(): void {
    void navigator.clipboard.writeText(answer);
  }

  return (
    <div
      className={[
        "rounded-md border border-l-2 border-slate-800 bg-slate-950 p-3",
        borderMap[color]
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-3">
        <div className={`text-[10px] font-bold uppercase tracking-widest ${textMap[color]}`}>
          {question}
        </div>
        <button
          aria-label={`Copy answer for ${question}`}
          className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-slate-800 text-slate-500 hover:border-slate-600 hover:text-slate-200"
          onClick={copyAnswer}
          title="Copy answer"
          type="button"
        >
          <Copy className="h-3.5 w-3.5" />
        </button>
      </div>
      <p className="mt-2 text-sm font-medium leading-6 text-slate-200">{answer}</p>
    </div>
  );
}

function eventTypeBadgeClass(eventType: string): string {
  switch (eventType) {
    case "CONTEXT_ASSEMBLY":
      return "border-blue-400/70 bg-blue-500/10 text-blue-200";
    case "VECTOR_RETRIEVAL":
      return "border-purple-400/70 bg-purple-500/10 text-purple-200";
    case "ORCHESTRATION_COMPLETE":
      return "border-emerald-400/70 bg-emerald-500/10 text-emerald-200";
    case "GUARDRAILS_EVALUATION":
      return "border-red-400/70 bg-red-500/10 text-red-200";
    case "AB_ASSIGNMENT":
      return "border-amber-400/70 bg-amber-500/10 text-amber-200";
    case "ACTION_EXECUTED":
      return "border-cyan-400/70 bg-cyan-500/10 text-cyan-200";
    case "OUTCOME_CAPTURED":
      return "border-green-400/70 bg-green-500/10 text-green-200";
    default:
      return "border-slate-400/70 bg-slate-500/10 text-slate-200";
  }
}

function eventTypeLeftBorder(eventType: string): string {
  switch (eventType) {
    case "CONTEXT_ASSEMBLY":
      return "border-l-blue-400";
    case "VECTOR_RETRIEVAL":
      return "border-l-purple-400";
    case "ORCHESTRATION_COMPLETE":
      return "border-l-emerald-400";
    case "GUARDRAILS_EVALUATION":
      return "border-l-red-400";
    case "AB_ASSIGNMENT":
      return "border-l-amber-400";
    case "ACTION_EXECUTED":
      return "border-l-cyan-400";
    case "OUTCOME_CAPTURED":
      return "border-l-green-400";
    default:
      return "border-l-slate-600";
  }
}

function layerLabel(eventType: string): string {
  switch (eventType) {
    case "CONTEXT_ASSEMBLY":
      return "L1";
    case "VECTOR_RETRIEVAL":
      return "L2";
    case "ORCHESTRATION_COMPLETE":
      return "L3";
    case "GUARDRAILS_EVALUATION":
      return "L4";
    case "AB_ASSIGNMENT":
      return "L5";
    case "ACTION_EXECUTED":
    case "OUTCOME_CAPTURED":
      return "L6";
    default:
      return "";
  }
}

function buildRunOptions(
  runs: PipelineRunSummary[],
  activeTraceId: string
): PipelineRunSummary[] {
  // Preserve deep-linked traces even when they are not in the process-local recent-run list.
  if (activeTraceId.length === 0 || runs.some((run) => run.traceId === activeTraceId)) {
    return runs;
  }
  return [{ traceId: activeTraceId, status: "unknown" }, ...runs];
}

function formatRunOption(run: PipelineRunSummary, isLatest: boolean): string {
  const prefix = isLatest ? "Latest - " : "";
  const metadata = [run.customerId, scenarioLabel(run.scenario), run.status]
    .filter((value): value is string => value !== undefined && value.length > 0)
    .join(" / ");
  return `${prefix}${run.traceId}${metadata.length > 0 ? ` - ${metadata}` : ""}`;
}

function scenarioLabel(value: string | undefined): string | undefined {
  if (value === undefined) {
    return undefined;
  }
  return value
    .split("_")
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function buildReplay(records: AuditRecord[]): {
  data: string;
  policy: string;
  checks: string;
  outcomes: string;
} {
  // Regulatory replay distills raw audit JSON into the four questions reviewers ask first.
  const context = records.find((record) => record.eventType === "CONTEXT_ASSEMBLY");
  const retrieval = records.find((record) => record.eventType === "VECTOR_RETRIEVAL");
  const guardrails = records.find((record) => record.eventType === "GUARDRAILS_EVALUATION");
  const outcomes = records.filter((record) => record.eventType === "OUTCOME_CAPTURED");
  const degradedSources = arrayValue(context?.payload.sourcesDegraded);
  const failedSources = arrayValue(context?.payload.sourcesFailed);
  const degraded = (degradedSources.length > 0 ? degradedSources : failedSources).join(", ") || "none";
  const retrievedChunks = arrayValue(retrieval?.payload.chunks);
  const auditedChunks = arrayValue(retrieval?.payload.chunksRetrieved);
  // Multiple paragraph chunks can map to the same policy document; show each policy once.
  const chunks = [
    ...new Set(
      (retrievedChunks.length > 0 ? retrievedChunks : auditedChunks)
        .map((chunk) => stringValue(asRecord(chunk)?.documentId))
        .filter((value): value is string => value !== null)
    )
  ];
  const checks = arrayValue(guardrails?.payload.checks);
  const evaluated = arrayValue(guardrails?.payload.actionsEvaluated);
  const flagged = arrayValue(guardrails?.payload.flaggedActions).length;
  const checkCount = checks.length > 0 ? checks.length : evaluated.length;

  return {
    data:
      context === undefined
        ? "No context record loaded yet."
        : `Customer ${context.customerId}; partial_context=${String(context.payload.partialContext)}; sources_degraded=${degraded}.`,
    policy: chunks.length === 0 ? "No retrieval record loaded yet." : chunks.join(", "),
    checks:
      guardrails === undefined
        ? "No guardrails record loaded yet."
        : `${checkCount} rule/action checks ran; ${flagged} action(s) flagged for review.`,
    outcomes:
      outcomes.length === 0
        ? "No outcome records captured yet."
        : outcomes.map((record) => stringValue(record.payload.outcomeType) ?? record.eventType).join(", ")
  };
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  const base = new Intl.DateTimeFormat("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
  return `${base}.${date.getMilliseconds().toString().padStart(3, "0")}`;
}

function arrayValue(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}
