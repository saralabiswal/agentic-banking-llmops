/**
 * Author: Sarala Biswal
 */
import type { Edge, EdgeProps } from "@xyflow/react";
import { getBezierPath } from "@xyflow/react";
import { usePipelineStore } from "../hooks/usePipelineStore";

export interface DataFlowEdgeData extends Record<string, unknown> {
  label: string;
}

export type DataFlowEdgeType = Edge<DataFlowEdgeData, "dataFlow">;

/**
 * Renders directional data movement between architecture nodes.
 */
export default function DataFlowEdge({
  id,
  source,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data
}: EdgeProps<DataFlowEdgeType>): JSX.Element {
  const sourceStatus = usePipelineStore((store) => store.layerStates[source]?.status);
  const animated = source === "trigger" || sourceStatus === "complete";
  const [edgePath] = getBezierPath({ sourceX, sourceY, sourcePosition, targetX, targetY, targetPosition });

  return (
    <g className={animated ? "text-emerald-300" : "text-slate-600"} data-testid="architecture-edge">
      <path
        className={`fill-none stroke-current ${animated ? "stroke-2 [stroke-dasharray:8_8]" : "stroke"}`}
        d={edgePath}
        id={id}
      />
      <text className="fill-current text-[10px] font-medium">
        <textPath href={`#${id}`} startOffset="50%" textAnchor="middle">
          {data?.label ?? ""}
        </textPath>
      </text>
    </g>
  );
}
