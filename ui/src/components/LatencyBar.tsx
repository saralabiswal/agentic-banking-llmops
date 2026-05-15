/**
 * Author: Sarala Biswal
 */
interface LatencyBarProps {
  latencyMs: number | null;
  maxMs?: number;
}

/**
 * Renders a compact latency meter for layer execution timing.
 */
export default function LatencyBar({ latencyMs, maxMs = 250 }: LatencyBarProps): JSX.Element {
  const value = latencyMs ?? 0;
  const width = Math.min(100, Math.round((value / maxMs) * 100));
  const widthClass =
    width >= 95
      ? "w-full"
      : width >= 75
        ? "w-3/4"
        : width >= 50
          ? "w-1/2"
          : width >= 25
            ? "w-1/4"
            : width > 0
              ? "w-1/12"
              : "w-0";

  return (
    <div className="flex w-full items-center gap-3">
      <div className="h-2 flex-1 overflow-hidden rounded-sm bg-slate-800">
        <div className={`h-full bg-emerald-400 transition-all ${widthClass}`} />
      </div>
      <span className="w-16 text-right text-xs tabular-nums text-slate-400">{latencyMs ?? 0}ms</span>
    </div>
  );
}
