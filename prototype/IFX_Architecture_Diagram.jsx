import { useState } from "react";

const FONT = "'IBM Plex Mono', monospace";
const SANS = "'IBM Plex Sans', sans-serif";

const C = {
  bg: "#04060a",
  panel: "#080c12",
  card: "#0c1118",
  border: "#1a2234",
  borderBright: "#243050",
  accent: "#4f8fff",
  accentDim: "rgba(79,143,255,0.12)",
  accentGlow: "rgba(79,143,255,0.25)",
  green: "#3dd68c",
  greenDim: "rgba(61,214,140,0.12)",
  red: "#ff5f5f",
  redDim: "rgba(255,95,95,0.12)",
  yellow: "#f5c842",
  yellowDim: "rgba(245,200,66,0.12)",
  purple: "#b57bff",
  purpleDim: "rgba(181,123,255,0.12)",
  cyan: "#3ecfcf",
  cyanDim: "rgba(62,207,207,0.12)",
  orange: "#ff8c42",
  orangeDim: "rgba(255,140,66,0.12)",
  text: "#d8e4f0",
  textMid: "#7a8fa8",
  textDim: "#3d4f63",
};

const LAYERS = [
  {
    id: "l1", num: "01", label: "Context Assembly",
    sub: "Parallel fetch · Schema norm · Feature store merge · TTL Redis store",
    color: C.accent, dim: C.accentDim,
    tech: ["Redis / ElastiCache", "DynamoDB Audit", "SageMaker Feature Store"],
    latency: "167ms",
    produces: "UnifiedCustomerProfile",
    marcus: "Card util 0.76, checking $312, 2 missed pmts · CRM DEGRADED",
  },
  {
    id: "l2", num: "02", label: "Vector Search",
    sub: "Dynamic query · Hybrid ANN+BM25 · Cross-encoder reranking",
    color: C.purple, dim: C.purpleDim,
    tech: ["Pinecone / OpenSearch", "text-embedding-3-small", "cross-encoder"],
    latency: "55ms",
    produces: "Top-3 Policy Chunks",
    marcus: "KB-HARD-001 (0.961) · KB-PAY-007 (0.934) · KB-COMP-003 (0.918)",
  },
  {
    id: "l3", num: "03", label: "Multi-Agent Orchestration",
    sub: "Hub-and-spoke routing · Tool auth · Schema validation · Failure handling",
    color: C.green, dim: C.greenDim,
    tech: ["ECS / EKS", "Amazon Bedrock", "SQS (HumanReview)"],
    latency: "6,072ms",
    produces: "InterventionProposal",
    marcus: "RiskScoringAgent → CRITICAL · InterventionAgent → Hardship offer",
  },
  {
    id: "l4", num: "04", label: "Guardrails & Policy",
    sub: "Regulatory · Business policy · Responsible AI · Rule engine · Approval queue",
    color: C.red, dim: C.redDim,
    tech: ["DynamoDB Rule Store", "SQS Approval Queue", "Step Functions"],
    latency: "88ms",
    produces: "Authorized Actions",
    marcus: "ACT-001 APPROVED (8/8) · ACT-002 FLAGGED (2 flags, 4hr SLA queue)",
  },
  {
    id: "l5", num: "05", label: "A/B & Model Governance",
    sub: "Hash-based variant selection · Drift detection · Champion/Challenger",
    color: C.yellow, dim: C.yellowDim,
    tech: ["SageMaker Model Monitor", "SageMaker Pipelines", "DynamoDB Experiments"],
    latency: "5ms",
    produces: "Winning Variant",
    marcus: "exp_payment_msg_v3 → Variant A (soft framing, 0.9998 confidence)",
  },
  {
    id: "l6", num: "06", label: "SDK Surface & Execution",
    sub: "Blueprint catalog · Channel adapters · Outcome capture · Feedback loop",
    color: C.cyan, dim: C.cyanDim,
    tech: ["FCM / APNS", "Amazon SNS / Pinpoint", "EventBridge"],
    latency: "57ms",
    produces: "Delivered Action + Tracking",
    marcus: "Push DELIVERED to device · outcome_tracking_id issued · ACT-002 queued",
  },
];

const CROSS = [
  {
    label: "Observability & Audit Trail",
    color: C.orange,
    items: [
      "CloudWatch SLOs per layer",
      "AWS X-Ray distributed tracing",
      "trace_id threads all 6 layers",
      "DynamoDB audit (90d hot)",
      "S3 Object Lock (7yr, COMPLIANCE mode)",
      "Athena regulatory replay",
    ],
  },
  {
    label: "MLOps & Drift Detection",
    color: C.purple,
    items: [
      "Feature store (single source of truth)",
      "3-type drift: feature · prediction · performance",
      "Signal-based retraining triggers",
      "Champion/Challenger (5% traffic)",
      "4-gate evaluation (accuracy, fairness, perf, regression)",
      "Model Card per version",
    ],
  },
];

const TIMELINE = [
  { t: "T+0ms",      layer: "L1", event: "Context Assembly starts. 4 adapters fire in parallel." },
  { t: "T+150ms",    layer: "L1", event: "CRM timeout. Marked degraded. Profile assembled anyway." },
  { t: "T+167ms",    layer: "L1", event: "UnifiedCustomerProfile written to Redis TTL store." },
  { t: "T+222ms",    layer: "L2", event: "Hybrid ANN+BM25 retrieves KB-HARD-001, KB-PAY-007, KB-COMP-003." },
  { t: "T+223ms",    layer: "L3", event: "RiskScoringAgent invoked. 2 tool calls. LLM reasoning begins." },
  { t: "T+2,847ms",  layer: "L3", event: "RiskScoringAgent returns CRITICAL risk. Schema validated." },
  { t: "T+2,848ms",  layer: "L3", event: "Branch: CRITICAL → InterventionAgent routed." },
  { t: "T+6,291ms",  layer: "L3", event: "InterventionAgent returns hardship enrollment proposal." },
  { t: "T+6,340ms",  layer: "L4", event: "ACT-001 (push): 8/8 checks APPROVED." },
  { t: "T+6,381ms",  layer: "L4", event: "ACT-002 (case): 2 flags → approval queue. 4hr SLA." },
  { t: "T+6,387ms",  layer: "L5", event: "Variant A selected (hash+leader, confidence 0.9998)." },
  { t: "T+6,441ms",  layer: "L6", event: "Push DELIVERED to Marcus Webb's device." },
  { t: "T+10:48",    layer: "L6", event: "Customer opens push. Outcome captured → A/B + governance." },
  { t: "T+10:51",    layer: "L6", event: "Customer ENROLLED in hardship program. Loop closes." },
];

const LAYER_COLORS = {
  L1: C.accent, L2: C.purple, L3: C.green,
  L4: C.red, L5: C.yellow, L6: C.cyan,
};

function Tag({ label, color }) {
  return (
    <span style={{
      fontFamily: FONT, fontSize: 9, fontWeight: 700,
      letterSpacing: "0.1em", textTransform: "uppercase",
      color, border: `1px solid ${color}`,
      background: color + "18",
      borderRadius: 3, padding: "1px 6px",
    }}>{label}</span>
  );
}

function LayerCard({ layer, active, onClick }) {
  const isActive = active === layer.id;
  return (
    <div
      onClick={() => onClick(isActive ? null : layer.id)}
      style={{
        cursor: "pointer",
        background: isActive ? layer.dim : C.card,
        border: `1px solid ${isActive ? layer.color : C.border}`,
        borderRadius: 8,
        padding: "14px 16px",
        transition: "all 0.2s",
        boxShadow: isActive ? `0 0 20px ${layer.color}30` : "none",
        position: "relative",
        overflow: "hidden",
      }}
    >
      {/* Number watermark */}
      <div style={{
        position: "absolute", right: 10, top: 6,
        fontFamily: FONT, fontSize: 32, fontWeight: 700,
        color: layer.color + "18", lineHeight: 1, userSelect: "none",
      }}>{layer.num}</div>

      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: layer.color, flexShrink: 0 }} />
        <span style={{ fontFamily: SANS, fontWeight: 700, fontSize: 13, color: C.text }}>{layer.label}</span>
        <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 10, color: layer.color }}>{layer.latency}</span>
      </div>

      <div style={{ fontFamily: FONT, fontSize: 10, color: C.textMid, lineHeight: 1.6, marginBottom: 8 }}>
        {layer.sub}
      </div>

      {isActive && (
        <div style={{ borderTop: `1px solid ${layer.color}30`, paddingTop: 10, marginTop: 4 }}>
          <div style={{ marginBottom: 6 }}>
            <span style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.1em" }}>PRODUCES → </span>
            <span style={{ fontFamily: FONT, fontSize: 10, color: layer.color }}>{layer.produces}</span>
          </div>
          <div style={{ marginBottom: 8 }}>
            <div style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.1em", marginBottom: 3 }}>MARCUS WEBB EXAMPLE</div>
            <div style={{ fontFamily: FONT, fontSize: 10, color: C.textMid, lineHeight: 1.6 }}>{layer.marcus}</div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
            {layer.tech.map(t => <Tag key={t} label={t} color={layer.color} />)}
          </div>
        </div>
      )}
    </div>
  );
}

export default function BankingPlatformDiagram() {
  const [active, setActive] = useState(null);
  const [tab, setTab] = useState("architecture");

  return (
    <div style={{
      background: C.bg, minHeight: "100vh",
      fontFamily: SANS, color: C.text,
      padding: "28px 24px",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: ${C.panel}; }
        ::-webkit-scrollbar-thumb { background: ${C.borderBright}; border-radius: 2px; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
        @keyframes fadein { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
      `}</style>

      {/* HEADER */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
          <div style={{ display: "flex", gap: 5 }}>
            {[C.green, C.yellow, C.red].map((c, i) => (
              <div key={i} style={{ width: 8, height: 8, borderRadius: "50%", background: c }} />
            ))}
          </div>
          <span style={{ fontFamily: FONT, fontSize: 10, color: C.textDim, letterSpacing: "0.15em" }}>
            BANKING AGENTIC AI PLATFORM · ARCHITECTURE v0.8 · PRODUCTION REFERENCE
          </span>
        </div>
        <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", color: C.text, marginBottom: 4 }}>
          Banking Agentic AI Platform
        </h1>
        <p style={{ fontFamily: FONT, fontSize: 11, color: C.textMid }}>
          Agentic AI Platform · 6 Layers · 2 Cross-Cutting Concerns · Marcus Webb end-to-end · 6,444ms
        </p>
      </div>

      {/* TABS */}
      <div style={{ display: "flex", gap: 2, marginBottom: 24 }}>
        {["architecture", "data flow", "tech stack"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            background: tab === t ? C.accent : C.card,
            color: tab === t ? "#fff" : C.textMid,
            border: `1px solid ${tab === t ? C.accent : C.border}`,
            borderRadius: 6, padding: "7px 16px",
            fontFamily: FONT, fontSize: 11, fontWeight: 600,
            cursor: "pointer", textTransform: "uppercase", letterSpacing: "0.08em",
          }}>{t}</button>
        ))}
      </div>

      {/* ── ARCHITECTURE TAB ── */}
      {tab === "architecture" && (
        <div style={{ animation: "fadein 0.3s ease" }}>

          {/* TRIGGER */}
          <div style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: "10px 16px",
            display: "flex", alignItems: "center", gap: 12, marginBottom: 12,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green, animation: "pulse 2s infinite" }} />
            <span style={{ fontFamily: FONT, fontSize: 11, color: C.textMid }}>INBOUND TRIGGER</span>
            <span style={{ fontFamily: FONT, fontSize: 10, color: C.textDim }}>payment_risk_scheduler · customer_event · API call</span>
            <span style={{ marginLeft: "auto", fontFamily: FONT, fontSize: 10, color: C.green }}>customer_id + session_id + scenario</span>
          </div>

          {/* CONNECTOR */}
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 4 }}>
            <div style={{ width: 1, height: 12, background: C.border }} />
          </div>

          {/* LAYERS */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 8 }}>
            {LAYERS.map((layer, i) => (
              <div key={layer.id}>
                <LayerCard layer={layer} active={active} onClick={setActive} />
                {/* Connector between cards in same column */}
                {i < 3 && (
                  <div style={{ display: "flex", justifyContent: "center", margin: "4px 0" }}>
                    <div style={{ fontFamily: FONT, fontSize: 10, color: C.textDim }}>↓</div>
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* FLOW ARROWS between rows */}
          <div style={{ display: "flex", justifyContent: "center", margin: "6px 0" }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {LAYERS.slice(0,3).map((l, i) => (
                <span key={i} style={{ fontFamily: FONT, fontSize: 9, color: l.color + "80" }}>
                  {l.produces} →
                </span>
              ))}
            </div>
          </div>

          {/* CROSS-CUTTING */}
          <div style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: 16, marginBottom: 12,
          }}>
            <div style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.12em", marginBottom: 12 }}>
              CROSS-CUTTING CONCERNS — RUN ALONGSIDE EVERY LAYER
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
              {CROSS.map(c => (
                <div key={c.label} style={{
                  background: C.bg, border: `1px solid ${c.color}30`,
                  borderRadius: 6, padding: "10px 12px",
                  borderLeft: `2px solid ${c.color}`,
                }}>
                  <div style={{ fontFamily: SANS, fontWeight: 600, fontSize: 12, color: c.color, marginBottom: 8 }}>{c.label}</div>
                  {c.items.map(item => (
                    <div key={item} style={{ display: "flex", gap: 6, alignItems: "flex-start", marginBottom: 4 }}>
                      <span style={{ color: c.color, fontSize: 10, marginTop: 1, flexShrink: 0 }}>·</span>
                      <span style={{ fontFamily: FONT, fontSize: 10, color: C.textMid, lineHeight: 1.5 }}>{item}</span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>

          {/* OUTCOMES */}
          <div style={{
            background: C.greenDim, border: `1px solid ${C.green}40`,
            borderRadius: 8, padding: "10px 16px",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: C.green }} />
            <span style={{ fontFamily: FONT, fontSize: 11, color: C.green }}>OUTCOME CAPTURE</span>
            <span style={{ fontFamily: FONT, fontSize: 10, color: C.textMid }}>
              PUSH_OPENED · ENROLLED · IGNORED · OPT_OUT → feedback to A/B + Model Governance + MLOps
            </span>
          </div>

          <p style={{ fontFamily: FONT, fontSize: 10, color: C.textDim, marginTop: 10, textAlign: "center" }}>
            Click any layer card to expand Marcus Webb example, outputs, and technology stack
          </p>
        </div>
      )}

      {/* ── DATA FLOW TAB ── */}
      {tab === "data flow" && (
        <div style={{ animation: "fadein 0.3s ease" }}>
          <div style={{
            background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: 16, marginBottom: 16,
          }}>
            <div style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.12em", marginBottom: 12 }}>
              MARCUS WEBB (C002) · PAYMENT RISK INTERVENTION · trace_id: trace_20260511_104233_C002
            </div>
            {TIMELINE.map((item, i) => (
              <div key={i} style={{
                display: "flex", gap: 12, alignItems: "flex-start",
                padding: "7px 0",
                borderBottom: i < TIMELINE.length - 1 ? `1px solid ${C.border}` : "none",
              }}>
                <span style={{
                  fontFamily: FONT, fontSize: 10, color: C.textDim,
                  minWidth: 80, flexShrink: 0,
                }}>{item.t}</span>
                <span style={{
                  fontFamily: FONT, fontSize: 10, fontWeight: 700,
                  color: LAYER_COLORS[item.layer],
                  minWidth: 28, flexShrink: 0,
                }}>{item.layer}</span>
                <span style={{ fontFamily: FONT, fontSize: 11, color: C.textMid, lineHeight: 1.5 }}>
                  {item.event}
                </span>
              </div>
            ))}
          </div>

          {/* LATENCY BREAKDOWN */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: 16 }}>
            <div style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.12em", marginBottom: 12 }}>
              END-TO-END LATENCY BREAKDOWN
            </div>
            {LAYERS.map(l => {
              const ms = parseInt(l.latency.replace(/[^0-9]/g, ""));
              const total = 6444;
              const pct = (ms / total) * 100;
              return (
                <div key={l.id} style={{ marginBottom: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 3 }}>
                    <span style={{ fontFamily: FONT, fontSize: 10, color: l.color }}>{l.label}</span>
                    <span style={{ fontFamily: FONT, fontSize: 10, color: C.textMid }}>{l.latency}</span>
                  </div>
                  <div style={{ height: 4, background: C.border, borderRadius: 2, overflow: "hidden" }}>
                    <div style={{
                      height: "100%", width: `${Math.max(pct, 0.5)}%`,
                      background: l.color, borderRadius: 2,
                      transition: "width 0.6s ease",
                    }} />
                  </div>
                </div>
              );
            })}
            <div style={{
              marginTop: 12, paddingTop: 12, borderTop: `1px solid ${C.border}`,
              display: "flex", justifyContent: "space-between",
            }}>
              <span style={{ fontFamily: FONT, fontSize: 10, color: C.textDim }}>TOTAL END-TO-END</span>
              <span style={{ fontFamily: FONT, fontSize: 12, fontWeight: 700, color: C.text }}>6,444ms</span>
            </div>
            <div style={{ marginTop: 6 }}>
              <span style={{ fontFamily: FONT, fontSize: 9, color: C.textDim }}>
                Note: 94% of latency is Layer 3 (2 LLM calls). Layers 1,2,4,5,6 combined = 372ms.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── TECH STACK TAB ── */}
      {tab === "tech stack" && (
        <div style={{ animation: "fadein 0.3s ease" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {LAYERS.map(l => (
              <div key={l.id} style={{
                background: C.card, border: `1px solid ${C.border}`,
                borderRadius: 8, padding: "12px 14px",
                borderLeft: `2px solid ${l.color}`,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
                  <span style={{ fontFamily: FONT, fontSize: 9, color: l.color, fontWeight: 700 }}>L{l.num}</span>
                  <span style={{ fontFamily: SANS, fontWeight: 600, fontSize: 12, color: C.text }}>{l.label}</span>
                </div>
                {l.tech.map(t => (
                  <div key={t} style={{ display: "flex", gap: 6, alignItems: "center", marginBottom: 5 }}>
                    <span style={{ color: l.color, fontSize: 10, flexShrink: 0 }}>·</span>
                    <span style={{ fontFamily: FONT, fontSize: 10, color: C.textMid }}>{t}</span>
                  </div>
                ))}
              </div>
            ))}

            {/* Cross-cutting tech */}
            <div style={{
              gridColumn: "1/-1",
              background: C.card, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "12px 14px",
            }}>
              <div style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.12em", marginBottom: 10 }}>
                CROSS-CUTTING TECHNOLOGY
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr 1fr", gap: 8 }}>
                {[
                  { label: "Tracing", tech: "AWS X-Ray", color: C.orange },
                  { label: "Metrics", tech: "CloudWatch + PagerDuty", color: C.orange },
                  { label: "Audit Hot", tech: "DynamoDB (90d)", color: C.orange },
                  { label: "Audit Cold", tech: "S3 Object Lock (7yr)", color: C.orange },
                  { label: "Feature Store", tech: "SageMaker Feature Store", color: C.purple },
                  { label: "Training", tech: "SageMaker Pipelines", color: C.purple },
                  { label: "Model Registry", tech: "SageMaker Model Registry", color: C.purple },
                  { label: "Drift Monitor", tech: "SageMaker Model Monitor", color: C.purple },
                ].map(item => (
                  <div key={item.label} style={{
                    background: C.bg, borderRadius: 5, padding: "8px 10px",
                    border: `1px solid ${item.color}25`,
                  }}>
                    <div style={{ fontFamily: FONT, fontSize: 9, color: item.color, marginBottom: 3 }}>{item.label}</div>
                    <div style={{ fontFamily: FONT, fontSize: 10, color: C.textMid }}>{item.tech}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Cloud agnostic note */}
          <div style={{
            marginTop: 10, background: C.card, border: `1px solid ${C.border}`,
            borderRadius: 8, padding: "10px 14px",
          }}>
            <span style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.1em" }}>
              CLOUD AGNOSTIC NOTE · </span>
            <span style={{ fontFamily: FONT, fontSize: 10, color: C.textMid }}>
              All AWS services are deployment choices, not design constraints. Patterns (parallel fetch,
              TTL context store, hub-and-spoke orchestration, champion/challenger) are universal.
              OCI equivalent: OCI Dataflow · Redis on OCI · OCI Functions · OCI Object Storage.
            </span>
          </div>
        </div>
      )}

      {/* FOOTER */}
      <div style={{ marginTop: 20, textAlign: "center" }}>
        <span style={{ fontFamily: FONT, fontSize: 9, color: C.textDim, letterSpacing: "0.12em" }}>
          BANKING AGENTIC AI PLATFORM · PRODUCTION REFERENCE ARCHITECTURE · v0.8 · MAY 2026
        </span>
      </div>
    </div>
  );
}
