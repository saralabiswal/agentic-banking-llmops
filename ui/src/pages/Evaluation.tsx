/**
 * Author: Sarala Biswal
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Filter, Play, RefreshCw, XCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { EvaluationModelOption, EvaluationReport } from "../api/types";

type StatusFilter = "all" | "passed" | "failed";

export default function Evaluation(): JSX.Element {
  const queryClient = useQueryClient();
  const options = useQuery({
    queryKey: ["evaluation-options"],
    queryFn: api.getEvaluationOptions,
    retry: false
  });
  const history = useQuery({
    queryKey: ["evaluation-history"],
    queryFn: () => api.getEvaluationHistory(),
    retry: false
  });
  const [modelName, setModelName] = useState("");
  const [candidateVersion, setCandidateVersion] = useState("");
  const [filterModel, setFilterModel] = useState("all");
  const [filterVersion, setFilterVersion] = useState("all");
  const [filterStatus, setFilterStatus] = useState<StatusFilter>("all");
  const modelOptions = options.data?.models ?? [];
  const selectedModel = modelOptions.find((model) => model.modelName === modelName) ?? modelOptions[0];
  const knownVersions = selectedModel?.versions ?? [];
  const historyRows = history.data ?? [];
  const filteredRows = useMemo(
    () => filterReports(historyRows, filterModel, filterVersion, filterStatus),
    [filterModel, filterStatus, filterVersion, historyRows]
  );
  const versionFilterOptions = useMemo(
    () => ["all", ...uniqueStrings(historyRows.map((report) => report.candidateVersion))],
    [historyRows]
  );
  const latestVisibleReport = filteredRows[0] ?? historyRows[0] ?? null;
  const storageError = options.data?.storageOk === false
    ? options.data.storageError ?? "Evaluation storage is unavailable."
    : errorMessage(history.error) ?? errorMessage(options.error);
  const runEvaluation = useMutation({
    mutationFn: api.runEvaluation,
    onSuccess: (report) => {
      setFilterModel(report.modelName);
      setFilterVersion(report.candidateVersion);
      setFilterStatus("all");
      void queryClient.invalidateQueries({ queryKey: ["evaluation-history"] });
      void queryClient.invalidateQueries({ queryKey: ["evaluation-options"] });
    }
  });
  const canRun =
    modelName.length > 0
    && candidateVersion.trim().length > 0
    && !runEvaluation.isPending
    && options.data?.storageOk !== false;

  useEffect(() => {
    if (modelName.length > 0 || modelOptions.length === 0) {
      return;
    }
    const first = modelOptions[0];
    setModelName(first.modelName);
    setCandidateVersion(first.defaultVersion);
  }, [modelName, modelOptions]);

  function chooseModel(nextModelName: string): void {
    setModelName(nextModelName);
    const nextModel = modelOptions.find((model) => model.modelName === nextModelName);
    setCandidateVersion(nextModel?.defaultVersion ?? "1");
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <div className="rounded-md border border-slate-800 bg-slate-900 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-100">Offline Evaluation</h2>
            <p className="mt-1 text-sm text-slate-400">
              Benchmark, fairness, and regression gates before model promotion.
            </p>
          </div>
          <div className="grid w-full gap-3 lg:w-auto lg:grid-cols-[240px_150px_auto] lg:items-end">
            <label>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Model
              </span>
              <select
                className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100 disabled:cursor-not-allowed disabled:text-slate-600"
                data-testid="evaluation-model-selector"
                disabled={modelOptions.length === 0}
                onChange={(event) => chooseModel(event.target.value)}
                value={modelName}
              >
                {modelOptions.length === 0 ? (
                  <option value="">{options.isLoading ? "Loading models..." : "No models"}</option>
                ) : (
                  modelOptions.map((option) => (
                    <option key={option.modelName} value={option.modelName}>
                      {option.label}
                    </option>
                  ))
                )}
              </select>
            </label>
            <label>
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Version
              </span>
              <input
                className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
                data-testid="evaluation-version-input"
                list="evaluation-version-options"
                onChange={(event) => setCandidateVersion(event.target.value)}
                placeholder={selectedModel?.defaultVersion ?? "1"}
                value={candidateVersion}
              />
              <datalist id="evaluation-version-options">
                {knownVersions.map((version) => (
                  <option key={version} value={version} />
                ))}
              </datalist>
            </label>
            <button
              type="button"
              onClick={() =>
                runEvaluation.mutate({
                  modelName,
                  candidateVersion: candidateVersion.trim()
                })
              }
              className="inline-flex h-10 items-center justify-center gap-2 rounded-md bg-emerald-400 px-4 text-sm font-semibold text-slate-950 transition hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-60"
              data-testid="run-evaluation-button"
              disabled={!canRun}
            >
              <Play className="h-4 w-4" />
              {runEvaluation.isPending ? "Running" : "Run Evaluation"}
            </button>
          </div>
        </div>
        {storageError !== null ? <EvaluationStorageError message={storageError} /> : null}
        {runEvaluation.error !== null ? (
          <EvaluationStorageError message={errorMessage(runEvaluation.error) ?? "Evaluation run failed."} />
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="space-y-4">
          <div className="rounded-md border border-slate-800 bg-slate-900 p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-blue-300" />
                <h3 className="text-sm font-semibold text-white">Evaluation History</h3>
              </div>
              <button
                aria-label="Refresh evaluation history"
                className="inline-flex h-8 items-center gap-2 rounded-md border border-slate-700 px-2 text-xs font-semibold text-slate-200 hover:border-slate-500 disabled:cursor-not-allowed disabled:text-slate-600"
                disabled={history.isFetching}
                onClick={() => void history.refetch()}
                type="button"
              >
                <RefreshCw className={["h-3.5 w-3.5", history.isFetching ? "animate-spin" : ""].join(" ")} />
                Refresh
              </button>
            </div>
            <div className="mb-4 grid gap-3 md:grid-cols-3">
              <FilterSelect
                label="Model"
                onChange={setFilterModel}
                options={[
                  { label: "All models", value: "all" },
                  ...modelOptions.map((option) => ({
                    label: option.label,
                    value: option.modelName
                  }))
                ]}
                value={filterModel}
              />
              <FilterSelect
                label="Version"
                onChange={setFilterVersion}
                options={versionFilterOptions.map((version) => ({
                  label: version === "all" ? "All versions" : version,
                  value: version
                }))}
                value={filterVersion}
              />
              <FilterSelect
                label="Status"
                onChange={(value) => setFilterStatus(value as StatusFilter)}
                options={[
                  { label: "All results", value: "all" },
                  { label: "Passed", value: "passed" },
                  { label: "Failed", value: "failed" }
                ]}
                value={filterStatus}
              />
            </div>
            <EvaluationTable reports={filteredRows} loading={history.isLoading} />
          </div>
        </section>

        <aside className="rounded-md border border-slate-800 bg-slate-900 p-4">
          <h3 className="mb-4 text-sm font-semibold text-white">Gate Snapshot</h3>
          {latestVisibleReport === null ? (
            <div className="rounded-md border border-slate-800 bg-slate-950 p-4 text-sm text-slate-500">
              Run an evaluation to populate gate metrics.
            </div>
          ) : (
            <GateSnapshot report={latestVisibleReport} modelOptions={modelOptions} />
          )}
        </aside>
      </div>
    </div>
  );
}

function EvaluationStorageError({ message }: { message: string }): JSX.Element {
  return (
    <div
      className="mt-4 rounded-md border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-100"
      data-testid="evaluation-storage-error"
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-300" />
        <div>
          <div className="font-semibold">Evaluation storage needs attention.</div>
          <div className="mt-1 text-amber-100/80">
            Run <span className="font-mono">make migrate</span> if the evaluation tables are missing. Details: {message}
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterSelect({
  label,
  options,
  value,
  onChange
}: {
  label: string;
  options: { label: string; value: string }[];
  value: string;
  onChange: (value: string) => void;
}): JSX.Element {
  return (
    <label>
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </span>
      <select
        className="mt-2 h-10 w-full rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-slate-100"
        onChange={(event) => onChange(event.target.value)}
        value={value}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function EvaluationTable({
  reports,
  loading
}: {
  reports: EvaluationReport[];
  loading: boolean;
}): JSX.Element {
  return (
    <div className="overflow-hidden rounded-md border border-slate-800">
      <table className="min-w-full divide-y divide-slate-800 text-sm">
        <thead className="bg-slate-950 text-left text-xs uppercase text-slate-400">
          <tr>
            <th className="px-4 py-3">Model</th>
            <th className="px-4 py-3">Candidate</th>
            <th className="px-4 py-3">Champion</th>
            <th className="px-4 py-3">Overall</th>
            <th className="px-4 py-3">Gates</th>
            <th className="px-4 py-3">Evaluated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800 bg-slate-950">
          {reports.map((report) => (
            <EvaluationRow key={report.traceId} report={report} />
          ))}
          {reports.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-slate-500" colSpan={6}>
                {loading ? "Loading evaluation runs..." : "No evaluation runs match the current filters."}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function EvaluationRow({ report }: { report: EvaluationReport }): JSX.Element {
  const OverallIcon = report.overallPassed ? CheckCircle2 : XCircle;
  return (
    <tr data-testid="evaluation-history-row">
      <td className="px-4 py-3 font-medium text-slate-100">{report.modelName}</td>
      <td className="px-4 py-3 text-slate-300">{report.candidateVersion}</td>
      <td className="px-4 py-3 text-slate-400">{report.championVersion ?? "none"}</td>
      <td className="px-4 py-3">
        <span
          className={[
            "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold",
            report.overallPassed
              ? "bg-emerald-400/10 text-emerald-300"
              : "bg-rose-400/10 text-rose-300"
          ].join(" ")}
        >
          <OverallIcon className="h-3.5 w-3.5" />
          {report.overallPassed ? "PASSED" : "FAILED"}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-2">
          {report.gates.map((gate) => (
            <span
              key={gate.gate}
              className={[
                "rounded-md border px-2 py-1 text-xs font-semibold",
                gate.passed
                  ? "border-emerald-400/30 text-emerald-300"
                  : "border-rose-400/30 text-rose-300"
              ].join(" ")}
            >
              {gate.gate}: {formatGateMetrics(gate.metrics)}
            </span>
          ))}
        </div>
      </td>
      <td className="px-4 py-3 text-slate-400">
        {new Date(report.evaluatedAt).toLocaleString()}
      </td>
    </tr>
  );
}

function GateSnapshot({
  report,
  modelOptions
}: {
  report: EvaluationReport;
  modelOptions: EvaluationModelOption[];
}): JSX.Element {
  // The snapshot translates the latest durable report into a compact promotion-readiness view.
  const label = modelOptions.find((model) => model.modelName === report.modelName)?.label ?? report.modelName;
  return (
    <div className="space-y-4" data-testid="evaluation-gate-snapshot">
      <div className="rounded-md border border-slate-800 bg-slate-950 p-3">
        <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Candidate vs Champion
        </div>
        <div className="mt-2 text-sm font-semibold text-slate-100">{label}</div>
        <div className="mt-1 text-xs text-slate-400">
          Candidate {report.candidateVersion} vs {report.championVersion ?? "no champion"}
        </div>
      </div>
      <div className="space-y-3">
        {report.gates.map((gate) => {
          const metric = firstMetric(gate.metrics);
          const width = `${Math.max(4, Math.min(100, metric.value * 100))}%`;
          return (
            <div className="rounded-md border border-slate-800 bg-slate-950 p-3" key={gate.gate}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                <span className="font-semibold capitalize text-slate-200">{gate.gate}</span>
                <span className={gate.passed ? "text-emerald-300" : "text-rose-300"}>
                  {gate.passed ? "PASS" : "FAIL"}
                </span>
              </div>
              <div className="h-2 rounded-sm bg-slate-800">
                <div
                  className={[
                    "h-2 rounded-sm",
                    gate.passed ? "bg-emerald-400" : "bg-rose-400"
                  ].join(" ")}
                  style={{ width }}
                />
              </div>
              <div className="mt-2 text-xs text-slate-400">
                {formatMetricName(metric.name)} {metric.value.toFixed(3)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function filterReports(
  reports: EvaluationReport[],
  model: string,
  version: string,
  status: StatusFilter
): EvaluationReport[] {
  // Filters are applied client-side because the history payload is intentionally small.
  return reports.filter((report) => {
    const modelMatches = model === "all" || report.modelName === model;
    const versionMatches = version === "all" || report.candidateVersion === version;
    const statusMatches =
      status === "all"
      || (status === "passed" && report.overallPassed)
      || (status === "failed" && !report.overallPassed);
    return modelMatches && versionMatches && statusMatches;
  });
}

function formatGateMetrics(metrics: Record<string, number>): string {
  const metric = firstMetric(metrics);
  return `${metric.name} ${metric.value.toFixed(3)}`;
}

function firstMetric(metrics: Record<string, number>): { name: string; value: number } {
  // Gate cards show the lead metric, while the table still lists all metric text.
  const [name, value] = Object.entries(metrics)[0] ?? ["score", 0];
  return { name, value: Number(value) };
}

function formatMetricName(value: string): string {
  return value
    .split("_")
    .map((word) => `${word.charAt(0).toUpperCase()}${word.slice(1)}`)
    .join(" ");
}

function uniqueStrings(values: string[]): string[] {
  return [...new Set(values)];
}

function errorMessage(error: unknown): string | null {
  return error instanceof Error ? error.message : null;
}
