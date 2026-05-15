/**
 * Author: Sarala Biswal
 */
import { useEffect } from "react";
import type { LayerState } from "../api/types";
import { apiUrl } from "../api/client";
import { usePipelineStore } from "./usePipelineStore";

interface LayerStartedEvent {
  trace_id?: string;
  traceId?: string;
  layer: string;
  timestamp: string;
}

interface LayerCompletedEvent {
  trace_id?: string;
  traceId?: string;
  layer: string;
  latency_ms?: number;
  latencyMs?: number;
  output_summary?: unknown;
  outputSummary?: unknown;
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

/**
 * Subscribe to server-sent pipeline events and project them into UI layer state.
 */
export function usePipelineEvents(
  traceId: string | null
): { layers: Record<string, LayerState>; isComplete: boolean } {
  const layerStates = usePipelineStore((state) => state.layerStates);
  const isComplete = usePipelineStore((state) => state.isComplete);
  const setActiveTraceId = usePipelineStore((state) => state.setActiveTraceId);
  const setLayerActive = usePipelineStore((state) => state.setLayerActive);
  const setLayerComplete = usePipelineStore((state) => state.setLayerComplete);
  const setLayerError = usePipelineStore((state) => state.setLayerError);
  const appendEventLog = usePipelineStore((state) => state.appendEventLog);
  const setComplete = usePipelineStore((state) => state.setComplete);

  useEffect(() => {
    if (traceId === null) {
      return undefined;
    }

    // One EventSource is opened per trace so Architecture and Runner views share a live timeline.
    setActiveTraceId(traceId);
    const source = new EventSource(apiUrl(`/pipeline/events/${encodeURIComponent(traceId)}`));
    source.addEventListener("layer_started", (event) => {
      const payload = parseEvent<LayerStartedEvent>(event);
      // Mark the node active before appending the log so visual state and text stay in sync.
      setLayerActive(payload.layer);
      appendEventLog({
        id: eventId(payload, "layer_started"),
        timestamp: payload.timestamp,
        layer: payload.layer,
        message: `${layerName(payload.layer)} started`,
        level: "info"
      });
    });
    source.addEventListener("layer_completed", (event) => {
      const payload = parseEvent<LayerCompletedEvent>(event);
      // SSE payloads may arrive in Python snake_case or already-normalized camelCase.
      const latencyMs = payload.latencyMs ?? payload.latency_ms ?? 0;
      const summaryPayload = payload.outputSummary ?? payload.output_summary ?? {};
      const summary = JSON.stringify(summaryPayload);
      setLayerComplete(payload.layer, latencyMs, summary);
      appendEventLog({
        id: eventId(payload, "layer_completed", String(latencyMs)),
        timestamp: new Date().toISOString(),
        layer: payload.layer,
        message: completionMessage(payload.layer, latencyMs, summaryPayload),
        level: completionLevel(payload.layer, summaryPayload)
      });
    });
    source.addEventListener("layer_error", (event) => {
      const payload = parseEvent<LayerErrorEvent>(event);
      setLayerError(payload.layer, payload.error);
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
      const totalMs = payload.totalMs ?? payload.total_ms ?? 0;
      setComplete();
      appendEventLog({
        id: eventId(payload, "pipeline_done", String(totalMs)),
        timestamp: new Date().toISOString(),
        layer: "ALL",
        message: `Pipeline completed in ${totalMs}ms`,
        level: "success"
      });
      // The server retains completed events, so the browser can close the stream after completion.
      source.close();
    });

    return () => {
      source.close();
    };
  }, [
    appendEventLog,
    setActiveTraceId,
    setComplete,
    setLayerActive,
    setLayerComplete,
    setLayerError,
    traceId
  ]);

  return { layers: layerStates, isComplete };
}

/**
 * Parse a typed SSE payload from the browser's EventSource API.
 */
function parseEvent<T>(event: Event): T {
  const message = event as MessageEvent<string>;
  return JSON.parse(message.data) as T;
}

/**
 * Build a stable log key from trace, event type, layer, and timestamp/suffix.
 */
function eventId(
  payload: { trace_id?: string; traceId?: string; layer?: string; timestamp?: string },
  eventType: string,
  suffix = ""
): string {
  return [payload.traceId ?? payload.trace_id ?? "trace", eventType, payload.layer ?? "all", payload.timestamp ?? suffix].join(
    ":"
  );
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
    // Layer 1 explainability needs to call out partial context immediately.
    const degraded = arrayLength(object?.sources_degraded) > 0;
    const suffix = degraded ? " with degraded CRM context" : "";
    return `Profile assembled${suffix} (${latencyMs}ms)`;
  }
  if (layer === "L2") {
    return `${arrayLength(object?.chunks)} policy chunks retrieved (${latencyMs}ms)`;
  }
  if (layer === "L3") {
    const risk = riskLevel(object) ?? "risk assessed";
    const intervention = interventionType(object);
    return intervention === null ? `Risk ${risk} (${latencyMs}ms)` : `Risk ${risk}; ${intervention} (${latencyMs}ms)`;
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

function completionLevel(layer: string, summary: unknown): "info" | "success" | "warning" | "error" {
  if (layer === "L1" && arrayLength(asRecord(summary)?.sources_degraded) > 0) {
    return "warning";
  }
  return "success";
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

function interventionType(summary: Record<string, unknown> | null): string | null {
  const outputs = arrayValue(summary?.agent_outputs);
  for (const item of outputs) {
    const output = asRecord(asRecord(item)?.output);
    const value = stringValue(output?.intervention_type);
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
