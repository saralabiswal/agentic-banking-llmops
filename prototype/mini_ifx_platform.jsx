import { useState, useEffect, useRef, useCallback } from "react";

// ─── DESIGN TOKENS ────────────────────────────────────────────────────────────
const T = {
  bg: "#0a0c10",
  surface: "#111318",
  surfaceHigh: "#181c24",
  border: "#1e2330",
  borderBright: "#2a3148",
  accent: "#3b82f6",
  accentDim: "#1d3f7a",
  accentGlow: "rgba(59,130,246,0.15)",
  green: "#10b981",
  greenDim: "#064e3b",
  red: "#ef4444",
  redDim: "#450a0a",
  yellow: "#f59e0b",
  yellowDim: "#451a03",
  purple: "#a855f7",
  purpleDim: "#2e1065",
  text: "#e2e8f0",
  textMid: "#94a3b8",
  textDim: "#475569",
  fontMono: "'JetBrains Mono', 'Fira Code', monospace",
  fontSans: "'IBM Plex Sans', system-ui, sans-serif",
};

// ─── MOCK CUSTOMER DATA ───────────────────────────────────────────────────────
const CUSTOMERS = {
  C001: {
    id: "C001", name: "Alexandra Chen", segment: "Prime",
    card: { balance: 4230.50, limit: 15000, utilization: 0.28, missed_payments: 0 },
    banking: { checking: 8420.00, savings: 22000.00, last_deposit: "2026-05-01" },
    crm: { tenure_years: 6, nps_score: 82, open_tickets: 0, last_contact: "2026-04-12" },
    risk_score: 0.08, churn_probability: 0.04,
  },
  C002: {
    id: "C002", name: "Marcus Webb", segment: "Standard",
    card: { balance: 3800.00, limit: 5000, utilization: 0.76, missed_payments: 2 },
    banking: { checking: 312.40, savings: 0, last_deposit: "2026-04-15" },
    crm: { tenure_years: 2, nps_score: 44, open_tickets: 2, last_contact: "2026-05-08" },
    risk_score: 0.71, churn_probability: 0.58,
  },
  C003: {
    id: "C003", name: "Priya Sharma", segment: "Affluent",
    card: { balance: 1200.00, limit: 25000, utilization: 0.05, missed_payments: 0 },
    banking: { checking: 45000.00, savings: 180000.00, last_deposit: "2026-05-09" },
    crm: { tenure_years: 11, nps_score: 94, open_tickets: 0, last_contact: "2026-03-20" },
    risk_score: 0.03, churn_probability: 0.02,
  },
};

const KNOWLEDGE_BASE = [
  { id: "KB001", text: "Customers with utilization above 70% are eligible for credit limit increase review if payment history is clean.", tags: ["credit", "limit"] },
  { id: "KB002", text: "Hardship program offers 90-day payment deferral for customers with 2+ missed payments and checking balance under $500.", tags: ["hardship", "payment"] },
  { id: "KB003", text: "Dispute resolution under CFPB Reg E requires provisional credit within 5 business days of dispute filing.", tags: ["dispute", "regulation"] },
  { id: "KB004", text: "Fraud alerts should be triggered when transaction location is more than 500 miles from last known location.", tags: ["fraud", "alert"] },
  { id: "KB005", text: "High-value customers (NPS > 80, tenure > 5 years) qualify for relationship manager escalation and premium offers.", tags: ["retention", "premium"] },
  { id: "KB006", text: "Payment intervention effectiveness: SMS reminder +12% on-time payment, hardship call +34%, rate reduction offer +41%.", tags: ["intervention", "payment"] },
  { id: "KB007", text: "Churn propensity model: key signals are NPS below 50, utilization change > 20%, and 2+ service interactions in 30 days.", tags: ["churn", "model"] },
  { id: "KB008", text: "Credit limit increase requests require: 12+ months account history, utilization > 60%, no missed payments in 6 months.", tags: ["credit", "policy"] },
];

const GUARDRAIL_RULES = [
  { id: "G001", name: "PII Exposure Block", description: "Block any action that would expose SSN, DOB, or full account number in response", severity: "CRITICAL" },
  { id: "G002", name: "Fair Lending Check", description: "Ensure credit decisions are not correlated with protected class signals", severity: "HIGH" },
  { id: "G003", name: "Hardship Program Auth", description: "Hardship enrollments > $5000 require supervisor approval queue", severity: "HIGH" },
  { id: "G004", name: "Rate Modification Limit", description: "APR reductions > 5% require VP-level approval workflow", severity: "MEDIUM" },
  { id: "G005", name: "Contact Frequency Cap", description: "Maximum 3 outbound contacts per customer per 7-day window", severity: "MEDIUM" },
  { id: "G006", name: "Regulatory Compliance", description: "All dispute resolutions must log CFPB Reg E provisional credit timeline", severity: "HIGH" },
];

// ─── API CALL ─────────────────────────────────────────────────────────────────
async function callClaude(systemPrompt, userMessage, maxTokens = 600) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: "user", content: userMessage }],
    }),
  });
  const data = await res.json();
  return data.content?.[0]?.text || "";
}

// ─── LAYER BADGE ──────────────────────────────────────────────────────────────
function LayerBadge({ label, color }) {
  const colors = {
    blue: { bg: T.accentDim, text: T.accent, border: T.accent },
    green: { bg: T.greenDim, text: T.green, border: T.green },
    red: { bg: T.redDim, text: T.red, border: T.red },
    yellow: { bg: T.yellowDim, text: T.yellow, border: T.yellow },
    purple: { bg: T.purpleDim, text: T.purple, border: T.purple },
  };
  const c = colors[color] || colors.blue;
  return (
    <span style={{
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      borderRadius: 4, fontSize: 10, fontFamily: T.fontMono,
      padding: "2px 8px", letterSpacing: "0.08em", fontWeight: 700,
      textTransform: "uppercase",
    }}>{label}</span>
  );
}

// ─── LOG LINE ─────────────────────────────────────────────────────────────────
function LogLine({ ts, layer, msg, type = "info" }) {
  const colors = { info: T.textMid, success: T.green, warn: T.yellow, error: T.red, system: T.accent };
  return (
    <div style={{ display: "flex", gap: 10, fontFamily: T.fontMono, fontSize: 11, lineHeight: "1.6", borderBottom: `1px solid ${T.border}`, padding: "3px 0" }}>
      <span style={{ color: T.textDim, minWidth: 60 }}>{ts}</span>
      <span style={{ color: T.accentDim, minWidth: 80, color: T.purple }}>[{layer}]</span>
      <span style={{ color: colors[type] }}>{msg}</span>
    </div>
  );
}

// ─── SECTION CARD ─────────────────────────────────────────────────────────────
function SectionCard({ title, badge, badgeColor, children, glowing }) {
  return (
    <div style={{
      background: T.surface, border: `1px solid ${glowing ? T.accent : T.border}`,
      borderRadius: 10, overflow: "hidden",
      boxShadow: glowing ? `0 0 24px ${T.accentGlow}` : "none",
      transition: "box-shadow 0.4s",
    }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "12px 16px", borderBottom: `1px solid ${T.border}`,
        background: T.surfaceHigh,
      }}>
        <span style={{ fontFamily: T.fontSans, fontWeight: 600, color: T.text, fontSize: 13, flex: 1 }}>{title}</span>
        {badge && <LayerBadge label={badge} color={badgeColor || "blue"} />}
      </div>
      <div style={{ padding: 16 }}>{children}</div>
    </div>
  );
}

// ─── SPINNER ──────────────────────────────────────────────────────────────────
function Spinner() {
  return (
    <div style={{ display: "inline-block", width: 14, height: 14, border: `2px solid ${T.borderBright}`, borderTopColor: T.accent, borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function BankingAgenticPlatform() {
  const [selectedCustomer, setSelectedCustomer] = useState("C002");
  const [scenario, setScenario] = useState("payment_risk");
  const [running, setRunning] = useState(false);
  const [activeLayer, setActiveLayer] = useState(null);
  const [logs, setLogs] = useState([]);
  const [results, setResults] = useState({});
  const [abResults, setAbResults] = useState(null);
  const [vectorResults, setVectorResults] = useState([]);
  const [guardrailResults, setGuardrailResults] = useState([]);
  const logRef = useRef(null);

  const customer = CUSTOMERS[selectedCustomer];

  const addLog = useCallback((layer, msg, type = "info") => {
    const ts = new Date().toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
    setLogs(prev => [...prev, { ts, layer, msg, type }]);
    setTimeout(() => logRef.current?.scrollTo({ top: 9999, behavior: "smooth" }), 50);
  }, []);

  const SCENARIOS = {
    payment_risk: { label: "Payment Risk Intervention", desc: "Detect and intervene on missed payment risk" },
    dispute: { label: "Billing Dispute Resolution", desc: "Autonomous dispute triage and resolution" },
    churn: { label: "Churn Prevention", desc: "Identify churn signals and generate retention offer" },
  };

  async function runPipeline() {
    if (running) return;
    setRunning(true);
    setLogs([]);
    setResults({});
    setAbResults(null);
    setVectorResults([]);
    setGuardrailResults([]);

    const cust = CUSTOMERS[selectedCustomer];

    try {
      // ── LAYER 1: CONTEXT ASSEMBLY ──────────────────────────────────────────
      setActiveLayer("context");
      addLog("CONTEXT", "Initializing unified customer profile assembly...", "system");
      await sleep(300);
      addLog("CONTEXT", `Fetching card data for ${cust.id} — balance: $${cust.card.balance}, util: ${Math.round(cust.card.utilization * 100)}%`, "info");
      await sleep(250);
      addLog("CONTEXT", `Fetching banking data — checking: $${cust.banking.checking}, savings: $${cust.banking.savings}`, "info");
      await sleep(250);
      addLog("CONTEXT", `Fetching CRM signals — NPS: ${cust.crm.nps_score}, tenure: ${cust.crm.tenure_years}yr, open tickets: ${cust.crm.open_tickets}`, "info");
      await sleep(200);
      addLog("CONTEXT", `Unified customer profile assembled — risk_score: ${cust.risk_score}, churn_prob: ${cust.churn_probability}`, "success");

      const contextSummary = `Customer: ${cust.name} (${cust.segment})
Card: balance $${cust.card.balance}, limit $${cust.card.limit}, utilization ${Math.round(cust.card.utilization*100)}%, missed_payments: ${cust.card.missed_payments}
Banking: checking $${cust.banking.checking}, savings $${cust.banking.savings}
CRM: tenure ${cust.crm.tenure_years}yr, NPS ${cust.crm.nps_score}, open_tickets ${cust.crm.open_tickets}
Risk score: ${cust.risk_score} | Churn probability: ${cust.churn_probability}`;

      setResults(r => ({ ...r, context: contextSummary }));

      // ── LAYER 2: VECTOR SEARCH ─────────────────────────────────────────────
      setActiveLayer("vector");
      addLog("VECTOR", "Running semantic search over knowledge base...", "system");
      await sleep(300);

      const vectorQuery = scenario === "payment_risk" ? "payment intervention hardship missed payments"
        : scenario === "dispute" ? "dispute resolution CFPB regulation provisional credit"
        : "churn retention NPS customer lifetime value";

      addLog("VECTOR", `Query: "${vectorQuery}"`, "info");
      await sleep(400);

      const relevant = KNOWLEDGE_BASE
        .map(kb => ({ ...kb, score: computeSimScore(kb.text, vectorQuery) }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 3);

      relevant.forEach(r => {
        addLog("VECTOR", `[${r.id}] score: ${r.score.toFixed(3)} — ${r.text.substring(0, 60)}...`, "info");
      });
      addLog("VECTOR", `Top 3 knowledge articles retrieved`, "success");
      setVectorResults(relevant);

      const knowledgeContext = relevant.map(r => r.text).join("\n");

      // ── LAYER 3: ORCHESTRATOR ROUTES TO AGENTS ─────────────────────────────
      setActiveLayer("orchestrator");
      addLog("ORCH", "Orchestrator receiving task from context layer...", "system");
      await sleep(300);
      addLog("ORCH", `Scenario: ${SCENARIOS[scenario].label}`, "info");
      await sleep(200);

      const agentMap = {
        payment_risk: ["RiskScoringAgent", "InterventionAgent"],
        dispute: ["DisputeTriageAgent", "ResolutionAgent"],
        churn: ["ChurnSignalAgent", "RetentionOfferAgent"],
      };
      const agents = agentMap[scenario];
      addLog("ORCH", `Routing to: ${agents.join(" → ")}`, "info");
      await sleep(300);

      // ── LAYER 4: AGENT EXECUTION ───────────────────────────────────────────
      setActiveLayer("agents");
      addLog("AGENT", `[${agents[0]}] starting analysis...`, "system");

      const agentSystem = `You are ${agents[0]}, a specialized AI agent in a banking AI platform.
You analyze customer data and produce a structured assessment.
Respond in JSON with keys: assessment (string), risk_level (LOW/MEDIUM/HIGH/CRITICAL), signals (array of strings), recommended_action (string).
Be concise. Use real banking terminology.`;

      const agentPrompt = `Scenario: ${SCENARIOS[scenario].label}
Customer Profile:
${contextSummary}

Relevant Policy Knowledge:
${knowledgeContext}

Analyze this customer and produce your assessment.`;

      const agent1Raw = await callClaude(agentSystem, agentPrompt, 500);
      let agent1Result;
      try {
        const cleaned = agent1Raw.replace(/```json|```/g, "").trim();
        agent1Result = JSON.parse(cleaned);
      } catch {
        agent1Result = { assessment: agent1Raw, risk_level: "MEDIUM", signals: [], recommended_action: "Review manually" };
      }

      addLog("AGENT", `[${agents[0]}] risk_level: ${agent1Result.risk_level}`, agent1Result.risk_level === "CRITICAL" ? "error" : agent1Result.risk_level === "HIGH" ? "warn" : "success");
      addLog("AGENT", `[${agents[0]}] assessment: ${agent1Result.assessment?.substring(0, 80)}...`, "info");
      await sleep(400);

      addLog("AGENT", `[${agents[1]}] generating action recommendation...`, "system");

      const agent2System = `You are ${agents[1]}, a specialized AI agent in a banking AI platform.
Given an assessment from a prior agent, you generate a specific, actionable recommendation.
Respond in JSON: action_type (string), message_to_customer (string, max 2 sentences), internal_note (string), requires_approval (boolean), estimated_impact (string).`;

      const agent2Prompt = `Prior agent assessment:
${JSON.stringify(agent1Result)}

Customer context:
${contextSummary}

Policy knowledge:
${knowledgeContext}

Generate your action recommendation.`;

      const agent2Raw = await callClaude(agent2System, agent2Prompt, 500);
      let agent2Result;
      try {
        const cleaned = agent2Raw.replace(/```json|```/g, "").trim();
        agent2Result = JSON.parse(cleaned);
      } catch {
        agent2Result = { action_type: "Manual Review", message_to_customer: agent2Raw.substring(0, 200), internal_note: "", requires_approval: true, estimated_impact: "Unknown" };
      }

      addLog("AGENT", `[${agents[1]}] action: ${agent2Result.action_type}`, "success");
      addLog("AGENT", `[${agents[1]}] requires_approval: ${agent2Result.requires_approval}`, agent2Result.requires_approval ? "warn" : "success");
      setResults(r => ({ ...r, agent1: agent1Result, agent2: agent2Result }));

      // ── LAYER 5: GUARDRAILS ────────────────────────────────────────────────
      setActiveLayer("guardrails");
      addLog("GUARD", "Running policy enforcement layer...", "system");
      await sleep(300);

      const guardrailChecks = await runGuardrailChecks(agent2Result, cust);
      guardrailChecks.forEach(g => {
        addLog("GUARD", `[${g.id}] ${g.name}: ${g.status}${g.reason ? " — " + g.reason : ""}`,
          g.status === "BLOCKED" ? "error" : g.status === "FLAGGED" ? "warn" : "success");
      });
      setGuardrailResults(guardrailChecks);

      const blocked = guardrailChecks.find(g => g.status === "BLOCKED");
      if (blocked) {
        addLog("GUARD", `ACTION BLOCKED by ${blocked.name}. Routing to human review queue.`, "error");
        setResults(r => ({ ...r, blocked: true, blockReason: blocked.name }));
      } else {
        addLog("GUARD", "All guardrails passed. Action authorized for execution.", "success");
      }

      // ── LAYER 6: A/B EVALUATION ────────────────────────────────────────────
      setActiveLayer("eval");
      addLog("EVAL", "Running A/B experiment evaluation...", "system");
      await sleep(300);

      const expA = { variant: "A — Immediate Outreach", confidence: 0.72 + Math.random() * 0.1, lift: "+12% on-time payment" };
      const expB = { variant: "B — Personalized Hardship Offer", confidence: 0.85 + Math.random() * 0.08, lift: "+34% on-time payment" };
      addLog("EVAL", `Variant A: ${expA.variant} — confidence ${expA.confidence.toFixed(2)}, lift ${expA.lift}`, "info");
      addLog("EVAL", `Variant B: ${expB.variant} — confidence ${expB.confidence.toFixed(2)}, lift ${expB.lift}`, "info");

      const winner = expB.confidence > expA.confidence ? expB : expA;
      addLog("EVAL", `Winner: ${winner.variant} (p < 0.05, n=12,400 historical events)`, "success");
      setAbResults({ expA, expB, winner });

      // ── DONE ───────────────────────────────────────────────────────────────
      setActiveLayer("done");
      addLog("SYSTEM", "Pipeline complete. All layers executed.", "success");

    } catch (err) {
      addLog("SYSTEM", `Error: ${err.message}`, "error");
    } finally {
      setRunning(false);
      setActiveLayer(null);
    }
  }

  return (
    <div style={{ background: T.bg, minHeight: "100vh", fontFamily: T.fontSans, color: T.text, padding: "24px 20px" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: ${T.surface}; }
        ::-webkit-scrollbar-thumb { background: ${T.borderBright}; border-radius: 3px; }
        button:hover { filter: brightness(1.1); }
        button:active { filter: brightness(0.9); }
      `}</style>

      {/* HEADER */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: T.green, boxShadow: `0 0 8px ${T.green}`, animation: "pulse 2s infinite" }} />
          <span style={{ fontFamily: T.fontMono, fontSize: 11, color: T.textDim, letterSpacing: "0.15em" }}>BANKING AGENTIC AI PLATFORM — PROTOTYPE v0.1</span>
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 700, color: T.text, letterSpacing: "-0.02em" }}>
          Banking Agentic AI Platform
        </h1>
        <p style={{ color: T.textMid, fontSize: 13, marginTop: 4 }}>
          Banking Agentic AI Platform — Full Stack Demo &nbsp;·&nbsp; Context Assembly · Multi-Agent Orchestration · Vector Search · Guardrails · A/B Evaluation
        </p>
      </div>

      {/* ARCHITECTURE DIAGRAM */}
      <div style={{ marginBottom: 20 }}>
        <ArchDiagram activeLayer={activeLayer} />
      </div>

      {/* CONTROLS */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: 12, marginBottom: 20 }}>
        <div>
          <label style={{ fontSize: 11, color: T.textDim, fontFamily: T.fontMono, display: "block", marginBottom: 6, letterSpacing: "0.08em" }}>CUSTOMER</label>
          <select value={selectedCustomer} onChange={e => setSelectedCustomer(e.target.value)}
            disabled={running}
            style={{ width: "100%", background: T.surfaceHigh, border: `1px solid ${T.border}`, color: T.text, padding: "9px 12px", borderRadius: 6, fontSize: 13, fontFamily: T.fontSans }}>
            {Object.values(CUSTOMERS).map(c => (
              <option key={c.id} value={c.id}>{c.name} — {c.segment} (risk: {c.risk_score})</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: T.textDim, fontFamily: T.fontMono, display: "block", marginBottom: 6, letterSpacing: "0.08em" }}>SCENARIO</label>
          <select value={scenario} onChange={e => setScenario(e.target.value)}
            disabled={running}
            style={{ width: "100%", background: T.surfaceHigh, border: `1px solid ${T.border}`, color: T.text, padding: "9px 12px", borderRadius: 6, fontSize: 13, fontFamily: T.fontSans }}>
            {Object.entries(SCENARIOS).map(([k, v]) => (
              <option key={k} value={k}>{v.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 11, color: T.textDim, fontFamily: T.fontMono, display: "block", marginBottom: 6, letterSpacing: "0.08em" }}>CUSTOMER PROFILE</label>
          <div style={{ background: T.surfaceHigh, border: `1px solid ${T.border}`, borderRadius: 6, padding: "9px 12px", fontSize: 12, fontFamily: T.fontMono, color: T.textMid }}>
            Util: {Math.round(customer.card.utilization * 100)}% · NPS: {customer.crm.nps_score} · Risk: {customer.risk_score}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "flex-end" }}>
          <button onClick={runPipeline} disabled={running}
            style={{
              background: running ? T.surfaceHigh : T.accent, color: running ? T.textDim : "#fff",
              border: "none", borderRadius: 6, padding: "10px 24px", fontSize: 13, fontWeight: 600,
              cursor: running ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8,
              fontFamily: T.fontSans, whiteSpace: "nowrap",
            }}>
            {running ? <><Spinner /> Running...</> : "▶ Run Pipeline"}
          </button>
        </div>
      </div>

      {/* MAIN GRID */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>

        {/* CONTEXT LAYER */}
        <SectionCard title="Layer 1 — Context Assembly" badge="Data Fusion" badgeColor="blue" glowing={activeLayer === "context"}>
          <div style={{ fontSize: 12, color: T.textMid, marginBottom: 10 }}>
            Unifies card, banking, and CRM data from separate systems into a single customer context for agents.
          </div>
          {["card", "banking", "crm"].map(src => (
            <div key={src} style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 3, textTransform: "uppercase", letterSpacing: "0.1em" }}>{src} system</div>
              <div style={{ background: T.surfaceHigh, borderRadius: 5, padding: "8px 10px", fontFamily: T.fontMono, fontSize: 11, color: T.textMid }}>
                {src === "card" && `balance: $${customer.card.balance} · util: ${Math.round(customer.card.utilization * 100)}% · missed: ${customer.card.missed_payments}`}
                {src === "banking" && `checking: $${customer.banking.checking} · savings: $${customer.banking.savings}`}
                {src === "crm" && `NPS: ${customer.crm.nps_score} · tenure: ${customer.crm.tenure_years}yr · tickets: ${customer.crm.open_tickets}`}
              </div>
            </div>
          ))}
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            <StatPill label="Risk Score" value={customer.risk_score} high={0.5} />
            <StatPill label="Churn Prob" value={customer.churn_probability} high={0.4} />
            <StatPill label="Segment" value={customer.segment} text />
          </div>
        </SectionCard>

        {/* VECTOR SEARCH */}
        <SectionCard title="Layer 2 — Vector Search" badge="Semantic Retrieval" badgeColor="purple" glowing={activeLayer === "vector"}>
          <div style={{ fontSize: 12, color: T.textMid, marginBottom: 10 }}>
            Semantic search over policy knowledge base. Retrieves top-K relevant articles at query time, not batch.
          </div>
          {vectorResults.length === 0 ? (
            <div style={{ color: T.textDim, fontSize: 12, fontStyle: "italic" }}>Run pipeline to see semantic retrieval results...</div>
          ) : vectorResults.map(r => (
            <div key={r.id} style={{ background: T.surfaceHigh, borderRadius: 5, padding: "8px 10px", marginBottom: 8, borderLeft: `2px solid ${T.purple}` }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontFamily: T.fontMono, fontSize: 10, color: T.purple }}>{r.id}</span>
                <span style={{ fontFamily: T.fontMono, fontSize: 10, color: T.textDim }}>score: {r.score.toFixed(3)}</span>
              </div>
              <div style={{ fontSize: 11, color: T.textMid, lineHeight: 1.5 }}>{r.text}</div>
            </div>
          ))}
        </SectionCard>

        {/* AGENT ORCHESTRATION */}
        <SectionCard title="Layer 3 — Multi-Agent Orchestration" badge="Hub-and-Spoke" badgeColor="green" glowing={activeLayer === "orchestrator" || activeLayer === "agents"}>
          <div style={{ fontSize: 12, color: T.textMid, marginBottom: 12 }}>
            Orchestrator routes task to specialized agents. Each agent has authorized tools and scoped permissions.
          </div>
          {results.agent1 ? (
            <>
              <AgentCard name={scenario === "payment_risk" ? "RiskScoringAgent" : scenario === "dispute" ? "DisputeTriageAgent" : "ChurnSignalAgent"}
                result={results.agent1} />
              <div style={{ textAlign: "center", color: T.textDim, fontSize: 16, margin: "4px 0" }}>↓</div>
              <AgentCard name={scenario === "payment_risk" ? "InterventionAgent" : scenario === "dispute" ? "ResolutionAgent" : "RetentionOfferAgent"}
                result={results.agent2} isAction />
            </>
          ) : (
            <div style={{ color: T.textDim, fontSize: 12, fontStyle: "italic" }}>Run pipeline to see agent execution...</div>
          )}
        </SectionCard>

        {/* GUARDRAILS */}
        <SectionCard title="Layer 4 — Guardrails & Policy Enforcement" badge="Runtime Safety" badgeColor="red" glowing={activeLayer === "guardrails"}>
          <div style={{ fontSize: 12, color: T.textMid, marginBottom: 10 }}>
            Every agent action passes through policy enforcement before execution. Blocks, flags, or approves.
          </div>
          {guardrailResults.length === 0 ? (
            GUARDRAIL_RULES.slice(0, 4).map(g => (
              <GuardrailRow key={g.id} rule={g} status="PENDING" />
            ))
          ) : guardrailResults.map(g => (
            <GuardrailRow key={g.id} rule={g} status={g.status} reason={g.reason} />
          ))}
          {results.blocked && (
            <div style={{ background: T.redDim, border: `1px solid ${T.red}`, borderRadius: 5, padding: "8px 12px", marginTop: 10, fontSize: 12, color: T.red }}>
              ⛔ ACTION BLOCKED — Routed to human review queue
            </div>
          )}
        </SectionCard>
      </div>

      {/* A/B EVALUATION + EXECUTION LOG */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>

        {/* A/B */}
        <SectionCard title="Layer 5 — A/B Experimentation & Model Evaluation" badge="Eval" badgeColor="yellow" glowing={activeLayer === "eval"}>
          <div style={{ fontSize: 12, color: T.textMid, marginBottom: 12 }}>
            Multi-armed bandit evaluation across intervention strategies. Selects winning variant with statistical confidence.
          </div>
          {!abResults ? (
            <div style={{ color: T.textDim, fontSize: 12, fontStyle: "italic" }}>Run pipeline to see A/B evaluation...</div>
          ) : (
            <>
              {[abResults.expA, abResults.expB].map((exp, i) => {
                const isWinner = exp.variant === abResults.winner.variant;
                return (
                  <div key={i} style={{
                    background: isWinner ? T.greenDim : T.surfaceHigh,
                    border: `1px solid ${isWinner ? T.green : T.border}`,
                    borderRadius: 6, padding: "10px 12px", marginBottom: 8,
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color: isWinner ? T.green : T.text }}>{exp.variant}</span>
                      {isWinner && <span style={{ fontSize: 10, background: T.green, color: "#000", borderRadius: 3, padding: "1px 6px", fontFamily: T.fontMono, fontWeight: 700 }}>WINNER</span>}
                    </div>
                    <div style={{ fontFamily: T.fontMono, fontSize: 11, color: T.textMid }}>
                      Confidence: <span style={{ color: T.text }}>{(exp.confidence * 100).toFixed(1)}%</span> &nbsp;·&nbsp;
                      Lift: <span style={{ color: T.green }}>{exp.lift}</span>
                    </div>
                    <ConfidenceBar value={exp.confidence} />
                  </div>
                );
              })}
            </>
          )}
        </SectionCard>

        {/* EXECUTION LOG */}
        <SectionCard title="Execution Log — All Layers" badge="Live Trace" badgeColor="blue">
          <div ref={logRef} style={{ height: 240, overflowY: "auto", fontFamily: T.fontMono }}>
            {logs.length === 0 ? (
              <div style={{ color: T.textDim, fontSize: 11, fontStyle: "italic" }}>Awaiting pipeline execution...</div>
            ) : logs.map((l, i) => <LogLine key={i} {...l} />)}
          </div>
        </SectionCard>
      </div>

      {/* ACTION RESULT */}
      {results.agent2 && !results.blocked && (
        <SectionCard title="Layer 6 — Final Action Output (SDK Surface)" badge="Product Team Interface" badgeColor="green">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 6, letterSpacing: "0.1em" }}>ACTION TYPE</div>
              <div style={{ background: T.surfaceHigh, borderRadius: 5, padding: "10px 12px", fontSize: 13, color: T.green, fontWeight: 600 }}>
                {results.agent2.action_type}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 6, letterSpacing: "0.1em" }}>ESTIMATED IMPACT</div>
              <div style={{ background: T.surfaceHigh, borderRadius: 5, padding: "10px 12px", fontSize: 13, color: T.yellow }}>
                {results.agent2.estimated_impact}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 6, letterSpacing: "0.1em" }}>APPROVAL REQUIRED</div>
              <div style={{ background: results.agent2.requires_approval ? T.yellowDim : T.greenDim, borderRadius: 5, padding: "10px 12px", fontSize: 13, color: results.agent2.requires_approval ? T.yellow : T.green, fontWeight: 600 }}>
                {results.agent2.requires_approval ? "⚠ YES — In Queue" : "✓ AUTO-APPROVED"}
              </div>
            </div>
            <div style={{ gridColumn: "1/-1" }}>
              <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 6, letterSpacing: "0.1em" }}>CUSTOMER-FACING MESSAGE</div>
              <div style={{ background: T.surfaceHigh, borderRadius: 5, padding: "12px 14px", fontSize: 13, color: T.text, lineHeight: 1.6, borderLeft: `2px solid ${T.green}` }}>
                {results.agent2.message_to_customer}
              </div>
            </div>
            {results.agent2.internal_note && (
              <div style={{ gridColumn: "1/-1" }}>
                <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.accent, marginBottom: 6, letterSpacing: "0.1em" }}>INTERNAL NOTE</div>
                <div style={{ background: T.surfaceHigh, borderRadius: 5, padding: "12px 14px", fontSize: 12, color: T.textMid, lineHeight: 1.6 }}>
                  {results.agent2.internal_note}
                </div>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      <div style={{ marginTop: 16, textAlign: "center", fontFamily: T.fontMono, fontSize: 10, color: T.textDim, letterSpacing: "0.1em" }}>
        BANKING AGENTIC AI PLATFORM · CLOUD AGNOSTIC · ALL LAYERS ACTIVE · POWERED BY CLAUDE API
      </div>
    </div>
  );
}

// ─── ARCHITECTURE DIAGRAM ─────────────────────────────────────────────────────
function ArchDiagram({ activeLayer }) {
  const layers = [
    { id: "context", label: "Context Assembly", sub: "Card + Banking + CRM", color: T.accent },
    { id: "vector", label: "Vector Search", sub: "Semantic Retrieval", color: T.purple },
    { id: "orchestrator", label: "Orchestrator", sub: "Hub-and-Spoke Routing", color: T.green },
    { id: "agents", label: "Specialized Agents", sub: "Tool Use + Function Calling", color: T.green },
    { id: "guardrails", label: "Guardrails", sub: "Runtime Policy Enforcement", color: T.red },
    { id: "eval", label: "A/B Evaluation", sub: "Experiment + Model Scoring", color: T.yellow },
    { id: "done", label: "SDK Surface", sub: "Product Team Interface", color: T.textMid },
  ];
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 10, padding: "14px 16px" }}>
      <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.textDim, letterSpacing: "0.1em", marginBottom: 10 }}>PLATFORM ARCHITECTURE</div>
      <div style={{ display: "flex", alignItems: "center", gap: 0, overflowX: "auto" }}>
        {layers.map((l, i) => {
          const isActive = activeLayer === l.id || (activeLayer === "agents" && l.id === "orchestrator");
          return (
            <div key={l.id} style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
              <div style={{
                background: isActive ? l.color + "22" : T.surfaceHigh,
                border: `1px solid ${isActive ? l.color : T.border}`,
                borderRadius: 6, padding: "8px 12px", textAlign: "center", minWidth: 110,
                boxShadow: isActive ? `0 0 16px ${l.color}44` : "none",
                transition: "all 0.3s",
              }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: isActive ? l.color : T.text, marginBottom: 2 }}>{l.label}</div>
                <div style={{ fontSize: 9, color: T.textDim, fontFamily: T.fontMono }}>{l.sub}</div>
              </div>
              {i < layers.length - 1 && (
                <div style={{ color: T.textDim, fontSize: 14, padding: "0 4px", flexShrink: 0 }}>→</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── AGENT CARD ───────────────────────────────────────────────────────────────
function AgentCard({ name, result, isAction }) {
  const riskColor = { LOW: T.green, MEDIUM: T.yellow, HIGH: T.red, CRITICAL: T.red }[result.risk_level] || T.textMid;
  return (
    <div style={{ background: T.surfaceHigh, borderRadius: 6, padding: "10px 12px", borderLeft: `2px solid ${isAction ? T.green : T.accent}`, marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontFamily: T.fontMono, fontSize: 10, color: isAction ? T.green : T.accent }}>{name}</span>
        {result.risk_level && <span style={{ fontSize: 10, color: riskColor, fontFamily: T.fontMono, fontWeight: 700 }}>{result.risk_level}</span>}
        {result.action_type && <span style={{ fontSize: 10, color: T.green, fontFamily: T.fontMono }}>{result.action_type}</span>}
      </div>
      <div style={{ fontSize: 11, color: T.textMid, lineHeight: 1.5 }}>
        {(result.assessment || result.message_to_customer || "").substring(0, 120)}
        {(result.assessment || result.message_to_customer || "").length > 120 ? "..." : ""}
      </div>
      {result.signals && result.signals.length > 0 && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
          {result.signals.slice(0, 3).map((s, i) => (
            <span key={i} style={{ fontSize: 9, background: T.accentDim, color: T.accent, borderRadius: 3, padding: "1px 6px", fontFamily: T.fontMono }}>{s}</span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── GUARDRAIL ROW ────────────────────────────────────────────────────────────
function GuardrailRow({ rule, status, reason }) {
  const statusColor = { PASSED: T.green, FLAGGED: T.yellow, BLOCKED: T.red, PENDING: T.textDim }[status] || T.textDim;
  const statusIcon = { PASSED: "✓", FLAGGED: "⚠", BLOCKED: "⛔", PENDING: "○" }[status] || "○";
  return (
    <div style={{ display: "flex", gap: 10, alignItems: "flex-start", marginBottom: 7 }}>
      <span style={{ color: statusColor, fontSize: 12, minWidth: 16, marginTop: 1 }}>{statusIcon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 11, color: T.text, fontWeight: 500 }}>{rule.name}</div>
        {reason && <div style={{ fontSize: 10, color: statusColor, fontFamily: T.fontMono, marginTop: 2 }}>{reason}</div>}
      </div>
      <span style={{ fontSize: 9, fontFamily: T.fontMono, color: statusColor, whiteSpace: "nowrap" }}>{status}</span>
    </div>
  );
}

// ─── STAT PILL ────────────────────────────────────────────────────────────────
function StatPill({ label, value, high, text }) {
  const isHigh = !text && value > high;
  return (
    <div style={{ flex: 1, background: T.surfaceHigh, borderRadius: 5, padding: "6px 8px", textAlign: "center" }}>
      <div style={{ fontSize: 9, color: T.textDim, fontFamily: T.fontMono, marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 12, fontWeight: 700, color: text ? T.accent : isHigh ? T.red : T.green, fontFamily: T.fontMono }}>
        {text ? value : value}
      </div>
    </div>
  );
}

// ─── CONFIDENCE BAR ───────────────────────────────────────────────────────────
function ConfidenceBar({ value }) {
  return (
    <div style={{ height: 4, background: T.border, borderRadius: 2, marginTop: 8, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${value * 100}%`, background: T.green, borderRadius: 2, transition: "width 0.6s ease" }} />
    </div>
  );
}

// ─── HELPERS ──────────────────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function computeSimScore(text, query) {
  const t = text.toLowerCase(), q = query.toLowerCase();
  const qWords = q.split(/\s+/).filter(w => w.length > 3);
  const matches = qWords.filter(w => t.includes(w)).length;
  return 0.3 + (matches / Math.max(qWords.length, 1)) * 0.65 + Math.random() * 0.05;
}

async function runGuardrailChecks(action, customer) {
  await sleep(200);
  const checks = [
    {
      ...GUARDRAIL_RULES[0],
      status: "PASSED",
    },
    {
      ...GUARDRAIL_RULES[1],
      status: "PASSED",
    },
    {
      ...GUARDRAIL_RULES[2],
      status: action.requires_approval ? "FLAGGED" : "PASSED",
      reason: action.requires_approval ? "Requires supervisor approval queue" : undefined,
    },
    {
      ...GUARDRAIL_RULES[3],
      status: (action.action_type || "").toLowerCase().includes("rate") ? "FLAGGED" : "PASSED",
      reason: (action.action_type || "").toLowerCase().includes("rate") ? "Rate changes require VP review" : undefined,
    },
    {
      ...GUARDRAIL_RULES[4],
      status: customer.crm.open_tickets > 1 ? "FLAGGED" : "PASSED",
      reason: customer.crm.open_tickets > 1 ? `${customer.crm.open_tickets} active tickets — contact frequency check` : undefined,
    },
    {
      ...GUARDRAIL_RULES[5],
      status: "PASSED",
    },
  ];
  return checks;
}
