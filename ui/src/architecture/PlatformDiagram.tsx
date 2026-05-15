/**
 * Author: Sarala Biswal
 */
import type { LayerState } from "../api/types";
import { usePipelineStore } from "../hooks/usePipelineStore";
import { LAYER_COLORS, sections, type ArchitectureSectionId } from "./content";

const layerIds = ["L1", "L2", "L3", "L4", "L5", "L6"] as const;
type LayerId = (typeof layerIds)[number];

interface FlowNote {
  input: string;
  output: string;
  decision: string;
}

interface PlatformDiagramProps {
  canStepBack: boolean;
  canStepNext: boolean;
  currentLayerId: LayerId;
  note: FlowNote;
  onSelectLayer: (id: ArchitectureSectionId) => void;
  onStepBack: () => void;
  onStepNext: () => void;
  showStepActions: boolean;
}

/**
 * Renders the six-layer architecture graph and data-flow overlays.
 */
export default function PlatformDiagram({
  canStepBack,
  canStepNext,
  currentLayerId,
  note,
  onSelectLayer,
  onStepBack,
  onStepNext,
  showStepActions
}: PlatformDiagramProps): JSX.Element {
  const layerStates = usePipelineStore((store) => store.layerStates);
  const completedCount = layerIds.filter((id) => layerStates[id]?.status === "complete").length;
  const activeCount = layerIds.filter((id) => layerStates[id]?.status === "active").length;
  const pendingCount = layerIds.length - completedCount - activeCount;

  return (
    <section className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(352px,1fr)_auto_auto] gap-3 overflow-x-hidden overflow-y-auto rounded-md border border-slate-800 bg-slate-950 bg-[radial-gradient(circle_at_1px_1px,rgba(148,163,184,0.14)_1px,transparent_0)] bg-[length:18px_18px] p-4">
      <div className="grid gap-3 rounded-md border border-slate-800 bg-slate-900/85 px-3 py-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="min-w-0">
          <h3 className="text-base font-semibold text-white">Six-Layer Flow Board</h3>
          <p className="mt-1 text-xs text-slate-400">
            Dense layer map for comparing responsibilities, handoffs, and live run state.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusPill label={`${completedCount} complete`} tone="good" />
          <StatusPill label={`${activeCount} active`} tone="good" />
          <StatusPill label={`${pendingCount} pending`} />
        </div>
      </div>

      <CrossCuttingBand
        label="Observability"
        meta="trace_id threaded end-to-end"
        text="Every layer emits logs, spans, metrics, audit records, and SSE events."
        tone="orange"
      />

      <div className="grid min-h-0 grid-cols-3 gap-3 auto-rows-[minmax(170px,1fr)]">
        {layerIds.map((id) => (
          <LayerTile
            canStepBack={canStepBack}
            canStepNext={canStepNext}
            currentLayerId={currentLayerId}
            id={id}
            key={id}
            onSelectLayer={onSelectLayer}
            onStepBack={onStepBack}
            onStepNext={onStepNext}
            showStepActions={showStepActions}
            state={layerStates[id]}
          />
        ))}
      </div>

      <CrossCuttingBand
        label="MLOps"
        meta="experiments + model registry"
        text="Outcomes and drift signals feed model governance after delivery."
        tone="purple"
      />

      <div className="grid gap-3 md:grid-cols-3">
        <HandoffCard label="Current Input" value={note.input} />
        <HandoffCard label="Current Output" value={note.output} />
        <HandoffCard label="Next Gate" value={note.decision} />
      </div>
    </section>
  );
}

function LayerTile({
  canStepBack,
  canStepNext,
  currentLayerId,
  id,
  onSelectLayer,
  onStepBack,
  onStepNext,
  showStepActions,
  state
}: {
  canStepBack: boolean;
  canStepNext: boolean;
  currentLayerId: LayerId;
  id: LayerId;
  onSelectLayer: (id: ArchitectureSectionId) => void;
  onStepBack: () => void;
  onStepNext: () => void;
  showStepActions: boolean;
  state: LayerState | undefined;
}): JSX.Element {
  const selectedLayerId = usePipelineStore((store) => store.selectedLayerId);
  const section = sections[id];
  const status = state?.status ?? "idle";
  const colors = LAYER_COLORS[id];
  const isSelected = selectedLayerId === id;
  const isActive = status === "active";
  const isComplete = status === "complete";
  const isError = status === "error";
  const showActions = showStepActions && currentLayerId === id && (isActive || isError);
  const nextId = nextLayerId(id);
  const previousId = previousLayerId(id);

  return (
    <div
      className={[
        "group relative flex min-h-[170px] cursor-pointer flex-col justify-between overflow-hidden rounded-lg border p-3 text-left transition",
        isError
          ? "border-red-400 bg-red-500/10"
          : isActive || isSelected
            ? `${colors.border} ${colors.bg} ${isActive ? colors.shadow : ""}`
            : isComplete
              ? `${colors.border} bg-slate-950/90`
              : `${colors.borderIdle} bg-slate-950/80 opacity-75 hover:opacity-100`,
        showActions ? "pb-12" : ""
      ].join(" ")}
      data-testid={`architecture-node-${id}`}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelectLayer(id);
        }
      }}
      onClick={() => onSelectLayer(id)}
      role="button"
      tabIndex={0}
    >
      {edgeAfter(id) ? (
        <span
          className={[
            "pointer-events-none absolute z-10 flex h-7 w-7 items-center justify-center rounded-full border border-slate-700 bg-slate-950 text-sm text-slate-500",
            id === "L3" ? "-bottom-4 left-1/2 -translate-x-1/2" : "-right-4 top-1/2 -translate-y-1/2"
          ].join(" ")}
          data-testid="architecture-edge"
        >
          {id === "L3" ? "↓" : "→"}
        </span>
      ) : null}

      <div>
        <div className="flex items-start gap-2">
          <span
            className={[
              "flex h-6 min-w-[32px] items-center justify-center rounded px-1.5 text-[10px] font-bold",
              isActive || isComplete || isSelected
                ? `${colors.badgeBg} ${colors.badgeText}`
                : "bg-slate-800 text-slate-500"
            ].join(" ")}
          >
            {id}
          </span>
          <h3 className={`text-sm font-semibold leading-tight ${isActive || isSelected ? colors.text : "text-slate-200"}`}>
            {section.name}
          </h3>
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">{section.subtitle}</p>
      </div>

      <div>
        <div className={`mt-3 text-[11px] font-semibold tabular-nums ${isError ? "text-red-300" : colors.text}`}>
          {statusLabel(status, state?.latencyMs)}
        </div>
        {showActions ? (
          <div
            className="absolute bottom-2.5 left-3 right-3 grid grid-cols-2 gap-2"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              aria-label={previousId === null ? "Back" : `Back to ${previousId}`}
              className="h-7 rounded-full border border-emerald-400/40 bg-slate-950/80 px-2 text-[11px] font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-45"
              disabled={!canStepBack}
              onClick={onStepBack}
              type="button"
            >
              ← Back
            </button>
            <button
              aria-label={nextId === null ? "Next" : `Next to ${nextId}`}
              className="h-7 rounded-full bg-emerald-500 px-2 text-[11px] font-bold text-slate-950 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              disabled={!canStepNext}
              onClick={onStepNext}
              type="button"
            >
              Next →
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function CrossCuttingBand({
  label,
  meta,
  text,
  tone
}: {
  label: string;
  meta: string;
  text: string;
  tone: "orange" | "purple";
}): JSX.Element {
  const color =
    tone === "orange"
      ? "border-orange-400/35 bg-orange-500/10 text-orange-300"
      : "border-purple-400/35 bg-purple-500/10 text-purple-300";
  return (
    <div
      className={`grid gap-2 rounded-md border px-3 py-2.5 text-xs md:grid-cols-[auto_minmax(0,1fr)_auto] md:items-center ${color}`}
      data-testid="cross-cutting-bar"
    >
      <strong className="uppercase tracking-widest">{label}</strong>
      <span className="min-w-0 text-slate-400">{text}</span>
      <code className="font-mono text-[11px] text-slate-300">{meta}</code>
    </div>
  );
}

function StatusPill({ label, tone }: { label: string; tone?: "good" }): JSX.Element {
  return (
    <span
      className={[
        "rounded-full border px-3 py-1 text-xs font-semibold",
        tone === "good"
          ? "border-emerald-400/50 text-emerald-300"
          : "border-slate-700 text-slate-400"
      ].join(" ")}
    >
      {label}
    </span>
  );
}

function HandoffCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="min-h-[78px] rounded-md border border-slate-800 bg-slate-900/80 p-3">
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</div>
      <p className="mt-1.5 line-clamp-3 text-xs leading-5 text-slate-200" title={value}>
        {value}
      </p>
    </div>
  );
}

function statusLabel(status: string, latencyMs: number | null | undefined): string {
  if (latencyMs != null && latencyMs > 0) {
    return `${status} - ${latencyMs}ms`;
  }
  return status === "idle" ? "pending" : status;
}

function previousLayerId(id: LayerId): LayerId | null {
  const index = layerIds.indexOf(id);
  return index > 0 ? layerIds[index - 1] : null;
}

function nextLayerId(id: LayerId): LayerId | null {
  const index = layerIds.indexOf(id);
  return index < layerIds.length - 1 ? layerIds[index + 1] : null;
}

function edgeAfter(id: LayerId): boolean {
  return id !== "L6";
}
