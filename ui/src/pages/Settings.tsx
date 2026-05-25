/**
 * Author: Sarala Biswal
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, KeyRound, Loader2, ServerCog, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { ConfigResponse, LLMBackendRequest } from "../api/types";

const fallbackOllamaModels = ["llama3.2", "llama3.1", "llama3", "mistral", "phi3.5"];
const apiModels = ["claude-sonnet-4-20250514", "gpt-4o"];

/**
 * Renders runtime LLM configuration controls and read-only platform settings.
 */
export default function Settings(): JSX.Element {
  const queryClient = useQueryClient();
  const config = useQuery({
    queryKey: ["config"],
    queryFn: api.getConfig,
    retry: false
  });
  const [backend, setBackend] = useState<LLMBackendRequest["llmBackend"]>("ollama");
  const [model, setModel] = useState("llama3.2");
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState("http://localhost:11434");
  const [apiKey, setApiKey] = useState("");
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);
  const [connectionOk, setConnectionOk] = useState<boolean | null>(null);
  const ollamaModels = useQuery({
    queryKey: ["ollama-models", ollamaBaseUrl],
    queryFn: () => api.getOllamaModels(ollamaBaseUrl),
    enabled: backend === "ollama",
    retry: false,
    staleTime: 5000
  });
  const detectedOllamaModels = ollamaModels.data?.models ?? [];
  const ollamaModelOptions =
    detectedOllamaModels.length > 0 ? detectedOllamaModels : fallbackOllamaModels;
  const detectedOllamaModelsKey = detectedOllamaModels.join("|");

  useEffect(() => {
    if (config.data === undefined) {
      return;
    }
    setBackend(config.data.llmBackend);
    setModel(config.data.llmModel);
    setOllamaBaseUrl(config.data.ollamaBaseUrl);
  }, [config.data]);

  useEffect(() => {
    if (backend !== "ollama" || detectedOllamaModels.length === 0) {
      return;
    }
    if (!detectedOllamaModels.includes(model)) {
      setModel(detectedOllamaModels[0]);
      setConnectionOk(null);
      setConnectionMessage(null);
    }
  }, [backend, detectedOllamaModelsKey, model]);

  const updateMutation = useMutation({
    mutationFn: api.updateLLMBackend,
    onSuccess: async () => {
      setApiKey("");
      setConnectionOk(true);
      setConnectionMessage("Runtime LLM backend updated for this server process.");
      await queryClient.invalidateQueries({ queryKey: ["config"] });
    },
    onError: (error: Error) => {
      setConnectionOk(false);
      setConnectionMessage(error.message);
    }
  });

  const testMutation = useMutation({
    mutationFn: api.testLLMBackend,
    onSuccess: (result) => {
      setConnectionOk(result.ok);
      setConnectionMessage(result.message);
    },
    onError: (error: Error) => {
      setConnectionOk(false);
      setConnectionMessage(error.message);
    }
  });

  function requestBody(): LLMBackendRequest {
    return {
      llmBackend: backend,
      llmModel: modelForBackend(backend, model, ollamaModelOptions),
      ollamaBaseUrl,
      ...(apiKey.trim() ? { apiKey: apiKey.trim() } : {})
    };
  }

  function chooseBackend(nextBackend: LLMBackendRequest["llmBackend"]): void {
    setBackend(nextBackend);
    setConnectionMessage(null);
    setConnectionOk(null);
    if (nextBackend === "mock") {
      setModel("mock");
    }
    if (nextBackend === "ollama" && !ollamaModelOptions.includes(model)) {
      setModel(ollamaModelOptions[0] ?? "llama3.2");
    }
    if (nextBackend === "api" && !apiModels.includes(model)) {
      setModel("claude-sonnet-4-20250514");
    }
  }

  return (
    <section className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-white">Settings</h2>
        <p className="mt-1 text-sm text-slate-400">
          Runtime-only settings for this server process. No file writes, no restarts, no browser key storage.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
        <section className="rounded-md border border-slate-800 bg-slate-900 p-5">
          <div className="mb-4 flex items-center gap-2">
            <ServerCog className="h-5 w-5 text-emerald-300" />
            <h3 className="text-base font-semibold text-white">Runtime LLM Backend</h3>
          </div>

          <div className="space-y-3">
            <BackendOption
              checked={backend === "mock"}
              description="No API key, deterministic, runs anywhere."
              label="Mock LLM"
              onChange={() => chooseBackend("mock")}
            />
            <BackendOption
              checked={backend === "ollama"}
              description="Local model inference with no cloud cost."
              label="Ollama"
              onChange={() => chooseBackend("ollama")}
            />
            {backend === "ollama" ? (
              <div className="ml-7 grid gap-3 rounded-md border border-slate-800 bg-slate-950 p-3 md:grid-cols-2">
                <SelectField
                  label="Model"
                  onChange={setModel}
                  options={ollamaModelOptions}
                  value={modelForBackend(backend, model, ollamaModelOptions)}
                />
                <TextField label="Base URL" onChange={setOllamaBaseUrl} value={ollamaBaseUrl} />
                <OllamaModelStatus
                  isLoading={ollamaModels.isFetching}
                  message={ollamaModels.data?.message ?? null}
                  ok={ollamaModels.data?.ok ?? null}
                />
              </div>
            ) : null}
            <BackendOption
              checked={backend === "api"}
              description="Claude or OpenAI through LiteLLM."
              label="API"
              onChange={() => chooseBackend("api")}
            />
            {backend === "api" ? (
              <div className="ml-7 grid gap-3 rounded-md border border-slate-800 bg-slate-950 p-3 md:grid-cols-2">
                <SelectField
                  label="Model"
                  onChange={setModel}
                  options={apiModels}
                  value={modelForBackend(backend, model, ollamaModelOptions)}
                />
                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                    API Key
                  </span>
                  <input
                    autoComplete="off"
                    className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
                    onChange={(event) => setApiKey(event.target.value)}
                    placeholder={config.data?.apiKeyConfigured ? "Configured for this process" : "Paste key for test/apply"}
                    type="password"
                    value={apiKey}
                  />
                </label>
              </div>
            ) : null}
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              className="inline-flex h-10 items-center gap-2 rounded-md border border-slate-700 px-3 text-sm font-semibold text-slate-200 hover:border-slate-500 disabled:cursor-not-allowed disabled:text-slate-600"
              disabled={testMutation.isPending}
              onClick={() => testMutation.mutate(requestBody())}
              type="button"
            >
              {testMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
              Test connection
            </button>
            <button
              className="inline-flex h-10 items-center rounded-md bg-emerald-500 px-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              disabled={updateMutation.isPending}
              onClick={() => updateMutation.mutate(requestBody())}
              type="button"
            >
              Apply runtime setting
            </button>
            {connectionMessage !== null ? (
              <StatusMessage ok={connectionOk} message={connectionMessage} />
            ) : null}
          </div>
        </section>

        <section className="rounded-md border border-slate-800 bg-slate-900 p-5">
          <h3 className="text-base font-semibold text-white">Platform Settings</h3>
          <p className="mt-1 text-sm text-slate-400">Read-only values from the server.</p>
          <div className="mt-4 space-y-2">
            <ReadOnlyRow label="Context TTL" value={`${config.data?.contextTtlSeconds ?? 0}s`} />
            <ReadOnlyRow label="Source timeout" value={`${config.data?.sourceAdapterTimeoutMs ?? 0}ms`} />
            <ReadOnlyRow label="Retrieval top-k" value={String(config.data?.retrievalTopK ?? 0)} />
            <ReadOnlyRow label="Hybrid alpha" value={String(config.data?.hybridAlpha ?? 0)} />
            <ReadOnlyRow label="Experiment confidence" value={String(config.data?.experimentConfidenceThreshold ?? 0)} />
            <ReadOnlyRow label="Environment" value={config.data?.environment ?? "development"} />
            <ReadOnlyRow label="Active LLM" value={activeLlmLabel(config.data)} />
          </div>
        </section>
      </div>
    </section>
  );
}

function BackendOption({
  checked,
  description,
  label,
  onChange
}: {
  checked: boolean;
  description: string;
  label: string;
  onChange: () => void;
}): JSX.Element {
  return (
    <label className="flex cursor-pointer gap-3 rounded-md border border-slate-800 bg-slate-950 p-3 hover:border-slate-600">
      <input checked={checked} className="mt-1 h-4 w-4 accent-emerald-500" onChange={onChange} type="radio" />
      <span>
        <span className="block text-sm font-semibold text-slate-100">{label}</span>
        <span className="mt-1 block text-sm text-slate-400">{description}</span>
      </span>
    </label>
  );
}

function SelectField({
  label,
  onChange,
  options,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  options: string[];
  value: string;
}): JSX.Element {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </label>
  );
}

function TextField({
  label,
  onChange,
  value
}: {
  label: string;
  onChange: (value: string) => void;
  value: string;
}): JSX.Element {
  return (
    <label className="block">
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      />
    </label>
  );
}

function StatusMessage({ message, ok }: { message: string; ok: boolean | null }): JSX.Element {
  const success = ok === true;
  return (
    <span
      className={[
        "inline-flex min-h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold",
        success
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
          : "border-red-500/30 bg-red-500/10 text-red-200"
      ].join(" ")}
    >
      {success ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
      {message}
    </span>
  );
}

function OllamaModelStatus({
  isLoading,
  message,
  ok
}: {
  isLoading: boolean;
  message: string | null;
  ok: boolean | null;
}): JSX.Element {
  const text = isLoading ? "Checking installed Ollama models..." : message ?? "Ollama models not checked.";
  const color = ok === false ? "text-amber-200" : "text-slate-400";
  return <p className={`md:col-span-2 text-xs ${color}`}>{text}</p>;
}

function ReadOnlyRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-slate-800 bg-slate-950 px-3 py-2 text-sm">
      <span className="text-slate-500">{label}</span>
      <span className="font-semibold text-slate-100">{value}</span>
    </div>
  );
}

function modelForBackend(
  backend: LLMBackendRequest["llmBackend"],
  model: string,
  ollamaModelOptions: string[]
): string {
  if (backend === "mock") {
    return "mock";
  }
  if (backend === "ollama" && !ollamaModelOptions.includes(model)) {
    return ollamaModelOptions[0] ?? "llama3.2";
  }
  if (backend === "api" && !apiModels.includes(model)) {
    return "claude-sonnet-4-20250514";
  }
  return model;
}

function activeLlmLabel(config: ConfigResponse | undefined): string {
  if (config === undefined) {
    return "Loading";
  }
  if (config.llmBackend === "mock") {
    return config.llmModeLabel;
  }
  return `${config.llmModeLabel} (${config.llmModel})`;
}
