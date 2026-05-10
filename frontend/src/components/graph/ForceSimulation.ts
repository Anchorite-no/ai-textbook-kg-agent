/** D3 force simulation 工厂：与 React 解耦的纯逻辑。 *
 *  调用方：KnowledgeGraph 在 useEffect 里 buildSimulation(nodes, edges)
 *  → sim.on("tick", ...) → 渲染。 */

import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type Simulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum
} from "d3";
import type { KnowledgeEdge, KnowledgeNode } from "@/types/api";
import { getNodeRadius } from "./colors";

export interface SimNode extends SimulationNodeDatum {
  id: string;
  name: string;
  bookId: string;
  nodeType: string;
  confidence: number;
  frequency: number;
  radius: number;
}

export interface SimLink extends SimulationLinkDatum<SimNode> {
  id: string;
  source: string | SimNode;
  target: string | SimNode;
  relation: string;
  weight: number;
}

export interface BuildOptions {
  width: number;
  height: number;
}

export function toSimNodes(nodes: KnowledgeNode[]): SimNode[] {
  return nodes.map((n) => {
    const freq =
      typeof n.metadata === "object" && n.metadata && "frequency" in n.metadata
        ? Number((n.metadata as { frequency?: unknown }).frequency) || 1
        : 1;
    return {
      id: n.id,
      name: n.name,
      bookId: n.source_locator.raw_file_id,
      nodeType: n.node_type,
      confidence: n.confidence,
      frequency: freq,
      radius: getNodeRadius(freq, n.node_type)
    };
  });
}

export function toSimLinks(edges: KnowledgeEdge[]): SimLink[] {
  return edges.map((e) => ({
    id: e.id,
    source: e.source_node_id,
    target: e.target_node_id,
    relation: e.relation_type,
    weight: e.confidence ?? 0.7
  }));
}

export function buildSimulation(
  nodes: SimNode[],
  links: SimLink[],
  { width, height }: BuildOptions
): Simulation<SimNode, SimLink> {
  return forceSimulation<SimNode>(nodes)
    .force(
      "link",
      forceLink<SimNode, SimLink>(links)
        .id((d) => d.id)
        .distance((d) => 120 + (1 - d.weight) * 120)
        .strength((d) => 0.22 + d.weight * 0.28)
    )
    .force(
      "charge",
      forceManyBody<SimNode>().strength((d) => -520 - d.radius * 8)
    )
    .force("center", forceCenter(width / 2, height / 2).strength(0.035))
    .force(
      "collide",
      forceCollide<SimNode>()
        .radius((d) => d.radius + 22)
        .iterations(3)
    )
    .alphaDecay(0.04)
    .velocityDecay(0.3);
}

/** 计算两端节点的曲线控制点，用于 SVG path。 */
export function curvedPath(
  source: { x: number; y: number },
  target: { x: number; y: number },
  curvature: number
): string {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const dr = Math.sqrt(dx * dx + dy * dy) * (1 / Math.max(curvature, 0.01));
  return `M${source.x},${source.y}A${dr},${dr} 0 0,1 ${target.x},${target.y}`;
}
