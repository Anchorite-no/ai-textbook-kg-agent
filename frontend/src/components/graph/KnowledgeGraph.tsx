/** KnowledgeGraph：D3 全权渲染力图。
 *  参照 ExpensePro CustomOrganicNetwork 实现：
 *  - D3 直接操作 DOM（不通过 React 状态驱动 tick）
 *  - zoom 绑定到 SVG，drag 绑定到节点 g，D3 自动分离事件
 *  - 稳定后 auto-fit 到画布中心
 *  - 重置视图回到 auto-fit 时的 transform */

import { useEffect, useMemo, useRef, useState } from "react";
import * as d3 from "d3";
import { EmptyState, ErrorState, Skeleton } from "@/components/_kit";
import { cn } from "@/utils/cn";
import {
  toSimLinks,
  toSimNodes,
  curvedPath,
  type SimLink,
  type SimNode
} from "./ForceSimulation";
import { getBookColor, getRelationStyle } from "./colors";
import type { KnowledgeEdge, KnowledgeNode } from "@/types/api";

export interface KnowledgeGraphProps {
  nodes: KnowledgeNode[] | undefined;
  edges: KnowledgeEdge[] | undefined;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  selectedNodeId: string | null;
  onSelect: (nodeId: string | null) => void;
}

export function KnowledgeGraph({
  nodes,
  edges,
  loading,
  error,
  onRetry,
  selectedNodeId,
  onSelect
}: KnowledgeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const gRef = useRef<SVGGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const initialTransformRef = useRef<d3.ZoomTransform | null>(null);
  const simulationRef = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const sizeRef = useRef({ width: 800, height: 600 });
  const [svgSize, setSvgSize] = useState({ width: 800, height: 600 });

  // 监听容器尺寸：写入 ref（不触发 D3 重建）+ debounce 更新 SVG 尺寸
  useEffect(() => {
    if (!containerRef.current) return;
    let timer: ReturnType<typeof setTimeout>;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) {
        sizeRef.current = { width, height };
        // debounce SVG 尺寸更新（仅影响 SVG width/height 属性，不触发 D3 重建）
        clearTimeout(timer);
        timer = setTimeout(() => setSvgSize({ width, height }), 150);
      }
    });
    observer.observe(containerRef.current);
    return () => { observer.disconnect(); clearTimeout(timer); };
  }, []);

  // 计算 simulation 所需数据
  const simData = useMemo(() => {
    if (!nodes || !edges || nodes.length === 0) return null;
    return {
      nodes: toSimNodes(nodes),
      links: toSimLinks(edges)
    };
  }, [nodes, edges]);

  // 稳定引用 onSelect，避免 effect 无限循环
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // D3 全权管理渲染（仅在数据变化时重建，不因容器尺寸变化重建）
  useEffect(() => {
    if (!svgRef.current || !gRef.current || !simData || simData.nodes.length === 0) return;

    const { width, height } = sizeRef.current;
    const centerX = width / 2;
    const centerY = height / 2;

    // 深拷贝（D3 会原地修改）
    const simNodes: SimNode[] = simData.nodes.map((n) => ({ ...n }));
    const simLinks: SimLink[] = simData.links.map((l) => ({ ...l }));

    // 邻接表（悬停高亮用）
    const adjacency = new Map<string, Set<string>>();
    simNodes.forEach((n) => adjacency.set(n.id, new Set()));
    simLinks.forEach((l) => {
      const sId = typeof l.source === "string" ? l.source : (l.source as SimNode).id;
      const tId = typeof l.target === "string" ? l.target : (l.target as SimNode).id;
      adjacency.get(sId)?.add(tId);
      adjacency.get(tId)?.add(sId);
    });

    const svg = d3.select(svgRef.current);
    const g = d3.select(gRef.current);
    g.selectAll("*").remove();

    // ---- Zoom：绑定到 SVG，控制 <g> 的 transform ----
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.25, 5])
      .on("zoom", (event) => {
        g.attr("transform", event.transform.toString());
      });

    zoomRef.current = zoom;
    svg.call(zoom).on("dblclick.zoom", null);

    // 阻止默认滚轮滚动
    svg.on("wheel.prevent", (event) => {
      event.preventDefault();
    });

    // ---- Defs: 箭头 ----
    const defs = g.append("defs");
    defs.append("marker")
      .attr("id", "arrow-default")
      .attr("viewBox", "0 -4 8 8")
      .attr("refX", 12)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-4L8,0L0,4")
      .attr("fill", "var(--text-muted)");

    // ---- 绘制边（默认不显示箭头，hover 时才加） ----
    const linkSel = g.selectAll<SVGPathElement, SimLink>(".graph-link")
      .data(simLinks)
      .enter()
      .append("path")
      .attr("class", "graph-link")
      .attr("fill", "none")
      .each(function (d) {
        const style = getRelationStyle(d.relation as never);
        d3.select(this)
          .attr("stroke", style.color)
          .attr("stroke-width", style.width)
          .attr("stroke-dasharray", style.dasharray ?? "")
          .attr("stroke-opacity", 0.45)
          .attr("marker-end", "");
      });

    // ---- 绘制节点 ----
    const nodeSel = g.selectAll<SVGGElement, SimNode>(".graph-node")
      .data(simNodes, (d) => d.id)
      .enter()
      .append("g")
      .attr("class", "graph-node")
      .style("cursor", "grab");

    // 主圆
    nodeSel.append("circle")
      .attr("class", "node-circle")
      .attr("r", (d) => d.radius)
      .attr("fill", (d) => getBookColor(d.bookId))
      .attr("fill-opacity", 0.92)
      .attr("stroke", "var(--surface-card)")
      .attr("stroke-width", 1.5)
      .style("filter", "drop-shadow(0 2px 4px rgba(0,0,0,0.12))")
      .style("transform-origin", "center")
      .style("transform-box", "fill-box");

    // 呼吸动画
    if (simNodes.length <= 200) {
      nodeSel.each(function () {
        const dur = 3 + Math.random() * 2;
        const delay = Math.random() * 2;
        d3.select(this).select(".node-circle")
          .style("animation", `breathing ${dur.toFixed(1)}s ease-in-out ${delay.toFixed(1)}s infinite`);
      });
    }

    // 标签
    nodeSel.append("text")
      .attr("x", (d) => d.radius + 5)
      .attr("y", 4)
      .attr("font-size", 11)
      .attr("fill", "var(--text-default)")
      .attr("pointer-events", "none")
      .attr("user-select", "none")
      .text((d) => (d.frequency >= 3 ? d.name : ""));

    // title tooltip
    nodeSel.append("title")
      .text((d) => `${d.name}（${d.nodeType}，置信度 ${(d.confidence * 100).toFixed(0)}%）`);

    // ---- BFS 知识链高亮 ----
    const MAX_HOPS = 2;
    let highlightedId: string | null = null;
    let draggingId: string | null = null;

    function bfsDepthMap(startId: string, maxDepth: number): Map<string, number> {
      const depth = new Map<string, number>();
      depth.set(startId, 0);
      const queue = [startId];
      let head = 0;
      while (head < queue.length) {
        const cur = queue[head++];
        const d = depth.get(cur)!;
        if (d >= maxDepth) continue;
        for (const neighbor of adjacency.get(cur) ?? []) {
          if (!depth.has(neighbor)) {
            depth.set(neighbor, d + 1);
            queue.push(neighbor);
          }
        }
      }
      return depth;
    }

    function applyHighlight(nodeId: string) {
      highlightedId = nodeId;
      const depthMap = bfsDepthMap(nodeId, MAX_HOPS);
      const hopOpacity = [1, 0.7, 0.4];

      nodeSel.each(function (n) {
        const hop = depthMap.get(n.id);
        d3.select(this).style("opacity", hop !== undefined ? hopOpacity[hop] ?? 0.4 : 0.08);
      });

      linkSel.each(function (l) {
        const sId = typeof l.source === "object" ? (l.source as SimNode).id : l.source;
        const tId = typeof l.target === "object" ? (l.target as SimNode).id : l.target;
        const sHop = depthMap.get(sId);
        const tHop = depthMap.get(tId);
        const onChain = sHop !== undefined && tHop !== undefined && Math.abs(sHop - tHop) <= 1;
        if (onChain) {
          const maxHop = Math.max(sHop, tHop);
          const style = getRelationStyle(l.relation as never);
          d3.select(this)
            .attr("stroke-opacity", maxHop <= 1 ? 0.9 : 0.5)
            .attr("marker-end", style.arrow ? "url(#arrow-default)" : "");
        } else {
          d3.select(this)
            .attr("stroke-opacity", 0.03)
            .attr("marker-end", "");
        }
      });

      nodeSel.select("text").text((n) => {
        const hop = depthMap.get(n.id);
        if (hop !== undefined && hop <= 1) return n.name;
        return n.frequency >= 3 ? n.name : "";
      });
    }

    function clearHighlight() {
      highlightedId = null;
      nodeSel.style("opacity", 1);
      linkSel.each(function () {
        d3.select(this)
          .attr("stroke-opacity", 0.45)
          .attr("marker-end", "");
      });
      nodeSel.select("text").text((n) => (n.frequency >= 3 ? n.name : ""));
    }

    // ---- 悬停高亮（拖拽期间锁定，不受 mouseenter/mouseleave 干扰） ----
    nodeSel
      .on("mouseenter", function (_event, d) {
        if (draggingId) return;
        applyHighlight(d.id);
      })
      .on("mouseleave", function () {
        if (draggingId) return;
        clearHighlight();
      })
      .on("click", function (_event, d) {
        _event.stopPropagation();
        onSelectRef.current(d.id);
      });

    // 背景点击取消选中
    svg.on("click.deselect", (event) => {
      if (event.target === svgRef.current) {
        onSelectRef.current(null);
      }
    });

    // 双击空白处 auto-fit
    svg.on("dblclick", (event) => {
      if (event.target === svgRef.current || event.target === gRef.current) {
        const t = initialTransformRef.current || d3.zoomIdentity;
        svg.transition().duration(400).call(zoom.transform, t);
      }
    });

    // ---- Force Simulation ----
    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force(
        "link",
        d3.forceLink<SimNode, SimLink>(simLinks)
          .id((d) => d.id)
          .distance((d) => 120 + (1 - d.weight) * 120)
          .strength((d) => 0.22 + d.weight * 0.28)
      )
      .force("charge", d3.forceManyBody<SimNode>().strength((d) => -520 - d.radius * 8))
      .force("x", d3.forceX<SimNode>(centerX).strength(0.025))
      .force("y", d3.forceY<SimNode>(centerY).strength(0.025))
      .force("collide", d3.forceCollide<SimNode>().radius((d) => d.radius + 22).iterations(3));

    simulationRef.current = simulation;

    let fitted = false;

    simulation.on("tick", () => {
      // 更新边
      linkSel.attr("d", (d) => {
        const s = d.source as SimNode;
        const t = d.target as SimNode;
        const style = getRelationStyle(d.relation as never);
        return curvedPath(
          { x: s.x ?? 0, y: s.y ?? 0 },
          { x: t.x ?? 0, y: t.y ?? 0 },
          style.curvature
        );
      });

      // 更新节点位置
      nodeSel.attr("transform", (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);

      // 稳定后 auto-fit 到画布中心（放大显示，不需要看到全部节点）
      if (!fitted && simulation.alpha() < 0.08 && simNodes.length > 0) {
        // 安全检查：所有节点必须有有效坐标
        const allValid = simNodes.every(
          (n) => Number.isFinite(n.x) && Number.isFinite(n.y)
        );
        if (!allValid) return;

        fitted = true;
        const curSize = sizeRef.current;
        const pad = 40;
        const x0 = Math.min(...simNodes.map((n) => (n.x!) - n.radius)) - pad;
        const y0 = Math.min(...simNodes.map((n) => (n.y!) - n.radius)) - pad;
        const x1 = Math.max(...simNodes.map((n) => (n.x!) + n.radius)) + pad;
        const y1 = Math.max(...simNodes.map((n) => (n.y!) + n.radius)) + pad;
        const bw = x1 - x0;
        const bh = y1 - y0;
        if (bw > 0 && bh > 0) {
          let scale = Math.min(curSize.width / bw, curSize.height / bh) * 0.85;
          scale = Math.max(scale, 1.0);
          scale = Math.min(scale, 2.5);
          const tx = curSize.width / 2 - ((x0 + x1) / 2) * scale;
          const ty = curSize.height / 2 - ((y0 + y1) / 2) * scale;
          const transform = d3.zoomIdentity.translate(tx, ty).scale(scale);
          initialTransformRef.current = transform;
          svg.transition().duration(600).call(zoom.transform, transform);
        }
      }
    });

    // ---- Drag：绑定到节点 g，D3 自动和 zoom 分离 ----
    const drag = d3.drag<SVGGElement, SimNode>()
      .on("start", function (event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
        draggingId = d.id;
        applyHighlight(d.id);
        d3.select(this).style("cursor", "grabbing");
      })
      .on("drag", function (_event, d) {
        d.fx = _event.x;
        d.fy = _event.y;
      })
      .on("end", function (event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
        draggingId = null;
        clearHighlight();
        d3.select(this).style("cursor", "grab");
      });

    nodeSel.call(drag);

    // ---- 监听外部重置事件 ----
    function onReset() {
      if (initialTransformRef.current) {
        svg.transition().duration(400).call(zoom.transform, initialTransformRef.current);
        return;
      }
      const curSize = sizeRef.current;
      const pad = 40;
      const xs = simNodes.map((n) => n.x ?? 0);
      const ys = simNodes.map((n) => n.y ?? 0);
      const rs = simNodes.map((n) => n.radius);
      const x0 = Math.min(...xs.map((x, i) => x - rs[i])) - pad;
      const y0 = Math.min(...ys.map((y, i) => y - rs[i])) - pad;
      const x1 = Math.max(...xs.map((x, i) => x + rs[i])) + pad;
      const y1 = Math.max(...ys.map((y, i) => y + rs[i])) + pad;
      const bw = x1 - x0;
      const bh = y1 - y0;
      if (bw > 0 && bh > 0) {
        let s = Math.min(curSize.width / bw, curSize.height / bh) * 0.85;
        s = Math.max(s, 1.0);
        s = Math.min(s, 2.5);
        const tx = curSize.width / 2 - ((x0 + x1) / 2) * s;
        const ty = curSize.height / 2 - ((y0 + y1) / 2) * s;
        const t = d3.zoomIdentity.translate(tx, ty).scale(s);
        initialTransformRef.current = t;
        svg.transition().duration(400).call(zoom.transform, t);
      }
    }
    window.addEventListener("graph:reset", onReset);

    return () => {
      simulation.stop();
      svg.on(".zoom", null);
      svg.on("click.deselect", null);
      svg.on("dblclick", null);
      svg.on("wheel.prevent", null);
      window.removeEventListener("graph:reset", onReset);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [simData]);

  // 五状态
  if (loading) {
    return (
      <div className="flex-1 grid-bg flex items-center justify-center">
        <div className="flex flex-col gap-3 items-center">
          <Skeleton width={120} height={120} rounded="full" />
          <Skeleton width={200} height={12} rounded="control" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex-1 grid-bg flex items-center justify-center p-6">
        <ErrorState title="图谱加载失败" description={error} onRetry={onRetry} />
      </div>
    );
  }

  if (!simData || simData.nodes.length === 0) {
    return (
      <div className="flex-1 grid-bg flex items-center justify-center">
        <EmptyState
          title="导入教材并构建图谱后显示"
          description="工作台中央保留给力导向图谱。"
        />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex-1 relative overflow-hidden grid-bg">
      <svg
        ref={svgRef}
        width={svgSize.width}
        height={svgSize.height}
        className="block w-full h-full"
        style={{ cursor: "grab" }}
      >
        <g ref={gRef} />
      </svg>

      {/* 节点/边计数浮条 */}
      <div
        className={cn(
          "absolute bottom-3 right-3 flex items-center gap-2 text-meta tabular text-text-muted",
          "bg-surface-overlay backdrop-blur-sm rounded-pill px-2.5 py-1 shadow-card"
        )}
      >
        <span>{simData.nodes.length} 节点</span>
        <span className="text-text-subtle">·</span>
        <span>{simData.links.length} 边</span>
      </div>
    </div>
  );
}
