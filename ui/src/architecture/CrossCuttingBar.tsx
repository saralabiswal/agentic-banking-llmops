/**
 * Author: Sarala Biswal
 */
interface CrossCuttingBarProps {
  label: string;
  side: "left" | "right";
}

/**
 * Renders a cross-cutting architecture concern in the React Flow diagram.
 */
export default function CrossCuttingBar({ label, side }: CrossCuttingBarProps): JSX.Element {
  const accentBorder =
    side === "left"
      ? "border-l-2 border-l-orange-500 border-t border-r border-b border-slate-700"
      : "border-r-2 border-r-violet-500 border-t border-l border-b border-slate-700";

  const textColor = side === "left" ? "text-orange-400" : "text-violet-400";
  const bg = side === "left" ? "bg-orange-500/5" : "bg-violet-500/5";

  return (
    <div
      className={[
        "pointer-events-none absolute top-[132px] z-10 flex h-[565px] w-14 items-center justify-center rounded-md",
        accentBorder,
        bg,
        side === "left" ? "left-2" : "right-2"
      ].join(" ")}
      data-testid="cross-cutting-bar"
    >
      <div className="flex flex-col items-center gap-2">
        <span
          className={[
            "-rotate-90 whitespace-nowrap text-[9px] font-bold uppercase tracking-widest",
            textColor
          ].join(" ")}
        >
          {label}
        </span>
        {[0, 1, 2].map((index) => (
          <div
            className={[
              "h-1.5 w-1.5 rounded-full opacity-40",
              side === "left" ? "bg-orange-400" : "bg-violet-400"
            ].join(" ")}
            key={index}
          />
        ))}
      </div>
    </div>
  );
}
