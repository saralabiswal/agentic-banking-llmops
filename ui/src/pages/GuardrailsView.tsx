/**
 * Author: Sarala Biswal
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { ApprovalQueueItem, Decision, Rule } from "../api/types";

const categories: Rule["category"][] = ["REGULATORY", "BUSINESS_POLICY", "RESPONSIBLE_AI"];

/**
 * Renders guardrail rules, enforcement order, and the human approval queue.
 */
export default function GuardrailsView(): JSX.Element {
  const queryClient = useQueryClient();
  const rules = useQuery({
    queryKey: ["guardrails-rules"],
    queryFn: api.getRules
  });
  const queue = useQuery({
    queryKey: ["approval-queue"],
    queryFn: api.getApprovalQueue,
    refetchInterval: 5000
  });
  const decision = useMutation({
    mutationFn: ({ queueId, value }: { queueId: string; value: Decision }) =>
      api.recordDecision(queueId, value),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["approval-queue"] });
    }
  });
  const now = useNow();
  const queueItems = useMemo(
    () =>
      [...(queue.data ?? [])].sort(
        (left, right) =>
          new Date(left.slaDeadline).getTime() - new Date(right.slaDeadline).getTime()
      ),
    [queue.data]
  );

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Guardrails</h2>
        <p className="mt-1 text-sm text-slate-300">
          Runtime policy enforcement, rule store visibility, and approval queue workflow.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]" data-testid="guardrails-page">
        <section className="space-y-4">
          <div className="rounded-md border border-slate-700 bg-slate-900 p-3">
            <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
              <span className="font-bold text-red-300">REGULATORY</span>
              <span className="text-slate-400">blocks immediately on failure</span>
              <span className="mx-1 text-slate-500">-&gt;</span>
              <span className="font-bold text-amber-300">BUSINESS POLICY</span>
              <span className="text-slate-400">flags for approval</span>
              <span className="mx-1 text-slate-500">-&gt;</span>
              <span className="font-bold text-blue-300">RESPONSIBLE AI</span>
              <span className="text-slate-400">confidence + fairness</span>
            </div>
          </div>
          {categories.map((category) => (
            <RuleCategory
              category={category}
              key={category}
              rules={(rules.data ?? []).filter((rule) => rule.category === category)}
            />
          ))}
        </section>

        <aside className="rounded-md border border-slate-700 bg-slate-900 p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-300" />
              <h3 className="text-sm font-semibold text-white">Approval Queue</h3>
            </div>
            <span className="text-xs text-slate-400">{queueItems.length} pending</span>
          </div>
          <div className="space-y-3" data-testid="approval-queue">
            {queueItems.length === 0 ? (
              <div className="rounded-md border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">
                Run the payment risk demo to create a flagged approval item.
              </div>
            ) : (
              queueItems.map((item) => (
                <ApprovalQueueCard
                  item={item}
                  key={item.queueId}
                  now={now}
                  onDecision={(value) => decision.mutate({ queueId: item.queueId, value })}
                />
              ))
            )}
          </div>
        </aside>
      </div>
    </section>
  );
}

function RuleCategory({ category, rules }: { category: Rule["category"]; rules: Rule[] }): JSX.Element {
  return (
    <div className="rounded-md border border-slate-700 bg-slate-900 p-4">
      <h3 className="mb-3 text-sm font-semibold text-white">{category.replace(/_/g, " ")}</h3>
      <div className="grid gap-3 md:grid-cols-2">
        {rules.map((rule) => (
          <div className="rounded-md border border-slate-700 bg-slate-950 p-3" key={rule.ruleId}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold text-slate-100">{rule.ruleId}</span>
              <span className="rounded-sm border border-blue-400/60 px-2 py-1 text-xs font-semibold text-blue-200">
                v{rule.version}
              </span>
            </div>
            <p className="mt-2 text-sm leading-6 text-slate-300">{rule.description ?? "Rule"}</p>
            <div className="mt-3 space-y-1">
              {Object.entries(rule.condition ?? {}).length === 0 ? (
                <div className="rounded-sm bg-slate-900 px-2 py-1.5 text-xs text-slate-300">
                  No condition metadata
                </div>
              ) : (
                Object.entries(rule.condition ?? {}).map(([key, value]) => (
                  <div className="flex items-center gap-2 rounded-sm bg-slate-900 px-2 py-1.5" key={key}>
                    <span className="w-20 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                      {key.replace(/_/g, " ")}
                    </span>
                    <span className="truncate font-mono text-xs text-amber-200">
                      {formatRuleValue(value)}
                    </span>
                  </div>
                ))
              )}
            </div>
            <div className="mt-2 flex items-center gap-2">
              <span
                className={[
                  "rounded-sm border px-2 py-1 text-xs font-bold",
                  outcomeClass(rule.outcome)
                ].join(" ")}
              >
                {rule.outcome ?? "FLAG"}
              </span>
              <span className="text-xs text-slate-400">on match</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ApprovalQueueCard({
  item,
  now,
  onDecision
}: {
  item: ApprovalQueueItem;
  now: Date;
  onDecision: (decision: Decision) => void;
}): JSX.Element {
  return (
    <article className="rounded-md border border-slate-700 bg-slate-950 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-white">{item.action.actionId}</h4>
          <p className="mt-1 text-xs text-slate-400">{item.queueId}</p>
        </div>
        <span className="rounded-sm border border-blue-400/60 px-2 py-1 text-xs font-semibold text-blue-200">
          {item.priority}
        </span>
      </div>
      <div className="mt-3 rounded-md border border-slate-700 bg-slate-900 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">SLA Countdown</div>
        <div className="mt-1 font-mono text-lg font-semibold text-emerald-200" data-testid="sla-countdown">
          {formatRemaining(new Date(item.slaDeadline).getTime() - now.getTime())}
        </div>
      </div>
      <div className="mt-3 space-y-1.5">
        <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-slate-400">
          Flag Reasons
        </div>
        {item.flagReasons.map((reason) => (
          <div
            className={[
              "rounded border px-2.5 py-2 text-xs font-medium",
              flagReasonClass(reason)
            ].join(" ")}
            key={reason}
          >
            {reason}
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 rounded-md border border-slate-700 bg-slate-900 p-2.5 text-xs">
        <div>
          <div className="text-slate-400">Customer</div>
          <div className="font-semibold text-slate-100">
            {String(item.context.customerId ?? "-")}
          </div>
        </div>
        <div>
          <div className="text-slate-400">Risk Level</div>
          <div className={`font-bold ${riskLevelClass(item.context.riskLevel)}`}>
            {String(item.context.riskLevel ?? "-")}
          </div>
        </div>
        <div>
          <div className="text-slate-400">Reviewer</div>
          <div className="font-semibold text-slate-100">
            {item.assignedTo ?? "unassigned"}
          </div>
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <button
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-emerald-500 px-3 text-sm font-bold text-slate-950 transition hover:bg-emerald-400"
          onClick={() => onDecision("APPROVED")}
          type="button"
        >
          <CheckCircle2 className="h-4 w-4" />
          Approve Action
        </button>
        <button
          className="inline-flex h-9 w-full items-center justify-center gap-2 rounded-md border border-red-500/50 px-3 text-sm font-semibold text-red-300 transition hover:bg-red-500/10"
          onClick={() => onDecision("REJECTED")}
          type="button"
        >
          <XCircle className="h-4 w-4" />
          Reject
        </button>
      </div>
    </article>
  );
}

function formatRuleValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.map((item) => formatRuleValue(item)).join(", ");
  }
  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }
  return String(value);
}

function outcomeClass(outcome: Rule["outcome"]): string {
  if (outcome === "BLOCK") {
    return "border-red-400/60 text-red-300";
  }
  if (outcome === "APPROVE") {
    return "border-emerald-400/60 text-emerald-300";
  }
  return "border-amber-400/60 text-amber-300";
}

function flagReasonClass(reason: string): string {
  if (reason.startsWith("R-")) {
    return "border-red-400/50 bg-red-500/5 text-red-200";
  }
  if (reason.startsWith("AI-")) {
    return "border-blue-400/50 bg-blue-500/5 text-blue-200";
  }
  return "border-amber-400/50 bg-amber-500/5 text-amber-200";
}

function riskLevelClass(value: unknown): string {
  const riskLevel = String(value);
  if (riskLevel === "CRITICAL") {
    return "text-red-300";
  }
  if (riskLevel === "HIGH") {
    return "text-amber-300";
  }
  return "text-emerald-300";
}

function useNow(): Date {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const interval = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(interval);
  }, []);
  return now;
}

function formatRemaining(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return `${pad(hours)}:${pad(minutes)}:${pad(seconds)}`;
}

function pad(value: number): string {
  return value.toString().padStart(2, "0");
}
