/**
 * Author: Sarala Biswal
 */
import { Pause, Play, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState, type CSSProperties, type PointerEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api, apiUrl } from "../api/client";
import type { LayerState, Scenario } from "../api/types";
import LayerDetail from "../architecture/LayerDetail";
import PlatformDiagram from "../architecture/PlatformDiagram";
import { sections, type ArchitectureSectionId } from "../architecture/content";
import { usePipelineEvents } from "../hooks/usePipelineEvents";
import { usePipelineStore, type ExecutionLogEntry } from "../hooks/usePipelineStore";

const layerIds = ["L1", "L2", "L3", "L4", "L5", "L6"] as const;
type LayerId = (typeof layerIds)[number];
type PlaybackMode = "step" | "auto" | "realtime";

const customers = [
  { id: "C001", name: "Alexandra Chen", profile: "Prime, low risk" },
  { id: "C002", name: "Marcus Webb", profile: "Standard, high risk" },
  { id: "C003", name: "Priya Sharma", profile: "Affluent, very low risk" }
];

const scenarios: { id: Scenario; label: string }[] = [
  { id: "payment_risk_intervention", label: "Payment Risk" },
  { id: "billing_dispute_resolution", label: "Billing Dispute" },
  { id: "churn_prevention", label: "Churn Prevention" }
];

interface LayerCompletedEvent {
  trace_id?: string;
  traceId?: string;
  layer: string;
  latency_ms?: number;
  latencyMs?: number;
  output_summary?: unknown;
  outputSummary?: unknown;
}

interface LayerStartedEvent {
  trace_id?: string;
  traceId?: string;
  layer: string;
  timestamp?: string;
}

interface LayerErrorEvent {
  trace_id?: string;
  traceId?: string;
  layer: string;
  error: string;
}

interface PipelineDoneEvent {
  trace_id?: string;
  traceId?: string;
  total_ms?: number;
  totalMs?: number;
}

interface LayerPlayback {
  latencyMs: number;
  summary: string;
  summaryPayload: unknown;
}

interface TeachingNote {
  title: string;
  input: string;
  output: string;
  decision: string;
}

interface ResizeStyle extends CSSProperties {
  "--detail-width": string;
}

/**
 * Renders the live architecture diagram and layer-by-layer explainability panel.
 */
export default function ArchitectureView(): JSX.Element {
  const [searchParams, setSearchParams] = useSearchParams();
  const initialTraceId = searchParams.get("trace_id") ?? searchParams.get("traceId");
  const activeTraceId = usePipelineStore((store) => store.activeTraceId);
  const reset = usePipelineStore((store) => store.reset);
  const setActiveTraceId = usePipelineStore((store) => store.setActiveTraceId);
  const setLayerError = usePipelineStore((store) => store.setLayerError);
  const setLayerStates = usePipelineStore((store) => store.setLayerStates);
  const setSelectedLayer = usePipelineStore((store) => store.setSelectedLayer);
  const appendEventLog = usePipelineStore((store) => store.appendEventLog);
  const eventLog = usePipelineStore((store) => store.eventLog);
  const [mode, setMode] = useState<PlaybackMode>("auto");
  const [currentStep, setCurrentStep] = useState(0);
  const [autoPlaying, setAutoPlaying] = useState(true);
  const [playback, setPlayback] = useState<Record<string, LayerPlayback>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [pipelineDone, setPipelineDone] = useState(false);
  const [totalMs, setTotalMs] = useState<number | null>(null);
  const [customerId, setCustomerId] = useState(() => validCustomerId(searchParams.get("customer_id")));
  const [scenario, setScenario] = useState<Scenario>(() => validScenario(searchParams.get("scenario")));
  const [detailWidth, setDetailWidth] = useState(560);
  const [resizingDetail, setResizingDetail] = useState(false);
  const traceId = activeTraceId ?? initialTraceId;
  const selectedCustomer = customers.find((customer) => customer.id === customerId) ?? customers[1];
  const selectedScenario =
    scenarios.find((scenarioOption) => scenarioOption.id === scenario) ?? scenarios[0];
  const errorLayer = searchParams.get("error_layer") ?? searchParams.get("errorLayer");
  const isTeachingMode = mode !== "realtime";
  const currentLayerId = layerIds[Math.min(currentStep, layerIds.length - 1)];
  const currentPlayback = playback[currentLayerId];
  const runComplete = currentStep >= layerIds.length;
  const currentLayerReady =
    runComplete || currentPlayback !== undefined || errors[currentLayerId] !== undefined;
  const note = useMemo(
    () =>
      buildTeachingNote(
        currentLayerId,
        currentPlayback,
        errors[currentLayerId],
        runComplete,
        totalMs,
        selectedCustomer,
        selectedScenario
      ),
    [currentLayerId, currentPlayback, errors, runComplete, selectedCustomer, selectedScenario, totalMs]
  );

  usePipelineEvents(mode === "realtime" ? traceId : null);

  useEffect(() => {
    if (errorLayer !== null) {
      setLayerError(errorLayer, "Agent timeout");
    }
  }, [errorLayer, setLayerError]);

  useEffect(() => {
    if (!isTeachingMode || traceId === null) {
      return undefined;
    }

    setActiveTraceId(traceId);
    setPlayback({});
    setErrors({});
    setPipelineDone(false);
    setTotalMs(null);
    setCurrentStep(0);

    const source = new EventSource(apiUrl(`/pipeline/events/${encodeURIComponent(traceId)}`));

    source.addEventListener("layer_started", (event) => {
      const payload = parseEvent<LayerStartedEvent>(event);
      appendEventLog({
        id: eventId(payload, "layer_started"),
        timestamp: payload.timestamp ?? new Date().toISOString(),
        layer: payload.layer,
        message: `${layerName(payload.layer)} started`,
        level: "info"
      });
    });

    source.addEventListener("layer_completed", (event) => {
      const payload = parseEvent<LayerCompletedEvent>(event);
      const latencyMs = payload.latencyMs ?? payload.latency_ms ?? 0;
      const summaryPayload = payload.outputSummary ?? payload.output_summary ?? {};
      setPlayback((existing) => ({
        ...existing,
        [payload.layer]: {
          latencyMs,
          summary: JSON.stringify(summaryPayload),
          summaryPayload
        }
      }));
      appendEventLog({
        id: eventId(payload, "layer_completed", String(latencyMs)),
        timestamp: new Date().toISOString(),
        layer: payload.layer,
        message: completionMessage(payload.layer, latencyMs, summaryPayload),
        level: "success"
      });
    });

    source.addEventListener("layer_error", (event) => {
      const payload = parseEvent<LayerErrorEvent>(event);
      setErrors((existing) => ({ ...existing, [payload.layer]: payload.error }));
      appendEventLog({
        id: eventId(payload, "layer_error", payload.error),
        timestamp: new Date().toISOString(),
        layer: payload.layer,
        message: `${layerName(payload.layer)} failed: ${payload.error}`,
        level: "error"
      });
    });

    source.addEventListener("pipeline_done", (event) => {
      const payload = parseEvent<PipelineDoneEvent>(event);
      const nextTotalMs = payload.totalMs ?? payload.total_ms ?? 0;
      setPipelineDone(true);
      setTotalMs(nextTotalMs);
      appendEventLog({
        id: eventId(payload, "pipeline_done", String(nextTotalMs)),
        timestamp: new Date().toISOString(),
        layer: "ALL",
        message: `Pipeline completed in ${nextTotalMs}ms`,
        level: "success"
      });
      source.close();
    });

    return () => {
      source.close();
    };
  }, [appendEventLog, isTeachingMode, setActiveTraceId, traceId]);

  useEffect(() => {
    if (!isTeachingMode || traceId === null) {
      return;
    }

    setLayerStates(buildPlaybackStates(currentStep, playback, errors), runComplete && pipelineDone);
    setSelectedLayer(currentLayerId);
  }, [
    currentLayerId,
    currentStep,
    errors,
    isTeachingMode,
    pipelineDone,
    playback,
    runComplete,
    setLayerStates,
    setSelectedLayer,
    traceId
  ]);

  useEffect(() => {
    if (mode !== "auto" || !autoPlaying || traceId === null || !currentLayerReady) {
      return undefined;
    }
    if (currentStep >= layerIds.length) {
      return undefined;
    }
    const timeout = window.setTimeout(() => {
      setCurrentStep((step) => Math.min(step + 1, layerIds.length));
    }, 2200);
    return () => window.clearTimeout(timeout);
  }, [autoPlaying, currentLayerReady, currentStep, mode, traceId]);

  async function runPipeline(): Promise<void> {
    reset();
    setPlayback({});
    setErrors({});
    setPipelineDone(false);
    setTotalMs(null);
    setCurrentStep(0);
    setAutoPlaying(mode === "auto");
    const response = await api.runPipeline({
      customerId,
      scenario,
      callerId: "architecture_view",
      trigger: "ui"
    });
    setActiveTraceId(response.traceId);
    setSearchParams({ trace_id: response.traceId, customer_id: customerId, scenario });
  }

  function changeMode(nextMode: PlaybackMode): void {
    setMode(nextMode);
    setCurrentStep(0);
    setAutoPlaying(nextMode === "auto");
  }

  function goBack(): void {
    setAutoPlaying(false);
    setCurrentStep((step) => Math.max(step - 1, 0));
  }

  function goNext(): void {
    setAutoPlaying(false);
    setCurrentStep((step) => Math.min(step + 1, layerIds.length));
  }

  function replay(): void {
    setCurrentStep(0);
    setAutoPlaying(mode === "auto");
  }

  function startResize(event: PointerEvent<HTMLDivElement>): void {
    setResizingDetail(true);
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.style.userSelect = "none";
  }

  function resizeDetail(event: PointerEvent<HTMLDivElement>): void {
    if (!resizingDetail) {
      return;
    }
    const nextWidth = Math.min(720, Math.max(460, window.innerWidth - event.clientX - 24));
    setDetailWidth(nextWidth);
  }

  function endResize(event: PointerEvent<HTMLDivElement>): void {
    if (!resizingDetail) {
      return;
    }
    setResizingDetail(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
    document.body.style.userSelect = "";
  }

  function handleLayerSelected(id: ArchitectureSectionId): void {
    setSelectedLayer(id);
    if (!isTeachingMode) {
      return;
    }
    const selectedIndex = layerIds.indexOf(id as LayerId);
    if (selectedIndex >= 0) {
      setCurrentStep(selectedIndex);
      setAutoPlaying(false);
    }
  }

  return (
    <section className="flex h-full flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-white">Architecture View</h2>
          <p className="mt-1 truncate text-sm text-slate-400">{traceId ?? "No active trace"}</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <label className="block">
            <span className="sr-only">Customer</span>
            <select
              className="h-10 rounded-md border border-slate-800 bg-slate-950 px-3 text-sm font-semibold text-slate-100"
              onChange={(event) => setCustomerId(event.target.value)}
              value={customerId}
            >
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.id} - {customer.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="sr-only">Scenario</span>
            <select
              className="h-10 rounded-md border border-slate-800 bg-slate-950 px-3 text-sm font-semibold text-slate-100"
              onChange={(event) => setScenario(event.target.value as Scenario)}
              value={scenario}
            >
              {scenarios.map((scenarioOption) => (
                <option key={scenarioOption.id} value={scenarioOption.id}>
                  {scenarioOption.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex rounded-md border border-slate-800 bg-slate-950 p-1">
            {(["step", "auto", "realtime"] as const).map((item) => (
              <button
                className={[
                  "h-8 rounded px-3 text-xs font-semibold transition",
                  mode === item ? "bg-slate-100 text-slate-950" : "text-slate-400 hover:text-slate-100"
                ].join(" ")}
                key={item}
                onClick={() => changeMode(item)}
                type="button"
              >
                {modeLabel(item)}
              </button>
            ))}
          </div>
          <button
            className="inline-flex h-10 items-center gap-2 rounded-md bg-blue-500 px-3 text-sm font-semibold text-white hover:bg-blue-400"
            onClick={() => void runPipeline()}
            type="button"
          >
            <Play className="h-4 w-4" />
            Run new pipeline
          </button>
        </div>
      </div>

      <div
        className="grid min-h-0 flex-1 grid-cols-[274px_minmax(500px,1fr)_var(--detail-width)] gap-4 overflow-x-auto"
        style={{ "--detail-width": `${detailWidth}px` } as ResizeStyle}
      >
        <RunSidebar
          autoPlaying={autoPlaying}
          currentStep={currentStep}
          eventLog={eventLog}
          isStepMode={isTeachingMode}
          mode={mode}
          note={note}
          onPauseToggle={() => setAutoPlaying((playing) => !playing)}
          onReplay={replay}
          runComplete={runComplete}
          selectedCustomer={selectedCustomer}
          selectedScenario={selectedScenario}
          totalMs={totalMs}
        />
        <PlatformDiagram
          canStepBack={currentStep > 0}
          canStepNext={currentLayerReady && currentStep < layerIds.length}
          currentLayerId={currentLayerId}
          note={note}
          onSelectLayer={handleLayerSelected}
          onStepBack={goBack}
          onStepNext={goNext}
          showStepActions={isTeachingMode}
        />
        <div className="relative min-h-0">
          <div
            aria-label="Resize detail panel"
            className="absolute inset-y-0 -left-2 z-20 w-3 cursor-col-resize"
            onPointerDown={startResize}
            onPointerMove={resizeDetail}
            onPointerUp={endResize}
            role="separator"
          >
            <span className="absolute left-1 top-1/2 h-14 w-1 -translate-y-1/2 rounded-full bg-slate-700" />
          </div>
          <LayerDetail />
        </div>
      </div>
    </section>
  );
}

function RunSidebar({
  autoPlaying,
  currentStep,
  eventLog,
  isStepMode,
  mode,
  note,
  onPauseToggle,
  onReplay,
  runComplete,
  selectedCustomer,
  selectedScenario,
  totalMs
}: {
  autoPlaying: boolean;
  currentStep: number;
  eventLog: ExecutionLogEntry[];
  isStepMode: boolean;
  mode: PlaybackMode;
  note: TeachingNote;
  onPauseToggle: () => void;
  onReplay: () => void;
  runComplete: boolean;
  selectedCustomer: (typeof customers)[number];
  selectedScenario: (typeof scenarios)[number];
  totalMs: number | null;
}): JSX.Element {
  const visibleEvents = eventLog.slice(-8);
  const stepLabel = runComplete ? "Run complete" : `Step ${currentStep + 1} of ${layerIds.length}`;

  return (
    <aside className="flex h-full min-h-0 flex-col gap-3 overflow-hidden rounded-md border border-slate-800 bg-slate-900 p-3">
      <section className="rounded-md border border-slate-800 bg-slate-950 p-3">
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
          Run Context
        </div>
        <h3 className="mt-2 text-base font-bold text-white">{selectedCustomer.name}</h3>
        <p className="mt-1 text-xs leading-5 text-slate-400">
          {selectedCustomer.profile}. {selectedScenario.label} scenario.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <Metric label="Progress" value={runComplete ? "6 / 6" : `${currentStep} / 6`} />
          <Metric label="Total" value={totalMs !== null ? `${totalMs}ms` : "Running"} />
        </div>
      </section>

      {isStepMode ? (
        <section
          className="rounded-md border border-emerald-400/30 bg-emerald-500/10 p-3"
          data-testid="teaching-controls"
        >
          <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
            Step Focus
          </div>
          <div className="mt-2 text-xs font-bold uppercase tracking-widest text-emerald-300">
            {stepLabel}
          </div>
          <p className="mt-2 text-sm font-semibold leading-5 text-emerald-200">{note.title}</p>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button
              className="inline-flex h-9 items-center justify-center gap-1 rounded-md border border-slate-700 text-xs font-semibold text-slate-200 hover:border-slate-500"
              onClick={onReplay}
              type="button"
            >
              <RotateCcw className="h-4 w-4" />
              Replay
            </button>
            {mode === "auto" ? (
              <button
                className="inline-flex h-9 items-center justify-center gap-1 rounded-md border border-slate-700 text-xs font-semibold text-slate-200 hover:border-slate-500"
                onClick={onPauseToggle}
                type="button"
              >
                {autoPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                {autoPlaying ? "Pause" : "Play"}
              </button>
            ) : (
              <button
                className="inline-flex h-9 items-center justify-center gap-1 rounded-md border border-slate-800 text-xs font-semibold text-slate-500"
                disabled
                type="button"
              >
                Tile Steps
              </button>
            )}
          </div>
        </section>
      ) : null}

      <section className="min-h-0 flex-1 overflow-y-auto rounded-md border border-slate-800 bg-slate-950 p-3">
        <div className="text-[11px] font-bold uppercase tracking-widest text-slate-500">
          Run Event Timeline
        </div>
        <div className="relative mt-4 space-y-4 pl-4 before:absolute before:bottom-2 before:left-1 before:top-1 before:w-px before:bg-slate-700">
          {visibleEvents.length > 0 ? (
            visibleEvents.map((event) => <EventTimelineRow event={event} key={event.id} />)
          ) : (
            <div className="relative pl-3 text-xs leading-5 text-slate-500 before:absolute before:left-[-15px] before:top-1.5 before:h-2.5 before:w-2.5 before:rounded-full before:bg-slate-700">
              Run a pipeline to populate the event timeline.
            </div>
          )}
        </div>
      </section>
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900 px-3 py-2">
      <div className="text-[10px] font-bold uppercase tracking-widest text-slate-500">{label}</div>
      <div className="mt-1 text-sm font-bold text-white">{value}</div>
    </div>
  );
}

function EventTimelineRow({ event }: { event: ExecutionLogEntry }): JSX.Element {
  const dot =
    event.level === "success"
      ? "before:bg-emerald-400 before:shadow-[0_0_0_4px_rgba(52,211,153,0.12)]"
      : event.level === "error"
        ? "before:bg-red-400 before:shadow-[0_0_0_4px_rgba(248,113,113,0.12)]"
        : event.level === "warning"
          ? "before:bg-amber-400 before:shadow-[0_0_0_4px_rgba(251,191,36,0.12)]"
          : "before:bg-slate-500";
  return (
    <article
      className={`relative pl-3 before:absolute before:left-[-15px] before:top-1.5 before:h-2.5 before:w-2.5 before:rounded-full ${dot}`}
    >
      <div className="font-mono text-[11px] text-slate-500">{formatEventTime(event.timestamp)}</div>
      <div className="mt-0.5 text-xs font-semibold text-slate-100">{event.layer}</div>
      <p className="mt-1 text-xs leading-5 text-slate-400">{event.message}</p>
    </article>
  );
}

function formatEventTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function buildPlaybackStates(
  currentStep: number,
  playback: Record<string, LayerPlayback>,
  errors: Record<string, string>
): Record<string, LayerState> {
  return Object.fromEntries(
    layerIds.map((id, index) => {
      const completed = playback[id];
      const error = errors[id];
      if (currentStep >= layerIds.length || index < currentStep) {
        return [
          id,
          {
            id,
            status: error !== undefined ? "error" : completed !== undefined ? "complete" : "idle",
            latencyMs: completed?.latencyMs ?? null,
            summary: completed?.summary ?? null,
            error: error ?? null
          }
        ];
      }
      if (index === currentStep) {
        return [
          id,
          {
            id,
            status: error !== undefined ? "error" : "active",
            latencyMs: completed?.latencyMs ?? null,
            summary: completed?.summary ?? null,
            error: error ?? null
          }
        ];
      }
      return [
        id,
        {
          id,
          status: "idle",
          latencyMs: null,
          summary: null,
          error: null
        }
      ];
    })
  );
}

function buildTeachingNote(
  layer: LayerId,
  playback: LayerPlayback | undefined,
  error: string | undefined,
  runComplete: boolean,
  totalMs: number | null,
  selectedCustomer: (typeof customers)[number],
  selectedScenario: (typeof scenarios)[number]
): TeachingNote {
  if (runComplete) {
    return {
      title: `The pipeline finished end to end in ${totalMs ?? 0}ms. Use the layer tiles to review each handoff at human speed.`,
      input: "One trace_id ties together the trigger, context, retrieval, agents, guardrails, experiment assignment, and delivery.",
      output: "The run produced audit records, layer timings, a customer action, and an outcome tracking ID.",
      decision: "The platform stayed fast, while the walkthrough lets the architecture remain explainable."
    };
  }
  if (error !== undefined) {
    return {
      title: `${sections[layer].name} hit an error.`,
      input: "The layer received the previous pipeline state.",
      output: error,
      decision: "The walkthrough pauses on the failed layer so the failure path can be inspected."
    };
  }

  const summary = asRecord(playback?.summaryPayload);
  switch (layer) {
    case "L1":
      return {
        title: "Context Assembly builds the live customer profile before any model or agent acts.",
        input: `${selectedCustomer.id} (${selectedCustomer.profile}), ${selectedScenario.label}, and a new session_id.`,
        output:
          playback === undefined
            ? "Waiting for source adapters."
            : `Profile assembled in ${playback.latencyMs}ms with ${arrayLength(summary?.sources_degraded)} degraded source(s).`,
        decision: "CRM can time out without stopping the pipeline; downstream layers receive partial_context instead."
      };
    case "L2":
      return {
        title: "Vector Search turns the live profile into policy context.",
        input: "The session_id points to the assembled CustomerProfile in the context store.",
        output:
          playback === undefined
            ? "Waiting for retrieval results."
            : `${arrayLength(summary?.chunks)} policy chunks returned in ${playback.latencyMs}ms.`,
        decision: "Hybrid dense plus BM25 search keeps hard policy matches visible while preserving semantic recall."
      };
    case "L3":
      return {
        title: "Orchestration routes work through specialized agents without letting agents execute actions.",
        input: "Customer profile plus retrieved policy chunks.",
        output:
          playback === undefined
            ? "Waiting for agent outputs."
            : `Agents proposed ${arrayLength(summary?.proposed_actions)} action(s) in ${playback.latencyMs}ms.`,
        decision: `The risk path selected ${riskLevel(summary) ?? "the configured branch"} and sent proposals to guardrails.`
      };
    case "L4":
      return {
        title: "Guardrails decide what can execute and what needs review.",
        input: "Typed proposed actions from orchestration.",
        output:
          playback === undefined
            ? "Waiting for policy checks."
            : `${arrayLength(summary?.approved_actions)} approved, ${arrayLength(summary?.flagged_actions)} flagged, ${arrayLength(summary?.blocked_actions)} blocked.`,
        decision: "Regulatory checks run first; flagged business or AI actions become human-review queue items."
      };
    case "L5":
      return {
        title: "A/B Evaluation assigns the approved action to an experiment variant.",
        input: "Approved customer-facing actions and customer_id.",
        output:
          playback === undefined
            ? "Waiting for experiment assignment."
            : `Variant ${variantId(summary) ?? "selected"} assigned in ${playback.latencyMs}ms.`,
        decision: "Stable bucketing keeps the same customer on the same variant across repeated runs."
      };
    case "L6":
      return {
        title: "SDK Execution delivers the approved action and creates outcome tracking.",
        input: "Approved action, experiment metadata, and caller_id.",
        output:
          playback === undefined
            ? "Waiting for channel delivery."
            : `${stringValue(summary?.action_id) ?? "Action"} ${stringValue(summary?.status)?.toLowerCase() ?? "completed"} in ${playback.latencyMs}ms.`,
        decision: "Delivery is logged immediately; customer outcomes are captured later through the outcome API."
      };
  }
}

function validCustomerId(value: string | null): string {
  return customers.some((customer) => customer.id === value) ? value ?? "C002" : "C002";
}

function validScenario(value: string | null): Scenario {
  return scenarios.some((scenarioOption) => scenarioOption.id === value)
    ? (value as Scenario)
    : "payment_risk_intervention";
}

function modeLabel(mode: PlaybackMode): string {
  if (mode === "step") {
    return "Step Through";
  }
  if (mode === "auto") {
    return "Auto Tour";
  }
  return "Realtime";
}

function parseEvent<T>(event: Event): T {
  return JSON.parse((event as MessageEvent<string>).data) as T;
}

function eventId(
  payload: { trace_id?: string; traceId?: string; layer?: string; timestamp?: string },
  eventType: string,
  suffix = ""
): string {
  return [
    payload.traceId ?? payload.trace_id ?? "trace",
    eventType,
    payload.layer ?? "all",
    payload.timestamp ?? suffix
  ].join(":");
}

function layerName(layer: string): string {
  const names: Record<string, string> = {
    L1: "Context Assembly",
    L2: "Vector Search",
    L3: "Orchestration",
    L4: "Guardrails",
    L5: "A/B Evaluation",
    L6: "SDK Execution"
  };
  return names[layer] ?? layer;
}

function completionMessage(layer: string, latencyMs: number, summary: unknown): string {
  const object = asRecord(summary);
  if (layer === "L1") {
    const degraded = arrayLength(object?.sources_degraded) > 0;
    const suffix = degraded ? " with degraded CRM context" : "";
    return `Profile assembled${suffix} (${latencyMs}ms)`;
  }
  if (layer === "L2") {
    return `${arrayLength(object?.chunks)} policy chunks retrieved (${latencyMs}ms)`;
  }
  if (layer === "L3") {
    return `Risk ${riskLevel(object) ?? "assessed"} (${latencyMs}ms)`;
  }
  if (layer === "L4") {
    return `${arrayLength(object?.approved_actions)} approved, ${arrayLength(object?.flagged_actions)} flagged (${latencyMs}ms)`;
  }
  if (layer === "L5") {
    return `Variant ${variantId(object) ?? "selected"} selected (${latencyMs}ms)`;
  }
  if (layer === "L6") {
    const actionId = stringValue(object?.action_id) ?? "action";
    const status = stringValue(object?.status) ?? "executed";
    return `${actionId} ${status.toLowerCase()} (${latencyMs}ms)`;
  }
  return `${layerName(layer)} completed (${latencyMs}ms)`;
}

function riskLevel(summary: Record<string, unknown> | null): string | null {
  const outputs = arrayValue(summary?.agent_outputs);
  for (const item of outputs) {
    const output = asRecord(asRecord(item)?.output);
    const value = stringValue(output?.risk_level);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function variantId(summary: Record<string, unknown> | null): string | null {
  const items = arrayValue(summary?.items);
  for (const item of items) {
    const metadata = asRecord(asRecord(item)?.metadata);
    const value = stringValue(metadata?.variant_id);
    if (value !== null) {
      return value;
    }
  }
  return null;
}

function arrayLength(value: unknown): number {
  return Array.isArray(value) ? value.length : 0;
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
