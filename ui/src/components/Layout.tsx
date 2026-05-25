/**
 * Author: Sarala Biswal
 */
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Beaker,
  ClipboardCheck,
  ClipboardList,
  FileClock,
  GitBranch,
  Info,
  LayoutDashboard,
  Settings as SettingsIcon,
  ShieldCheck
} from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { api } from "../api/client";

/**
 * Primary application routes rendered as horizontal tabs.
 *
 * Keeping the navigation metadata centralized makes the app shell easy to audit
 * when new enterprise views are added.
 */
const navItems = [
  { to: "/about", label: "About", icon: Info, activePrefix: "/about" },
  { to: "/", label: "Pipeline", icon: Activity, end: true },
  { to: "/architecture", label: "Architecture", icon: GitBranch, activePrefix: "/architecture" },
  { to: "/audit/demo-trace", label: "Audit", icon: FileClock, activePrefix: "/audit" },
  { to: "/evaluation", label: "Evaluation", icon: ClipboardList, activePrefix: "/evaluation" },
  { to: "/experiments", label: "Experiments", icon: Beaker, activePrefix: "/experiments" },
  { to: "/drift", label: "Drift", icon: LayoutDashboard, activePrefix: "/drift" },
  { to: "/guardrails", label: "Guardrails", icon: ShieldCheck, activePrefix: "/guardrails" },
  { to: "/models", label: "Models", icon: ClipboardCheck, activePrefix: "/models" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, activePrefix: "/settings" }
];

/**
 * Renders the global application shell, header metadata, and horizontal navigation tabs.
 */
export default function Layout(): JSX.Element {
  const location = useLocation();
  // The active LLM backend is server-owned runtime state; React Query keeps it fresh.
  const config = useQuery({
    queryKey: ["config"],
    queryFn: api.getConfig,
    retry: false
  });
  const llmLabel = config.data?.llmModeLabel ?? "Mock LLM";

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <header className="z-20 shrink-0 border-b border-slate-700 bg-slate-950/95 backdrop-blur">
        <div className="grid min-h-14 grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-6 py-3">
          <div className="min-w-0">
            <h1 className="truncate text-base font-semibold text-slate-100">Banking Agentic AI Platform</h1>
            <div className="mt-0.5 text-xs font-medium text-slate-400">Author: Sarala Biswal</div>
          </div>
          <span className="shrink-0 rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-200">
            {llmLabel}
          </span>
        </div>
        <nav className="flex gap-1.5 overflow-x-auto px-6 pb-3 scrollbar-thin" aria-label="Primary">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              // NavLink supplies isActive so the tab styling is driven by the router.
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  navLinkClassName(isNavItemActive(item, isActive, location.pathname))
                }
              >
                <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </header>
      <main className="min-h-0 flex-1 overflow-y-auto px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}

function isNavItemActive(
  item: (typeof navItems)[number],
  routerActive: boolean,
  pathname: string
): boolean {
  if (item.end === true) {
    return pathname === item.to;
  }
  if (item.activePrefix !== undefined) {
    return pathname === item.activePrefix || pathname.startsWith(`${item.activePrefix}/`);
  }
  return routerActive;
}

function navLinkClassName(isActive: boolean): string {
  return [
    "flex h-10 shrink-0 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition",
    isActive
      ? "border-emerald-300/60 bg-emerald-500 text-slate-950 shadow-[0_0_0_2px_rgba(59,130,246,0.7)]"
      : "border-transparent text-slate-300 hover:bg-slate-900 hover:text-white"
  ].join(" ");
}
