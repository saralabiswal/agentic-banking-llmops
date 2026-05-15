/**
 * Author: Sarala Biswal
 */
import type {
  ApprovalQueueItem,
  AuditRecord,
  ConfigResponse,
  ConnectionTestResponse,
  Decision,
  Experiment,
  LLMBackendRequest,
  ModelVersion,
  OllamaModelsResponse,
  OutcomeEvent,
  PipelineRunSummary,
  PipelineStatus,
  Rule,
  RunPipelineRequest,
  RunPipelineResponse
} from "./types";

type JsonPrimitive = string | number | boolean | null;
type JsonValue = JsonPrimitive | JsonValue[] | { [key: string]: JsonValue };
type JsonObject = { [key: string]: JsonValue };

export const API_BASE_URL = "http://localhost:8000";

/**
 * Typed API facade used by React Query callers.
 *
 * Each method returns camelCase TypeScript data even though the FastAPI
 * contract is snake_case. Keeping that translation here prevents view
 * components from leaking transport-format details.
 */
export const api = {
  getConfig: (): Promise<ConfigResponse> => request<ConfigResponse>("/config"),
  getOllamaModels: (baseUrl: string): Promise<OllamaModelsResponse> =>
    request<OllamaModelsResponse>(
      `/config/ollama-models?base_url=${encodeURIComponent(baseUrl)}`
    ),
  updateLLMBackend: (body: LLMBackendRequest): Promise<ConfigResponse> =>
    request<ConfigResponse, LLMBackendRequest>("/config/llm-backend", {
      method: "POST",
      body
    }),
  testLLMBackend: (body: LLMBackendRequest): Promise<ConnectionTestResponse> =>
    request<ConnectionTestResponse, LLMBackendRequest>("/config/test-llm", {
      method: "POST",
      body
    }),
  runPipeline: (body: RunPipelineRequest): Promise<RunPipelineResponse> =>
    request<RunPipelineResponse, RunPipelineRequest>("/pipeline/run", {
      method: "POST",
      body
    }),
  getPipelineStatus: (traceId: string): Promise<PipelineStatus> =>
    request<PipelineStatus>(`/pipeline/status/${encodeURIComponent(traceId)}`),
  getPipelineRuns: (): Promise<PipelineRunSummary[]> =>
    request<PipelineRunSummary[]>("/pipeline/runs"),
  getAuditTrail: (traceId: string): Promise<AuditRecord[]> =>
    request<AuditRecord[]>(`/audit/${encodeURIComponent(traceId)}`),
  getLatestAudit: (): Promise<AuditRecord[]> => request<AuditRecord[]>("/audit/latest"),
  getExperiments: (): Promise<Experiment[]> => request<Experiment[]>("/experiments"),
  getModels: (): Promise<ModelVersion[]> => request<ModelVersion[]>("/models"),
  getRules: (): Promise<Rule[]> => request<Rule[]>("/guardrails/rules"),
  getApprovalQueue: (): Promise<ApprovalQueueItem[]> =>
    request<ApprovalQueueItem[]>("/guardrails/queue"),
  recordDecision: (queueId: string, decision: Decision): Promise<void> =>
    request<void, { decision: Decision; reason: string }>(
      `/guardrails/queue/${encodeURIComponent(queueId)}/decision`,
      {
        method: "PUT",
        body: { decision, reason: "UI reviewer decision" }
      }
    ),
  recordOutcome: (traceId: string, outcome: OutcomeEvent): Promise<void> =>
    request<void, OutcomeEvent>(`/outcomes/${encodeURIComponent(traceId)}`, {
      method: "POST",
      body: outcome
    })
};

interface RequestOptions<TBody> {
  method?: "GET" | "POST" | "PUT";
  body?: TBody;
}

async function request<TResponse, TBody extends object = JsonObject>(
  path: string,
  options: RequestOptions<TBody> = {}
): Promise<TResponse> {
  // Request bodies leave the browser as snake_case to match Pydantic models.
  const response = await fetch(apiUrl(path), {
    method: options.method ?? "GET",
    headers: options.body === undefined ? undefined : { "Content-Type": "application/json" },
    body: options.body === undefined ? undefined : JSON.stringify(toSnakeCase(options.body))
  });

  // Surface API validation failures as Error objects so React Query can own UI state.
  if (!response.ok) {
    throw new Error(await errorMessageFor(response));
  }
  if (response.status === 204) {
    return undefined as TResponse;
  }
  const text = await response.text();
  if (text.length === 0) {
    return undefined as TResponse;
  }
  // Responses enter the UI as camelCase so components stay idiomatic TypeScript.
  return toCamelCase(JSON.parse(text) as JsonValue) as TResponse;
}

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

/**
 * Extract a human-readable backend error message from a failed response.
 */
async function errorMessageFor(response: Response): Promise<string> {
  const text = await response.text();
  if (text.length === 0) {
    return `API request failed: ${response.status}`;
  }
  try {
    const parsed = JSON.parse(text) as JsonValue;
    if (isJsonObject(parsed) && typeof parsed.detail === "string") {
      return parsed.detail;
    }
  } catch {
    return text;
  }
  return `API request failed: ${response.status}`;
}

function toCamelCase(value: JsonValue): JsonValue {
  if (Array.isArray(value)) {
    // Recurse through arrays so nested Pydantic collections keep their shape.
    return value.map((item) => toCamelCase(item));
  }
  if (isJsonObject(value)) {
    return Object.fromEntries(
      Object.entries(value).map(([key, nested]) => [snakeToCamel(key), toCamelCase(nested)])
    );
  }
  return value;
}

function toSnakeCase(value: object): JsonValue {
  if (Array.isArray(value)) {
    // Preserve primitive array entries while normalizing nested objects.
    return value.map((item) => (typeof item === "object" && item !== null ? toSnakeCase(item) : item));
  }
  return Object.fromEntries(
    Object.entries(value).map(([key, nested]) => [
      camelToSnake(key),
      typeof nested === "object" && nested !== null ? toSnakeCase(nested) : nested
    ])
  );
}

function isJsonObject(value: JsonValue): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function snakeToCamel(value: string): string {
  return value.replace(/_([a-z0-9])/g, (_, character: string) => character.toUpperCase());
}

function camelToSnake(value: string): string {
  return value.replace(/[A-Z]/g, (character) => `_${character.toLowerCase()}`);
}
