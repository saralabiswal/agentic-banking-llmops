/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { api } from "../api/client";
import type { Experiment, ExperimentVariant } from "../api/types";

/**
 * Renders A/B test outcomes, deterministic assignment context, and conversion lift.
 */
export default function Experiments(): JSX.Element {
  const experiments = useQuery({
    queryKey: ["experiments"],
    queryFn: api.getExperiments
  });

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-white">Experiments</h2>
        <p className="mt-1 text-sm text-slate-400">
          Active and concluded tests with variant conversion and confidence.
        </p>
      </div>
      <div className="space-y-4" data-testid="experiments-page">
        {(experiments.data ?? []).map((experiment) => (
          <ExperimentPanel experiment={experiment} key={experiment.experimentId} />
        ))}
      </div>
    </section>
  );
}

function ExperimentPanel({ experiment }: { experiment: Experiment }): JSX.Element {
  const leader = [...experiment.variants].sort(
    (left, right) => conversionRate(right) - conversionRate(left)
  )[0];
  const runnerUp = [...experiment.variants]
    .filter((variant) => variant.variantId !== leader?.variantId)
    .sort((left, right) => conversionRate(right) - conversionRate(left))[0];
  const confidence = significanceConfidence(experiment.variants);
  const lift = relativeLift(leader, runnerUp);
  const chartData = experiment.variants.map((variant) => ({
    name: variant.variantId,
    conversionRate: Math.round(conversionRate(variant) * 1000) / 10,
    isLeader: variant.variantId === leader?.variantId,
    label: variant.name
  }));
  const pValue = Math.max(0.001, 1 - confidence);

  return (
    <article className="rounded-md border border-slate-800 bg-slate-900 p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-white">{experiment.experimentId}</h3>
          <p className="mt-1 text-sm text-slate-400">Leader: Variant {leader?.variantId ?? "-"}</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-sm border border-emerald-400/60 px-2 py-1 text-xs font-semibold text-emerald-200">
            {experiment.status}
          </span>
          <span className="rounded-sm border border-blue-400/60 px-2 py-1 text-xs font-semibold text-blue-200">
            p-value {pValue < 0.001 ? "<0.001" : pValue.toFixed(3)}
          </span>
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="overflow-hidden rounded-md border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950 text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Variant</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Samples</th>
                <th className="px-3 py-2">Conversions</th>
                <th className="px-3 py-2">Rate</th>
              </tr>
            </thead>
            <tbody>
              {experiment.variants.map((variant) => (
                <tr className="border-t border-slate-800 text-slate-300" key={variant.variantId}>
                  <td className="px-3 py-3">
                    <span className="font-semibold text-white">Variant {variant.variantId}</span>
                    {variant.variantId === leader?.variantId ? (
                      <span className="ml-2 rounded-sm bg-emerald-500/10 px-2 py-1 text-xs font-semibold text-emerald-200">
                        Leader
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-3">{variant.name}</td>
                  <td className="px-3 py-3 tabular-nums">{variant.sampleCount.toLocaleString()}</td>
                  <td className="px-3 py-3 tabular-nums">{variant.conversionCount.toLocaleString()}</td>
                  <td className="px-3 py-3">
                    <div className="tabular-nums font-semibold text-slate-100">
                      {(conversionRate(variant) * 100).toFixed(1)}%
                    </div>
                    <div className="mt-1 h-1.5 w-24 rounded-full bg-slate-800">
                      <div
                        className={[
                          "h-1.5 rounded-full",
                          variant.variantId === leader?.variantId ? "bg-emerald-400" : "bg-slate-600",
                          rateWidthClass(conversionRate(variant))
                        ].join(" ")}
                      />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="rounded-md border border-slate-800 bg-slate-950 p-4">
          <div className="mb-4 grid gap-4 md:grid-cols-3">
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Lift (Winner vs Next)
              </div>
              <div className="mt-1 text-2xl font-bold text-emerald-300">
                {lift === null ? "-" : `+${lift.toFixed(1)}%`}
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Statistical Confidence
              </div>
              <div className="mt-1 text-2xl font-bold text-blue-300">
                {(confidence * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Assignment Method
              </div>
              <div className="mt-1 text-sm font-semibold text-slate-200">
                Hash-based (deterministic)
              </div>
              <div className="text-xs text-slate-500">
                Same customer always sees same variant
              </div>
            </div>
          </div>
          <div className="h-[200px]">
            <ResponsiveContainer height="100%" width="100%">
              <BarChart data={chartData}>
                <CartesianGrid stroke="#1e293b" />
                <XAxis dataKey="name" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" unit="%" />
                <Tooltip content={<ExperimentTooltip />} />
                <Bar dataKey="conversionRate" name="Conversion rate" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry) => (
                    <Cell fill={entry.isLeader ? "#10b981" : "#334155"} key={entry.name} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </article>
  );
}

function ExperimentTooltip({ active, payload, label }: TooltipProps): JSX.Element | null {
  if (!active || payload === undefined || payload.length === 0) {
    return null;
  }
  return (
    <div className="rounded-md border border-slate-700 bg-slate-950 p-2 text-xs text-slate-200">
      <div className="font-semibold">Variant {label}</div>
      <div>Conversion {String(payload[0]?.value ?? "-")}%</div>
    </div>
  );
}

interface TooltipProps {
  active?: boolean;
  label?: string;
  payload?: { value?: number | string }[];
}

function conversionRate(variant: ExperimentVariant): number {
  if (variant.sampleCount === 0) {
    return 0;
  }
  return variant.conversionCount / variant.sampleCount;
}

function relativeLift(
  leader: ExperimentVariant | undefined,
  runnerUp: ExperimentVariant | undefined
): number | null {
  if (leader === undefined || runnerUp === undefined) {
    return null;
  }
  const baseline = conversionRate(runnerUp);
  if (baseline === 0) {
    return null;
  }
  return ((conversionRate(leader) - baseline) / baseline) * 100;
}

function rateWidthClass(rate: number): string {
  const width = Math.min(rate * 200, 100);
  if (width >= 95) {
    return "w-full";
  }
  if (width >= 90) {
    return "w-[90%]";
  }
  if (width >= 80) {
    return "w-4/5";
  }
  if (width >= 70) {
    return "w-[70%]";
  }
  if (width >= 60) {
    return "w-3/5";
  }
  if (width >= 50) {
    return "w-1/2";
  }
  if (width >= 40) {
    return "w-2/5";
  }
  if (width >= 30) {
    return "w-[30%]";
  }
  if (width >= 20) {
    return "w-1/5";
  }
  if (width >= 10) {
    return "w-[10%]";
  }
  return "w-[5%]";
}

function significanceConfidence(variants: ExperimentVariant[]): number {
  if (variants.length < 2) {
    return 0;
  }
  const [first, second] = variants;
  const pooled = (first.conversionCount + second.conversionCount) / (first.sampleCount + second.sampleCount);
  const standardError = Math.sqrt(
    pooled * (1 - pooled) * (1 / first.sampleCount + 1 / second.sampleCount)
  );
  if (standardError === 0) {
    return 0;
  }
  const z = Math.abs((conversionRate(first) - conversionRate(second)) / standardError);
  return z > 3.29 ? 0.999 : z > 2.58 ? 0.99 : z > 1.96 ? 0.95 : 0;
}
