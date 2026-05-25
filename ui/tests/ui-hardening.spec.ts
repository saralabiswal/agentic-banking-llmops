/**
 * Author: Sarala Biswal
 */
import { expect, test, type Page } from "@playwright/test";

const API_BASE = "http://localhost:8000";

test.beforeEach(async ({ page }) => {
  await installMockEventSource(page);
  await mockCommonApi(page);
});

test("pipeline summary surfaces Layer 1 ML scoring and Layer 3 LLM inference", async ({ page }) => {
  await page.goto("/?trace_id=trace_ui");

  await expect(page.getByText("Layer 1 ML Scoring")).toBeVisible();
  await expect(page.getByText("ML scoring service")).toBeVisible();
  await expect(page.getByText("Risk Score v1, Churn Probability v2")).toBeVisible();
  await expect(page.getByText("Layer 3 LLM Inference")).toBeVisible();
  await expect(page.getByText("mock / mock-risk, mock-intervention")).toBeVisible();
  await expect(page.getByText("1; primary failed")).toBeVisible();
});

test("audit replay summarizes memory retrieval and memory writes", async ({ page }) => {
  await page.goto("/audit/trace_ui");

  await expect(page.getByText("What memory was retrieved or stored?")).toBeVisible();
  await expect(page.getByText("2 long-term memories retrieved.")).toBeVisible();
  await expect(page.getByText("1 memory write(s): ENROLLED.")).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^MEMORY_RETRIEVED$/ })).toBeVisible();
  await expect(page.locator("span").filter({ hasText: /^MEMORY_STORED$/ })).toBeVisible();
});

test("evaluation can run a selected model and version with filters", async ({ page }) => {
  const reports = [evaluationReport("payment_risk_model", "7", true)];
  await mockEvaluationApi(page, reports);
  await page.goto("/evaluation");

  await page.getByTestId("evaluation-model-selector").selectOption("churn_propensity_model");
  await page.getByTestId("evaluation-version-input").fill("8");
  await page.getByTestId("run-evaluation-button").click();

  await expect(page.getByTestId("evaluation-history-row").first()).toContainText("churn_propensity_model");
  await expect(page.getByTestId("evaluation-history-row").first()).toContainText("8");
  await expect(page.getByTestId("evaluation-gate-snapshot")).toContainText("Candidate 8 vs 7");
  await expect(page.getByLabel("Status")).toHaveValue("all");
});

test("evaluation shows a targeted storage migration error", async ({ page }) => {
  await page.route(`${API_BASE}/evaluation/options`, async (route) => {
    await route.fulfill({
      json: {
        models: [
          {
            model_name: "payment_risk_model",
            label: "Payment Risk Model",
            versions: ["1"],
            default_version: "1"
          }
        ],
        storage_ok: false,
        storage_error: "relation evaluation_reports does not exist"
      }
    });
  });
  await page.route(`${API_BASE}/evaluation/history`, async (route) => {
    await route.fulfill({ status: 500, json: { detail: "relation evaluation_reports does not exist" } });
  });

  await page.goto("/evaluation");

  await expect(page.getByTestId("evaluation-storage-error")).toContainText("make migrate");
  await expect(page.getByTestId("evaluation-storage-error")).toContainText("evaluation_reports");
  await expect(page.getByTestId("run-evaluation-button")).toBeDisabled();
});

async function mockCommonApi(page: Page): Promise<void> {
  await page.route(`${API_BASE}/config`, async (route) => {
    await route.fulfill({
      json: {
        llm_backend: "mock",
        llm_mode_label: "Mock LLM",
        llm_model: "mock",
        ollama_base_url: "http://localhost:11434",
        api_key_configured: false,
        environment: "test",
        context_ttl_seconds: 300,
        source_adapter_timeout_ms: 500,
        retrieval_top_k: 5,
        hybrid_alpha: 0.7,
        experiment_confidence_threshold: 0.95
      }
    });
  });
  await page.route(`${API_BASE}/pipeline/status/trace_ui`, async (route) => {
    await route.fulfill({
      json: {
        trace_id: "trace_ui",
        session_id: "sess_ui",
        status: "completed",
        customer_id: "C002",
        scenario: "payment_risk_intervention",
        execution_result: null
      }
    });
  });
  await page.route(`${API_BASE}/pipeline/runs`, async (route) => {
    await route.fulfill({
      json: [
        {
          trace_id: "trace_ui",
          session_id: "sess_ui",
          status: "completed",
          customer_id: "C002",
          scenario: "payment_risk_intervention"
        }
      ]
    });
  });
  await page.route(`${API_BASE}/audit/trace_ui`, async (route) => {
    await route.fulfill({ json: auditRecords() });
  });
}

async function mockEvaluationApi(page: Page, reports: ReturnType<typeof evaluationReport>[]): Promise<void> {
  await page.route(`${API_BASE}/evaluation/options`, async (route) => {
    await route.fulfill({
      json: {
        models: [
          {
            model_name: "payment_risk_model",
            label: "Payment Risk Model",
            versions: ["7", "1"],
            default_version: "7"
          },
          {
            model_name: "churn_propensity_model",
            label: "Churn Propensity Model",
            versions: ["8", "1"],
            default_version: "1"
          }
        ],
        storage_ok: true,
        storage_error: null
      }
    });
  });
  await page.route(`${API_BASE}/evaluation/history`, async (route) => {
    await route.fulfill({ json: reports });
  });
  await page.route(`${API_BASE}/evaluation/run`, async (route) => {
    const body = route.request().postDataJSON() as { model_name: string; candidate_version: string };
    const report = evaluationReport(body.model_name, body.candidate_version, true);
    reports.unshift(report);
    await route.fulfill({ json: report });
  });
}

async function installMockEventSource(page: Page): Promise<void> {
  await page.addInitScript(() => {
    class MockEventSource {
      private listeners: Record<string, Array<(event: MessageEvent<string>) => void>> = {};

      constructor(url: string) {
        window.setTimeout(() => {
          if (!url.includes("/pipeline/events/")) {
            return;
          }
          this.emit("layer_completed", {
            trace_id: "trace_ui",
            layer: "L1",
            latency_ms: 42,
            output_summary: {
              sources_available: ["feature_store", "ml_scoring"],
              sources_degraded: [],
              model_versions_used: {
                risk_score: "1",
                churn_probability: "2"
              }
            }
          });
          this.emit("layer_completed", {
            trace_id: "trace_ui",
            layer: "L3",
            latency_ms: 75,
            output_summary: {
              agent_outputs: [
                {
                  agent_name: "RiskScoringAgent",
                  output: {
                    risk_level: "HIGH",
                    confidence: 0.92,
                    _inference: {
                      model_id: "mock-risk",
                      backend: "mock",
                      latency_ms: 30,
                      fallback_used: false,
                      prompt_tokens: 100,
                      completion_tokens: 40
                    }
                  },
                  latency_ms: 30
                },
                {
                  agent_name: "InterventionAgent",
                  output: {
                    intervention_type: "HARDSHIP_PLAN",
                    _inference: {
                      model_id: "mock-intervention",
                      backend: "mock",
                      latency_ms: 45,
                      fallback_used: true,
                      prompt_tokens: 90,
                      completion_tokens: 50
                    }
                  },
                  latency_ms: 45
                }
              ]
            }
          });
          this.emit("pipeline_done", {
            trace_id: "trace_ui",
            layer: "ALL",
            total_ms: 117
          });
        }, 25);
      }

      addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void {
        this.listeners[type] = [...(this.listeners[type] ?? []), listener];
      }

      close(): void {
        this.listeners = {};
      }

      private emit(type: string, payload: unknown): void {
        for (const listener of this.listeners[type] ?? []) {
          listener({ data: JSON.stringify(payload) } as MessageEvent<string>);
        }
      }
    }
    window.EventSource = MockEventSource as unknown as typeof EventSource;
  });
}

function evaluationReport(modelName: string, candidateVersion: string, passed: boolean): {
  model_name: string;
  candidate_version: string;
  champion_version: string | null;
  gates: Array<{
    gate: string;
    passed: boolean;
    metrics: Record<string, number>;
    failure_reason: string | null;
  }>;
  overall_passed: boolean;
  promotion_allowed: boolean;
  evaluated_at: string;
  trace_id: string;
} {
  return {
    model_name: modelName,
    candidate_version: candidateVersion,
    champion_version: modelName === "churn_propensity_model" ? "7" : "6",
    gates: [
      {
        gate: "benchmark",
        passed,
        metrics: { auc_roc: 0.83 },
        failure_reason: null
      },
      {
        gate: "fairness",
        passed,
        metrics: { air: 0.91 },
        failure_reason: null
      },
      {
        gate: "regression",
        passed,
        metrics: { auc_delta: 0.01 },
        failure_reason: null
      }
    ],
    overall_passed: passed,
    promotion_allowed: passed,
    evaluated_at: "2026-05-24T20:00:00Z",
    trace_id: `eval_${modelName}_${candidateVersion}`
  };
}

function auditRecords(): unknown[] {
  return [
    {
      audit_id: "aud_context",
      event_type: "CONTEXT_ASSEMBLY",
      trace_id: "trace_ui",
      session_id: "sess_ui",
      customer_id: "C002",
      timestamp: "2026-05-24T20:00:00Z",
      layer: "1",
      payload: {
        partial_context: false,
        sources_failed: []
      }
    },
    {
      audit_id: "aud_memory_retrieved",
      event_type: "MEMORY_RETRIEVED",
      trace_id: "trace_ui",
      session_id: "sess_ui",
      customer_id: "C002",
      timestamp: "2026-05-24T20:00:01Z",
      layer: "1",
      payload: {
        scenario: "payment_risk_intervention",
        memory_count: 2,
        degraded: false,
        reason: null
      }
    },
    {
      audit_id: "aud_memory_stored",
      event_type: "MEMORY_STORED",
      trace_id: "trace_ui",
      session_id: "sess_ui",
      customer_id: "C002",
      timestamp: "2026-05-24T20:00:06Z",
      layer: "6",
      payload: {
        memory_type: "outcome",
        outcome_signal: "ENROLLED"
      }
    }
  ];
}
