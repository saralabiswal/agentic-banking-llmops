/**
 * Author: Sarala Biswal
 */
import { AlertCircle, CheckCircle2, Circle, Loader2 } from "lucide-react";
import type { LayerStatus } from "../api/types";

interface LayerStatusBadgeProps {
  status: LayerStatus;
}

const styles: Record<LayerStatus, string> = {
  idle: "border-slate-700 bg-slate-900 text-slate-400",
  active: "border-blue-400/60 bg-blue-500/10 text-blue-200",
  complete: "border-emerald-400/60 bg-emerald-500/10 text-emerald-200",
  error: "border-red-400/60 bg-red-500/10 text-red-200"
};

/**
 * Renders a normalized visual status badge for pipeline layer state.
 */
export default function LayerStatusBadge({ status }: LayerStatusBadgeProps): JSX.Element {
  const Icon =
    status === "complete" ? CheckCircle2 : status === "error" ? AlertCircle : status === "active" ? Loader2 : Circle;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium capitalize ${styles[status]}`}
    >
      <Icon className={`h-3.5 w-3.5 ${status === "active" ? "animate-spin" : ""}`} />
      {status}
    </span>
  );
}
