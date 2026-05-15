/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { API_BASE_URL, api } from "../api/client";
import type { ModelVersion } from "../api/types";

/**
 * Renders model drift signals, threshold context, and Evidently report previews.
 */
export default function DriftMonitor(): JSX.Element {
  const models = useQuery({
    queryKey: ["models"],
    queryFn: api.getModels
  });
  const [selectedModelId, setSelectedModelId] = useState("risk_model");
  const modelList = models.data ?? [];
  const selected = modelList.find((model) => model.modelId === selectedModelId) ?? modelList[0];

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Drift Monitor</h2>
        <p className="mt-1 text-sm text-slate-400">
          Feature, prediction, and performance drift signals for production models.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]" data-testid="drift-page">
        <aside className="space-y-3">
          {modelList.map((model) => (
            <button
              className={[
                "w-full rounded-md border p-4 text-left transition",
                model.modelId === selected?.modelId
                  ? "border-blue-400 bg-blue-500/10"
                  : "border-slate-800 bg-slate-900 hover:border-slate-600"
              ].join(" ")}
              key={model.modelId}
              onClick={() => setSelectedModelId(model.modelId)}
              type="button"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-semibold text-slate-100">{model.modelId}</span>
                <DriftBadge status={model.driftStatus} />
              </div>
              <div className="mt-2 text-xs text-slate-500">PSI {model.psi.toFixed(2)}</div>
              <div className="mt-1 text-xs text-slate-600">
                {driftContext(model)}
              </div>
            </button>
          ))}
        </aside>
        {selected === undefined ? (
          <div className="rounded-md border border-slate-800 bg-slate-900 p-5 text-sm text-slate-500">
            No models loaded.
          </div>
        ) : (
          <ModelDriftDetail model={selected} />
        )}
      </div>
    </section>
  );
}

function ModelDriftDetail({ model }: { model: ModelVersion }): JSX.Element {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Metric label="Champion" value={model.championVersion} />
        <Metric label="Recall" value={model.recall.toFixed(2)} />
        <Metric label="AIR" value={model.airScore.toFixed(2)} />
        <Metric label="PSI" value={model.psi.toFixed(2)} />
      </div>
      <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-900 p-4 md:grid-cols-3">
        <DriftTypeCard
          description="Input distribution shift (KS test)"
          label="Feature Drift"
          status={model.psi < 0.1 ? "stable" : model.psi < 0.25 ? "monitor" : "investigate"}
          value={`PSI ${model.psi.toFixed(2)}`}
        />
        <DriftTypeCard
          description="Output score distribution shift"
          label="Prediction Drift"
          status={model.psi < 0.1 ? "stable" : "monitor"}
          value="Control chart: normal"
        />
        <DriftTypeCard
          description="Recall vs ground truth (30-day)"
          label="Performance Drift"
          status={model.recall >= 0.78 ? "stable" : "investigate"}
          value={`Recall ${model.recall.toFixed(2)}`}
        />
      </div>
      <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
        <h3 className="mb-3 text-sm font-semibold text-white">PSI Trend</h3>
        <div className="h-[260px]">
          <ResponsiveContainer height="100%" width="100%">
            <LineChart data={model.psiTrend}>
              <CartesianGrid stroke="#1e293b" />
              <XAxis dataKey="date" stroke="#94a3b8" />
              <YAxis domain={[0, 0.3]} stroke="#94a3b8" />
              <Tooltip content={<TooltipBox />} />
              <Line dataKey="psi" dot stroke="#38bdf8" strokeWidth={2} type="monotone" />
              <ReferenceLine
                label={{ value: "Monitor 0.10", position: "insideTopRight", fill: "#f59e0b", fontSize: 10 }}
                stroke="#f59e0b"
                strokeDasharray="4 4"
                strokeOpacity={0.7}
                y={0.1}
              />
              <ReferenceLine
                label={{ value: "Alert 0.25", position: "insideTopRight", fill: "#ef4444", fontSize: 10 }}
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeOpacity={0.7}
                y={0.25}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-white">Evidently Report</h3>
          <span className="text-xs text-slate-500">/drift/report/{model.modelId}</span>
        </div>
        <iframe
          className="h-[260px] w-full rounded-md border border-slate-800 bg-slate-950"
          data-testid="evidently-report"
          src={`${API_BASE_URL}/drift/report/${encodeURIComponent(model.modelId)}`}
          title={`Evidently report for ${model.modelId}`}
        />
      </div>
    </div>
  );
}

type DriftTypeStatus = ModelVersion["driftStatus"];

function DriftTypeCard({
  label,
  description,
  status,
  value
}: {
  label: string;
  description: string;
  status: DriftTypeStatus;
  value: string;
}): JSX.Element {
  const colors = {
    stable: {
      border: "border-emerald-400/40",
      text: "text-emerald-300",
      bg: "bg-emerald-500/5"
    },
    monitor: {
      border: "border-amber-400/40",
      text: "text-amber-300",
      bg: "bg-amber-500/5"
    },
    investigate: {
      border: "border-red-400/40",
      text: "text-red-300",
      bg: "bg-red-500/5"
    },
    retrain: {
      border: "border-red-400/60",
      text: "text-red-200",
      bg: "bg-red-500/10"
    }
  };
  const config = colors[status];

  return (
    <div className={`rounded-md border p-3 ${config.border} ${config.bg}`}>
      <div className={`text-xs font-bold uppercase tracking-wide ${config.text}`}>{label}</div>
      <div className="mt-1 text-xs text-slate-400">{description}</div>
      <div className={`mt-2 text-sm font-semibold ${config.text}`}>{value}</div>
      <div
        className={[
          "mt-1 inline-block rounded-sm border px-1.5 py-0.5 text-[10px] font-bold capitalize",
          config.border,
          config.text
        ].join(" ")}
      >
        {status}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function driftContext(model: ModelVersion): string {
  if (model.psi < 0.1) {
    return "Input distribution stable - no action needed";
  }
  if (model.psi < 0.25) {
    return "Moderate shift detected - monitor closely";
  }
  return "Major shift - investigate retraining trigger";
}

function DriftBadge({ status }: { status: ModelVersion["driftStatus"] }): JSX.Element {
  const className =
    status === "stable"
      ? "border-emerald-400/60 text-emerald-200"
      : status === "monitor"
        ? "border-blue-400/60 text-blue-200"
        : status === "investigate"
          ? "border-red-400/60 text-red-200"
          : "border-red-400/60 bg-red-500/10 text-red-200";
  return (
    <span className={`rounded-sm border px-2 py-1 text-xs font-semibold capitalize ${className}`}>
      {status}
    </span>
  );
}

function TooltipBox({ active, payload, label }: TooltipProps): JSX.Element | null {
  if (!active || payload === undefined || payload.length === 0) {
    return null;
  }
  return (
    <div className="rounded-md border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200">
      <div className="font-semibold">{label}</div>
      <div>PSI {String(payload[0]?.value ?? "-")}</div>
    </div>
  );
}

interface TooltipProps {
  active?: boolean;
  label?: string;
  payload?: { value?: number | string }[];
}
