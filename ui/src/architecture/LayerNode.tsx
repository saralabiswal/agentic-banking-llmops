/**
 * Author: Sarala Biswal
 */
import { Handle, Position, type Node, type NodeProps } from "@xyflow/react";
import { AlertCircle, CheckCircle2, Loader2 } from "lucide-react";
import { usePipelineStore } from "../hooks/usePipelineStore";
import type { ArchitectureSectionId } from "./content";
import { LAYER_COLORS } from "./content";

export interface LayerNodeData extends Record<string, unknown> {
  sectionId: ArchitectureSectionId | "TRIGGER" | "OUTCOME";
  label: string;
  subtitle: string;
  kind: "trigger" | "layer" | "outcome";
}

export type LayerNodeType = Node<LayerNodeData, "layerNode">;

/**
 * Renders an interactive architecture layer node with live status styling.
 */
export default function LayerNode({ data, selected }: NodeProps<LayerNodeType>): JSX.Element {
  const state = usePipelineStore((store) =>
    data.kind === "layer" ? store.layerStates[data.sectionId] : undefined
  );
  const setSelectedLayer = usePipelineStore((store) => store.setSelectedLayer);

  const status = state?.status ?? (data.kind === "layer" ? "idle" : "complete");
  const isActive = status === "active";
  const isComplete = status === "complete";
  const isError = status === "error";

  const colors = LAYER_COLORS[data.sectionId] ?? LAYER_COLORS["TRIGGER"];

  const borderClass = (() => {
    if (isError) return "border-red-400";
    if (isActive) return colors.border;
    if (isComplete) return colors.border;
    if (selected) return colors.border;
    return data.kind === "layer" ? colors.borderIdle : colors.border;
  })();

  const bgClass = isActive || selected ? colors.bg : "bg-slate-950";
  const glowClass = isActive ? colors.shadow : "";

  return (
    <div className="relative">
      {data.kind !== "trigger" ? (
        <Handle
          className="!h-2 !w-2 !border-slate-700 !bg-slate-700 !opacity-0"
          isConnectable={false}
          position={Position.Top}
          type="target"
        />
      ) : null}

      <button
        className={[
          "group min-h-[90px] w-[224px] rounded-lg border px-4 py-3 text-left transition-all duration-200",
          borderClass,
          bgClass,
          glowClass,
          data.kind !== "layer" ? "opacity-80" : ""
        ].join(" ")}
        data-testid={`architecture-node-${data.sectionId}`}
        onClick={() => {
          if (data.kind === "layer") {
            setSelectedLayer(data.sectionId as ArchitectureSectionId);
          }
        }}
        type="button"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span
              className={[
                "flex h-6 min-w-[28px] items-center justify-center rounded px-1.5 text-[10px] font-bold",
                isActive || isComplete || selected
                  ? `${colors.badgeBg} ${colors.badgeText}`
                  : "bg-slate-800 text-slate-500"
              ].join(" ")}
            >
              {data.sectionId === "TRIGGER" ? "⚡" : data.sectionId === "OUTCOME" ? "↩" : data.sectionId}
            </span>
            <div className="min-w-0">
              <div
                className={[
                  "text-sm font-semibold leading-tight",
                  isActive || selected ? colors.text : "text-slate-200"
                ].join(" ")}
              >
                {data.label}
              </div>
            </div>
          </div>

          {isActive ? (
            <Loader2 className={`h-4 w-4 shrink-0 animate-spin ${colors.text}`} />
          ) : isComplete ? (
            <CheckCircle2 className={`h-4 w-4 shrink-0 ${colors.text}`} />
          ) : isError ? (
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
          ) : null}
        </div>

        <div className="mt-2 text-[11px] leading-5 text-slate-400">{data.subtitle}</div>

        {state?.latencyMs != null ? (
          <div className={`mt-2 text-[11px] font-semibold tabular-nums ${colors.text}`}>
            {state.latencyMs}ms
          </div>
        ) : null}
      </button>

      {data.kind !== "outcome" ? (
        <Handle
          className="!h-2 !w-2 !border-slate-700 !bg-slate-700 !opacity-0"
          isConnectable={false}
          position={Position.Bottom}
          type="source"
        />
      ) : null}
    </div>
  );
}
