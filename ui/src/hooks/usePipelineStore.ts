/**
 * Author: Sarala Biswal
 */
import { create } from "zustand";
import type { LayerState } from "../api/types";

const layerIds = ["L1", "L2", "L3", "L4", "L5", "L6"];

/**
 * Build the neutral layer state used before a pipeline run starts.
 */
function initialLayerStates(): Record<string, LayerState> {
  return Object.fromEntries(
    layerIds.map((id) => [
      id,
      {
        id,
        status: "idle",
        latencyMs: null,
        summary: null,
        error: null
      }
    ])
  );
}

interface PipelineStore {
  activeTraceId: string | null;
  selectedLayerId: string;
  layerStates: Record<string, LayerState>;
  eventLog: ExecutionLogEntry[];
  isComplete: boolean;
  setActiveTraceId: (traceId: string | null) => void;
  setSelectedLayer: (layer: string) => void;
  setLayerActive: (layer: string) => void;
  setLayerComplete: (layer: string, latencyMs: number, summary: string) => void;
  setLayerError: (layer: string, error: string) => void;
  setLayerStates: (layerStates: Record<string, LayerState>, isComplete: boolean) => void;
  appendEventLog: (entry: ExecutionLogEntry) => void;
  setComplete: () => void;
  reset: () => void;
}

export interface ExecutionLogEntry {
  id: string;
  timestamp: string;
  layer: string;
  message: string;
  level: "info" | "success" | "warning" | "error";
}

/**
 * Client-side runtime store for live pipeline visualization.
 *
 * Server state remains in React Query; this store only holds transient UI state
 * such as active layer animation, selected layer, and the execution log.
 */
export const usePipelineStore = create<PipelineStore>((set) => ({
  activeTraceId: null,
  selectedLayerId: "L1",
  layerStates: initialLayerStates(),
  eventLog: [],
  isComplete: false,
  setActiveTraceId: (traceId) => set({ activeTraceId: traceId }),
  setSelectedLayer: (layer) => set({ selectedLayerId: layer }),
  setLayerActive: (layer) =>
    set((state) => ({
      layerStates: {
        ...state.layerStates,
        [layer]: {
          // Preserve prior details while moving the layer into active state.
          ...(state.layerStates[layer] ?? emptyLayer(layer)),
          status: "active",
          error: null
        }
      }
    })),
  setLayerComplete: (layer, latencyMs, summary) =>
    set((state) => ({
      layerStates: {
        ...state.layerStates,
        [layer]: {
          ...(state.layerStates[layer] ?? emptyLayer(layer)),
          status: "complete",
          latencyMs,
          summary,
          error: null
        }
      }
    })),
  setLayerError: (layer, error) =>
    set((state) => ({
      layerStates: {
        ...state.layerStates,
        [layer]: {
          ...(state.layerStates[layer] ?? emptyLayer(layer)),
          status: "error",
          error
        }
      }
    })),
  setLayerStates: (layerStates, isComplete) => set({ layerStates, isComplete }),
  appendEventLog: (entry) =>
    set((state) =>
      // SSE replay can resend retained events; dedupe by deterministic event id.
      state.eventLog.some((existing) => existing.id === entry.id)
        ? state
        : { eventLog: [...state.eventLog, entry] }
    ),
  setComplete: () => set({ isComplete: true }),
  reset: () =>
    set({
      activeTraceId: null,
      selectedLayerId: "L1",
      layerStates: initialLayerStates(),
      eventLog: [],
      isComplete: false
    })
}));

function emptyLayer(id: string): LayerState {
  return {
    id,
    status: "idle",
    latencyMs: null,
    summary: null,
    error: null
  };
}
