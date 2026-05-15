/**
 * Author: Sarala Biswal
 */
import { useEffect, useRef } from "react";
import LayerStatusBadge from "../components/LayerStatusBadge";
import { usePipelineStore } from "../hooks/usePipelineStore";
import { LAYER_COLORS, layerOrder, sections, type ArchitectureSectionId } from "./content";

interface LayerNavigatorProps {
  onSelectLayer?: (id: ArchitectureSectionId) => void;
}

/**
 * Renders compact layer navigation controls for the architecture page.
 */
export default function LayerNavigator({ onSelectLayer }: LayerNavigatorProps): JSX.Element {
  const selectedLayerId = usePipelineStore((store) => store.selectedLayerId);
  const layerStates = usePipelineStore((store) => store.layerStates);
  const setSelectedLayer = usePipelineStore((store) => store.setSelectedLayer);
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});
  const activeLayer = Object.values(layerStates).find((layer) => layer.status === "active")?.id;

  useEffect(() => {
    if (activeLayer !== undefined) {
      refs.current[activeLayer]?.scrollIntoView({ block: "nearest" });
    }
  }, [activeLayer]);

  return (
    <aside className="h-full overflow-y-auto rounded-md border border-slate-800 bg-slate-900 p-3">
      <div className="mb-3 px-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        Layer Navigator
      </div>
      <div className="space-y-2">
        {layerOrder.map((id) => {
          const section = sections[id];
          const state = layerStates[id];
          const status = state?.status ?? "idle";
          const colors = LAYER_COLORS[id] ?? LAYER_COLORS["TRIGGER"];
          const isSelected = selectedLayerId === id;
          const isActive = status === "active";
          const isComplete = status === "complete";

          return (
            <button
              className={[
                "w-full rounded-lg border px-3 py-3 text-left transition-all duration-150",
                isSelected
                  ? `${colors.border} ${colors.bg}`
                  : isActive
                    ? `${colors.borderIdle} bg-slate-950 ${colors.shadow}`
                    : "border-slate-800 bg-slate-950 hover:border-slate-600"
              ].join(" ")}
              data-testid={`navigator-${id}`}
              key={id}
              onClick={() => {
                setSelectedLayer(id as ArchitectureSectionId);
                onSelectLayer?.(id as ArchitectureSectionId);
              }}
              ref={(node) => {
                refs.current[id] = node;
              }}
              type="button"
            >
              <div className="flex items-center gap-2">
                <span
                  className={[
                    "flex h-6 w-9 items-center justify-center rounded px-1 text-[10px] font-bold",
                    isSelected || isActive || isComplete
                      ? `${colors.badgeBg} ${colors.badgeText}`
                      : "bg-slate-800 text-slate-500"
                  ].join(" ")}
                >
                  {section.number}
                </span>
                <span
                  className={[
                    "min-w-0 flex-1 truncate text-sm font-semibold",
                    isSelected || isActive ? colors.text : "text-slate-200"
                  ].join(" ")}
                >
                  {section.name}
                </span>
              </div>

              <div className="mt-2 flex items-center justify-between gap-2">
                <LayerStatusBadge status={status} />
                {state?.latencyMs != null && state.latencyMs > 0 ? (
                  <span className={`text-xs font-medium tabular-nums ${colors.text}`}>
                    {state.latencyMs}ms
                  </span>
                ) : (
                  <span className="text-xs text-slate-600">—</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </aside>
  );
}
