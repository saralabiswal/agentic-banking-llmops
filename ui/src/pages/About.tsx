/**
 * Author: Sarala Biswal
 */
import type { LucideIcon } from "lucide-react";
import { useState } from "react";
import {
  Archive,
  Cloud,
  FileSearch,
  GitBranch,
  Layers as LayersIcon,
  Lock,
  Shield,
  TrendingDown,
  Zap,
  CircleAlert as AlertCircle
} from "lucide-react";
import { LAYER_COLORS } from "../architecture/content";

interface FailureRow {
  title: string;
  description: string;
}

interface LayerValue {
  id: "L1" | "L2" | "L3" | "L4" | "L5" | "L6";
  name: string;
  value: string;
}

interface ScenarioCardData {
  title: string;
  colorId: "L1" | "L3" | "L5";
  icon: LucideIcon;
  customer: string;
  withoutPlatform: string;
  withPlatform: string;
}

interface Principle {
  icon: LucideIcon;
  title: string;
  description: string;
}

type AboutTabId = "problem" | "six-layers" | "scenarios" | "principles";

const sectionTabs = [
  { id: "problem", label: "Problem" },
  { id: "six-layers", label: "Six Layers" },
  { id: "scenarios", label: "Scenarios" },
  { id: "principles", label: "Principles" }
] satisfies { id: AboutTabId; label: string }[];

const tags = ["Open Source", "No API Key Required", "Cloud Agnostic", "Regulatory Replay"];

const problemParagraphs = [
  "Banks hold enough customer data to act before a customer misses a payment, churns, or disputes a charge. But most AI interventions arrive too late, act on stale data, or fire without any compliance check.",
  "A customer's risk score from last night's batch job does not reflect the $500 transfer they made this morning. An intervention that ignores that transfer produces a hardship offer to someone who no longer needs it — and a confused, annoyed customer.",
  "At the same time, every product team building AI features reimplements the same pipeline: fetch context, retrieve policy, run a model, check compliance, deliver the action. Each reimplementation has gaps. Each gap is a compliance risk or a quality failure waiting to surface."
];

const failureRows: FailureRow[] = [
  {
    title: "Batch scoring latency",
    description:
      "Nightly risk scores are stale by morning. A customer who transferred funds, opened a ticket, or received a prior intervention looks identical to one who did not. Agents reasoning on yesterday's data make decisions that feel wrong to the customer."
  },
  {
    title: "Prompt-stuffed context",
    description:
      "Stuffing entire customer histories into LLM prompts is expensive, slow, and imprecise. Without a retrieval layer, agents cannot distinguish which policy applies to this customer's situation from thousands of documents."
  },
  {
    title: "Ungoverned agent actions",
    description:
      "An agent that can directly execute — send a push, create a case, apply a rate reduction — has no compliance gate. One misconfigured prompt or injected instruction can trigger a customer-facing action that violates fair lending, CFPB, or UDAAP requirements."
  },
  {
    title: "No feedback loop",
    description:
      "An intervention that fires has no way to measure whether it worked, which variant performed better, or whether the underlying model is drifting. Without outcome capture, there is no learning."
  }
];

const layers: LayerValue[] = [
  {
    id: "L1",
    name: "Context Assembly",
    value: "Live customer context assembled from every source system in under 200ms — not last night's batch."
  },
  {
    id: "L2",
    name: "Vector Search",
    value:
      "The right policy retrieved at decision time, not hardcoded into prompts that go stale when regulations change."
  },
  {
    id: "L3",
    name: "Multi-Agent Orchestration",
    value: "Specialized agents that propose actions through a governed hub — never executing directly against customer systems."
  },
  {
    id: "L4",
    name: "Guardrails & Policy",
    value: "Every proposed action checked against regulatory, business, and fairness rules before it reaches a customer."
  },
  {
    id: "L5",
    name: "A/B Evaluation",
    value:
      "Interventions that improve over time through deterministic variant assignment, outcome capture, and drift detection."
  },
  {
    id: "L6",
    name: "SDK + Execution",
    value:
      "A stable platform surface so product teams inherit all six layers in three lines of code — not three months of work."
  }
];

const scenarios: ScenarioCardData[] = [
  {
    title: "Payment Risk Intervention",
    colorId: "L1",
    icon: AlertCircle,
    customer: "Marcus Webb has missed two payments, holds $312 in checking, and has a 71% risk score.",
    withoutPlatform:
      "A nightly batch job flags Marcus. A generic SMS fires the next morning. No compliance check. No variant test. No outcome tracking.",
    withPlatform:
      "Live context assembled in 167ms. Hardship eligibility confirmed against current policy. Guardrails check 8 regulatory and business rules. Variant A (soft framing) selected with 99.98% confidence. Push delivered. Enrollment outcome captured 9 minutes later."
  },
  {
    title: "Billing Dispute Resolution",
    colorId: "L3",
    icon: FileSearch,
    customer: "A customer disputes a charge and expects resolution within the CFPB's 5-business-day window.",
    withoutPlatform:
      "An associate manually pulls account history, checks policy docs, and decides whether to apply provisional credit. Inconsistent. Slow. Unaudited.",
    withPlatform:
      "DisputeTriageAgent retrieves CFPB Reg E requirements from the knowledge base. ResolutionAgent proposes a resolution. Guardrails verify the provisional credit timeline. Audit trail records every step for regulatory examination."
  },
  {
    title: "Churn Prevention",
    colorId: "L5",
    icon: TrendingDown,
    customer: "Priya Sharma's NPS dropped 20 points and her app logins have declined three weeks in a row.",
    withoutPlatform:
      "A monthly churn model scores Priya in the next batch run. A generic retention email fires. No personalization. No measurement.",
    withPlatform:
      "Churn signals assembled live. Retention offer generated from current product eligibility. Fairness check confirms consistent treatment across segments. Outcome tracked: did Priya re-engage?"
  }
];

const principles: Principle[] = [
  {
    icon: Zap,
    title: "Live context over cached snapshots",
    description:
      "Agents act on data fetched at decision time. Stale batch exports produce decisions that feel wrong to the customer."
  },
  {
    icon: Shield,
    title: "Governance as a runtime capability",
    description:
      "Guardrails, fairness checks, and policy enforcement run before any action executes — not as a post-hoc review."
  },
  {
    icon: GitBranch,
    title: "Hub-and-spoke orchestration",
    description:
      "All inter-agent communication routes through the orchestrator. Peer-to-peer agent calls have no central audit point."
  },
  {
    icon: LayersIcon,
    title: "Graceful degradation over hard failure",
    description: "A source timeout produces a partial profile with a flag — not a failed pipeline and no intervention."
  },
  {
    icon: FileSearch,
    title: "Full lineage for regulatory replay",
    description:
      "One trace_id reconstructs what data the agent had, which policy it followed, what compliance checks ran, and what the outcome was."
  },
  {
    icon: Cloud,
    title: "Cloud-agnostic by design",
    description:
      "Patterns are universal. Valkey, PostgreSQL, Qdrant, and Jaeger map directly to ElastiCache, RDS, Pinecone, and X-Ray in production."
  },
  {
    icon: Lock,
    title: "One writer, many readers",
    description:
      "Each layer has a single authoritative writer. Agents are always consumers — never producers — of shared state."
  },
  {
    icon: Archive,
    title: "Immutable audit trail",
    description:
      "Audit records are written once and never modified. Regulatory records must survive longer than the sessions that created them."
  }
];

/**
 * Renders the business narrative that explains why the platform architecture exists.
 */
export default function About(): JSX.Element {
  const [activeTab, setActiveTab] = useState<AboutTabId>("problem");

  return (
    <section className="space-y-5" data-testid="about-page">
      <section className="overflow-hidden rounded-md border border-slate-800 bg-slate-900">
        <div className="p-6">
          <div className="text-xs font-bold uppercase tracking-widest text-emerald-300">About the platform</div>
          <p className="mt-4 max-w-5xl text-sm leading-7 text-slate-300">
            A six-layer, open-source reference architecture that shows how to build AI-powered banking
            interventions that are live, governed, measurable, and explainable — end to end.
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span
                className="rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <nav
          aria-label="About sections"
          className="flex gap-1.5 overflow-x-auto border-t border-slate-800 px-5 py-3"
          role="tablist"
        >
          {sectionTabs.map((tab) => (
            <button
              aria-selected={activeTab === tab.id}
              className={[
                "flex h-9 shrink-0 items-center rounded-md border px-3 text-xs font-semibold transition",
                activeTab === tab.id
                  ? "border-emerald-300/60 bg-emerald-500 text-slate-950 shadow-[0_0_0_2px_rgba(59,130,246,0.7)]"
                  : "border-slate-800 text-slate-300 hover:border-slate-600 hover:text-white"
              ].join(" ")}
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              role="tab"
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </section>

      <div role="tabpanel">{renderActiveTab(activeTab)}</div>
    </section>
  );
}

function renderActiveTab(activeTab: AboutTabId): JSX.Element {
  if (activeTab === "six-layers") {
    return <SixLayerSolution />;
  }
  if (activeTab === "scenarios") {
    return <ScenarioSection />;
  }
  if (activeTab === "principles") {
    return <PrinciplesSection />;
  }
  return <ProblemSection />;
}

function ProblemSection(): JSX.Element {
  return (
    <section className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_420px]">
      <article className="rounded-md border border-slate-800 bg-slate-900 p-5">
        <SectionLabel value="The Problem" />
        <div className="mt-4 space-y-3">
          {problemParagraphs.map((paragraph) => (
            <p className="text-sm leading-7 text-slate-300" key={paragraph}>
              {paragraph}
            </p>
          ))}
        </div>
      </article>
      <article className="rounded-md border border-slate-800 bg-slate-900 p-5">
        <SectionLabel value="Why Existing Approaches Fall Short" />
        <div className="mt-4 space-y-3">
          {failureRows.map((row) => (
            <div className="rounded-md border border-slate-800 bg-slate-950 p-3" key={row.title}>
              <h3 className="text-sm font-semibold text-white">{row.title}</h3>
              <p className="mt-1 text-xs leading-5 text-slate-400">{row.description}</p>
            </div>
          ))}
        </div>
      </article>
    </section>
  );
}

function SixLayerSolution(): JSX.Element {
  return (
    <section className="rounded-md border border-slate-800 bg-slate-900 p-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <SectionLabel value="The Six-Layer Solution" />
          <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
            Each layer solves one problem. Together they form a governed pipeline that product teams can
            consume in a few lines of code.
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {layers.map((layer) => (
          <LayerCard key={layer.id} layer={layer} />
        ))}
      </div>
    </section>
  );
}

function ScenarioSection(): JSX.Element {
  return (
    <section className="rounded-md border border-slate-800 bg-slate-900 p-5">
      <SectionLabel value="Three Scenarios, One Platform" />
      <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-400">
        The same six layers handle every banking intervention scenario. The pipeline changes. The governance
        does not.
      </p>
      <div className="mt-4 grid gap-4 xl:grid-cols-3">
        {scenarios.map((scenario) => (
          <ScenarioCard key={scenario.title} scenario={scenario} />
        ))}
      </div>
    </section>
  );
}

function PrinciplesSection(): JSX.Element {
  return (
    <section className="rounded-md border border-slate-800 bg-slate-900 p-5">
      <SectionLabel value="Built on Eight Principles" />
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {principles.map((principle) => (
          <PrincipleRow key={principle.title} principle={principle} />
        ))}
      </div>
    </section>
  );
}

function SectionLabel({ value }: { value: string }): JSX.Element {
  return (
    <div className="text-xs font-bold uppercase tracking-widest text-slate-500">
      {value}
    </div>
  );
}

function LayerCard({ layer }: { layer: LayerValue }): JSX.Element {
  const colors = LAYER_COLORS[layer.id];

  return (
    <article className={`rounded-md border ${colors.borderIdle} ${colors.bg} p-4`}>
      <div className="flex items-center gap-2">
        <span className={`rounded px-2 py-1 text-[10px] font-bold ${colors.badgeBg} ${colors.badgeText}`}>
          {layer.id}
        </span>
        <h3 className="text-sm font-semibold text-white">{layer.name}</h3>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-300">{layer.value}</p>
    </article>
  );
}

function ScenarioCard({ scenario }: { scenario: ScenarioCardData }): JSX.Element {
  const colors = LAYER_COLORS[scenario.colorId];
  const Icon = scenario.icon;

  return (
    <article className={`rounded-md border ${colors.borderIdle} bg-slate-950 p-4`}>
      <div className="flex items-start gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${colors.bg} ${colors.text}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div>
          <h3 className="text-base font-semibold text-white">{scenario.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-300">{scenario.customer}</p>
        </div>
      </div>
      <div className="mt-4 space-y-3">
        <ScenarioBlock label="Without the platform" tone="red" value={scenario.withoutPlatform} />
        <ScenarioBlock label="With the platform" tone="emerald" value={scenario.withPlatform} />
      </div>
    </article>
  );
}

function ScenarioBlock({
  label,
  tone,
  value
}: {
  label: string;
  tone: "emerald" | "red";
  value: string;
}): JSX.Element {
  const toneClass =
    tone === "red"
      ? "border-red-500/25 bg-red-500/5 text-red-300"
      : "border-emerald-500/25 bg-emerald-500/5 text-emerald-300";

  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="text-[10px] font-bold uppercase tracking-widest">{label}</div>
      <p className="mt-2 text-xs leading-5 text-slate-300">{value}</p>
    </div>
  );
}

function PrincipleRow({ principle }: { principle: Principle }): JSX.Element {
  const Icon = principle.icon;

  return (
    <article className="flex gap-3 rounded-md border border-slate-800 bg-slate-950 p-4">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-500/10 text-blue-300">
        <Icon className="h-4 w-4" />
      </span>
      <div>
        <h3 className="text-sm font-semibold text-white">{principle.title}</h3>
        <p className="mt-1 text-xs leading-5 text-slate-400">{principle.description}</p>
      </div>
    </article>
  );
}
