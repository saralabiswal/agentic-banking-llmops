/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, GitBranch, Split } from "lucide-react";
import { api } from "../api/client";
import type { EvaluationGate, ModelVersion } from "../api/types";

/**
 * Renders champion/challenger model governance and evaluation gate status.
 */
export default function ModelRegistry(): JSX.Element {
  const models = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels
  });

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Model Registry</h2>
        <p className="mt-1 text-sm text-slate-400">
          Champion/challenger registry and evaluation gates for governed models.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3" data-testid="model-registry">
        {(models.data ?? []).map((model) => (
          <ModelCard key={model.modelId} model={model} />
        ))}
      </div>
    </section>
  );
}

function ModelCard({ model }: { model: ModelVersion }): JSX.Element {
  return (
    <article className="rounded-md border border-slate-800 bg-slate-900 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{model.modelId}</h3>
          <p className="mt-1 text-sm text-slate-400">{model.version}</p>
        </div>
        <span
          className={[
            "inline-flex items-center gap-1 rounded-sm border px-2 py-1 text-xs font-semibold",
            championBadgeClass(model)
          ].join(" ")}
        >
          <CheckCircle2 className="h-3.5 w-3.5" />
          {championBadgeLabel(model)}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <Metric label="Recall" value={model.recall.toFixed(2)} />
        <Metric label="AIR" value={model.airScore.toFixed(2)} />
      </div>
      <div className="mt-4 rounded-md border border-slate-800 bg-slate-950 p-3">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-100">
          <Split className="h-4 w-4 text-blue-300" />
          Champion / Challenger
        </div>
        <div className="space-y-3">
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <div className="flex min-w-0 items-center gap-2">
                <span className="rounded-sm bg-emerald-500/20 px-1.5 py-0.5 text-[10px] font-bold text-emerald-300">
                  CHAMPION
                </span>
                <span className="truncate text-slate-300">{model.championVersion}</span>
              </div>
              <span className="font-semibold tabular-nums text-emerald-300">{model.championTraffic}%</span>
            </div>
            <div className="h-2 rounded-sm bg-slate-800">
              <div className={`h-2 rounded-sm bg-emerald-400 ${trafficWidthClass(model.championTraffic)}`} />
            </div>
          </div>
          <div>
            <div className="mb-1 flex items-center justify-between text-xs">
              <div className="flex min-w-0 items-center gap-2">
                <span className="rounded-sm bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-bold text-blue-300">
                  CHALLENGER
                </span>
                <span className="truncate text-slate-400">{model.challengerVersion}</span>
              </div>
              <span className="font-semibold tabular-nums text-blue-300">{model.challengerTraffic}%</span>
            </div>
            <div className="h-2 rounded-sm bg-slate-800">
              <div className={`h-2 rounded-sm bg-blue-400 ${trafficWidthClass(model.challengerTraffic)}`} />
            </div>
            <div className="mt-1 text-[10px] text-slate-500">
              Monitoring challenger for 7 days before promotion decision
            </div>
          </div>
        </div>
      </div>
      <div className="mt-4 rounded-md border border-slate-800 bg-slate-950 p-3">
        <div className="mb-2 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <GitBranch className="h-4 w-4 text-blue-300" />
            Evaluation Gates
          </div>
          <div className="text-xs text-slate-500">
            <span className="font-semibold text-emerald-300">
              {model.gates.filter((gate) => gate.status === "PASS").length}
            </span>
            /{model.gates.length} pass
          </div>
        </div>
        <div className="space-y-2">
          {model.gates.map((gate) => (
            <GateRow gate={gate} key={gate.name} />
          ))}
        </div>
      </div>
    </article>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-950 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function GateRow({ gate }: { gate: EvaluationGate }): JSX.Element {
  const statusConfig = {
    PASS: {
      border: "border-emerald-400/50",
      text: "text-emerald-200",
      bg: "bg-emerald-500/5",
      dot: "bg-emerald-400"
    },
    MONITOR: {
      border: "border-amber-400/50",
      text: "text-amber-200",
      bg: "bg-amber-500/5",
      dot: "bg-amber-400"
    },
    FAIL: {
      border: "border-red-400/50",
      text: "text-red-200",
      bg: "bg-red-500/5",
      dot: "bg-red-400"
    }
  };
  const config = statusConfig[gate.status];

  return (
    <div
      className={[
        "flex items-center justify-between gap-3 rounded-md border px-3 py-2.5",
        config.border,
        config.bg
      ].join(" ")}
    >
      <div className="flex min-w-0 items-center gap-2">
        <div className={`h-2 w-2 shrink-0 rounded-full ${config.dot}`} />
        <span className="truncate text-xs text-slate-300">{gate.name}</span>
      </div>
      <span className={`shrink-0 rounded-sm border px-2 py-0.5 text-[10px] font-bold ${config.border} ${config.text}`}>
        {gate.status}
      </span>
    </div>
  );
}

function championBadgeClass(model: ModelVersion): string {
  const hasMonitor = model.gates.some((gate) => gate.status === "MONITOR");
  const hasFail = model.gates.some((gate) => gate.status === "FAIL");
  if (hasFail) {
    return "border-red-400/60 bg-red-500/10 text-red-200";
  }
  if (hasMonitor) {
    return "border-amber-400/60 bg-amber-500/10 text-amber-200";
  }
  return "border-emerald-400/60 bg-emerald-500/10 text-emerald-200";
}

function championBadgeLabel(model: ModelVersion): string {
  const hasMonitor = model.gates.some((gate) => gate.status === "MONITOR");
  const hasFail = model.gates.some((gate) => gate.status === "FAIL");
  if (hasFail) {
    return "Champion - Gate Fail";
  }
  if (hasMonitor) {
    return "Champion · Monitor";
  }
  return "Champion";
}

function trafficWidthClass(value: number): string {
  if (value >= 95) {
    return "w-[95%]";
  }
  if (value >= 90) {
    return "w-[90%]";
  }
  if (value >= 80) {
    return "w-4/5";
  }
  if (value >= 70) {
    return "w-[70%]";
  }
  if (value >= 60) {
    return "w-3/5";
  }
  if (value >= 50) {
    return "w-1/2";
  }
  if (value >= 40) {
    return "w-2/5";
  }
  if (value >= 30) {
    return "w-[30%]";
  }
  if (value >= 20) {
    return "w-1/5";
  }
  if (value >= 10) {
    return "w-[10%]";
  }
  return "w-[5%]";
}
