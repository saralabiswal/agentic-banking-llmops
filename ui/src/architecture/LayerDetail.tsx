/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import CodeBlock from "../components/CodeBlock";
import { usePipelineStore } from "../hooks/usePipelineStore";
import { LAYER_COLORS, sections, timeline, type ArchitectureSectionId } from "./content";

const tabs = ["Why", "Flow", "Decisions", "Run"] as const;
type Tab = (typeof tabs)[number];

/**
 * Renders tabbed layer documentation and live run evidence.
 */
export default function LayerDetail(): JSX.Element {
  const selectedLayerId = usePipelineStore(
    (store) => store.selectedLayerId
  ) as ArchitectureSectionId;
  const layerStates = usePipelineStore((store) => store.layerStates);
  const activeTraceId = usePipelineStore((store) => store.activeTraceId);
  const [activeTab, setActiveTab] = useState<Tab>("Why");

  const latestAudit = useQuery({
    queryKey: ["audit-latest"],
    queryFn: api.getLatestAudit,
    refetchInterval: 1500
  });

  const section = sections[selectedLayerId] ?? sections.L1;
  const state = layerStates[selectedLayerId];
  const colors = LAYER_COLORS[selectedLayerId] ?? LAYER_COLORS["L1"];

  return (
    <aside className="flex h-full flex-col overflow-hidden rounded-md border border-slate-800 bg-slate-900">
      <div className={["shrink-0 border-b border-slate-800 px-4 py-4", colors.bg].join(" ")}>
        <div className={`text-xs font-bold uppercase tracking-widest ${colors.text}`}>
          {section.number}
        </div>
        <h2 className={`mt-1 text-2xl font-bold ${colors.text}`}>{section.name}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-300">{section.subtitle}</p>

        {state != null ? (
          <div className="mt-2 flex items-center gap-2">
            <span
              className={[
                "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase",
                state.status === "active"
                  ? `${colors.bg} ${colors.text} ${colors.border} border`
                  : state.status === "complete"
                    ? `${colors.bg} ${colors.text} ${colors.border} border`
                    : state.status === "error"
                      ? "border border-red-400 bg-red-500/10 text-red-300"
                      : "border border-slate-700 bg-slate-800 text-slate-500"
              ].join(" ")}
            >
              {state.status}
            </span>
            {state.latencyMs != null && state.latencyMs > 0 ? (
              <span className={`text-xs font-semibold tabular-nums ${colors.text}`}>
                {state.latencyMs}ms
              </span>
            ) : null}
          </div>
        ) : null}
      </div>

      <div className="shrink-0 border-b border-slate-800 bg-slate-950 px-3 pt-2">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              className={[
                "rounded-t-md px-3 py-2 text-xs font-semibold transition",
                activeTab === tab ? `${colors.tabActive} text-white` : "text-slate-400 hover:text-slate-100"
              ].join(" ")}
              key={tab}
              onClick={() => setActiveTab(tab)}
              type="button"
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {activeTab === "Why" ? (
          <div className="space-y-4" data-testid="layer-problem">
            {section.problem.map((paragraph) => (
              <p className="text-sm leading-7 text-slate-300" key={paragraph}>
                {paragraph}
              </p>
            ))}
          </div>
        ) : null}

        {activeTab === "Flow" ? (
          <div className="grid gap-2 sm:grid-cols-2" data-testid="layer-architecture-tab">
            {section.architecture.map((step, index) => (
              <div
                className={["flex items-start gap-3 rounded-md border px-3 py-2.5", colors.borderIdle, colors.bg].join(" ")}
                key={step}
              >
                <span className={`mt-0.5 shrink-0 text-xs font-bold tabular-nums ${colors.text}`}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span className="text-sm text-slate-300">{step}</span>
              </div>
            ))}
          </div>
        ) : null}

        {activeTab === "Decisions" ? (
          <div className="overflow-hidden rounded-md border border-slate-800" data-testid="layer-decisions">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-500">
                <tr>
                  <th className="px-3 py-2">Decision</th>
                  <th className="px-3 py-2">Choice</th>
                  <th className="px-3 py-2">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {section.decisions.map((row) => (
                  <tr className="border-t border-slate-800 text-slate-300" key={row.decision}>
                    <td className={`px-3 py-2 font-semibold ${colors.text}`}>{row.decision}</td>
                    <td className="px-3 py-2 text-slate-200">{row.choice}</td>
                    <td className="px-3 py-2 text-slate-400">{row.rationale}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {activeTab === "Run" ? (
          <div className="space-y-4" data-testid="layer-last-run">
            <div className="grid overflow-hidden rounded-md border border-slate-800 bg-slate-950 text-sm sm:grid-cols-3">
              <div className="px-3 py-3">
                <span className="text-slate-500">Status</span>
                <span className={`mt-1 block font-semibold ${colors.text}`}>{state?.status ?? "idle"}</span>
              </div>
              <div className="border-t border-slate-800 px-3 py-3 sm:border-l sm:border-t-0">
                <span className="text-slate-500">Latency</span>
                <span className={`mt-1 block font-semibold tabular-nums ${colors.text}`}>
                  {state?.latencyMs ?? 0}ms
                </span>
              </div>
              <div className="border-t border-slate-800 px-3 py-3 sm:border-l sm:border-t-0">
                <span className="text-slate-500">Trace</span>
                <span className="mt-1 block truncate font-mono text-xs text-slate-400">
                  {activeTraceId ?? "none"}
                </span>
              </div>
            </div>
            <CodeBlock
              code={JSON.stringify(
                {
                  timeline,
                  latestAudit: latestAudit.data?.slice(0, 3) ?? []
                },
                null,
                2
              )}
              language="json"
            />
          </div>
        ) : null}
      </div>
    </aside>
  );
}
