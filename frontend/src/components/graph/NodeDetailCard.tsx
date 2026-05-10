import { useMemo, useState, Fragment } from "react";
import { BookOpen, ChevronDown, ChevronRight, X } from "lucide-react";
import { IconButton, Tag, Tooltip, Skeleton } from "@/components/_kit";
import { cn } from "@/utils/cn";
import { useNodeDetailQuery, useGraphQuery } from "@/hooks/useGraph";
import { useUIStore } from "@/store/uiStore";
import { getBookColor } from "./colors";
import type { KnowledgeEdge } from "@/types/api";

export interface NodeDetailCardProps {
  nodeId: string;
  onClose: () => void;
}

type RelGroup =
  | "contains"
  | "structure"
  | "causal"
  | "refine"
  | "apply"
  | "explain"
  | "contrast"
  | "alias"
  | "other";

interface GroupedEdge {
  otherId: string;
  otherName: string;
  relation: string;
  outgoing: boolean;
}

const GROUP_ORDER: RelGroup[] = [
  "contains", "structure", "refine", "causal",
  "apply", "explain", "contrast", "alias", "other"
];

function classifyRelation(rel: string, outgoing: boolean): RelGroup {
  switch (rel) {
    case "CONTAINS": return outgoing ? "contains" : "structure";
    case "PART_OF": return outgoing ? "structure" : "contains";
    case "IS_A": return "structure";
    case "CAUSES":
    case "LEADS_TO": return "causal";
    case "REFINES": return "refine";
    case "APPLIES_TO": return "apply";
    case "EXPLAINS":
    case "EVIDENCED_BY":
    case "MENTIONED_IN": return "explain";
    case "PREREQUISITE_OF": return outgoing ? "structure" : "causal";
    case "CONTRASTS_WITH":
    case "CONFLICTS_WITH": return "contrast";
    case "PARALLEL_WITH": return "refine";
    case "ALIAS_OF":
    case "SAME_AS": return "alias";
    default: return "other";
  }
}

function buildProse(
  group: RelGroup,
  items: GroupedEdge[],
  nodeName: string
): { heading: string; template: (names: React.ReactNode[]) => React.ReactNode } | null {
  if (items.length === 0) return null;
  const names = items.map((i) => i.otherName);

  const map: Record<RelGroup, { heading: string; text: string }> = {
    contains: {
      heading: "组成结构",
      text: `${nodeName}包含以下主要组成部分：`
    },
    structure: {
      heading: "所属与分类",
      text: `${nodeName}是以下结构或概念的组成部分：`
    },
    causal: {
      heading: "因果关联",
      text: items.every((i) => i.outgoing)
        ? `${nodeName}可导致或进展为：`
        : items.every((i) => !i.outgoing)
          ? `以下因素可导致${nodeName}：`
          : `${nodeName}与以下因素存在因果关联：`
    },
    refine: {
      heading: "细化与并列",
      text: items.some((i) => i.relation === "PARALLEL_WITH")
        ? `${nodeName}与以下概念存在并列或细化关系：`
        : `${nodeName}可进一步细分为：`
    },
    apply: {
      heading: "应用场景",
      text: items.every((i) => i.outgoing)
        ? `${nodeName}可应用于以下领域：`
        : `以下手段可应用于${nodeName}的诊疗：`
    },
    explain: {
      heading: "解释与依据",
      text: `${nodeName}的相关机制或证据涉及：`
    },
    contrast: {
      heading: "对比与冲突",
      text: `${nodeName}与以下概念存在对比或冲突：`
    },
    alias: {
      heading: "同义表述",
      text: `${nodeName}也被称为：`
    },
    other: {
      heading: "其他关联",
      text: `${nodeName}还与以下知识点相关：`
    }
  };

  const entry = map[group];
  if (!entry) return null;
  if (names.length === 0) return null;

  return {
    heading: entry.heading,
    template: (nodeLinks) => (
      <>{entry.text}{nodeLinks}</>
    )
  };
}

export function NodeDetailCard({ nodeId, onClose }: NodeDetailCardProps) {
  const { data, isLoading, error } = useNodeDetailQuery(nodeId);
  const { data: graphData } = useGraphQuery();
  const setSelectedNodeId = useUIStore((s) => s.setSelectedNodeId);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const nodeNameMap = useMemo(() => {
    const map = new Map<string, string>();
    graphData?.nodes?.forEach((n) => map.set(n.id, n.name));
    data?.related_nodes?.forEach((n) => map.set(n.id, n.name));
    if (data?.node) map.set(data.node.id, data.node.name);
    return map;
  }, [data?.node, data?.related_nodes, graphData?.nodes]);

  const node = data?.node ?? null;
  const edges = data?.edges ?? [];
  const chunks = data?.evidence_chunks ?? [];

  const grouped = useMemo(() => {
    const groups = new Map<RelGroup, GroupedEdge[]>();
    for (const g of GROUP_ORDER) groups.set(g, []);

    for (const edge of edges) {
      const outgoing = edge.source_node_id === nodeId;
      const otherId = outgoing ? edge.target_node_id : edge.source_node_id;
      const otherName = nodeNameMap.get(otherId) ?? "相关知识点";
      const group = classifyRelation(edge.relation_type, outgoing);
      groups.get(group)!.push({
        otherId,
        otherName,
        relation: edge.relation_type,
        outgoing
      });
    }
    return groups;
  }, [edges, nodeId, nodeNameMap]);

  if (isLoading) {
    return (
      <div className="flex flex-col flex-1 min-h-0 animate-fade-in-up">
        <div className="px-4 py-3 border-b border-border-soft flex items-center justify-between">
          <Skeleton width={180} height={18} rounded="control" />
          <IconButton label="关闭" size="sm" icon={<X />} onClick={onClose} />
        </div>
        <div className="p-4 flex flex-col gap-3">
          <Skeleton width="90%" height={14} rounded="control" />
          <Skeleton width="100%" height={12} rounded="control" />
          <Skeleton width="100%" height={12} rounded="control" />
          <Skeleton width="75%" height={12} rounded="control" />
          <div className="mt-2" />
          <Skeleton width="60%" height={12} rounded="control" />
          <Skeleton width="100%" height={12} rounded="control" />
          <Skeleton width="85%" height={12} rounded="control" />
        </div>
      </div>
    );
  }

  if (error || !node) {
    return (
      <div className="flex flex-col flex-1 min-h-0 items-center justify-center gap-2 p-6">
        <p className="text-meta text-status-error">
          {error instanceof Error ? error.message : "节点未找到"}
        </p>
        <button
          className="text-meta text-brand-600 hover:underline"
          onClick={onClose}
        >
          返回
        </button>
      </div>
    );
  }

  return (
    <div
      className="flex flex-col flex-1 min-h-0 animate-fade-in-up"
      role="region"
      aria-label={`${node.name} 知识卡片`}
      onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border-soft flex items-start gap-2 shrink-0 bg-surface-card">
        <span
          className="mt-1.5 inline-block size-2.5 rounded-full shrink-0"
          style={{ backgroundColor: getBookColor(node.source_locator.raw_file_id) }}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <h2 className="text-[15px] font-semibold text-text-strong leading-snug">
            {node.name}
          </h2>
          <div className="flex items-center gap-2 mt-0.5">
            <Tag size="sm" variant="brand">{node.node_type}</Tag>
            <span className="text-[11px] text-text-muted tabular">
              {node.source_locator.locator_text}
            </span>
          </div>
        </div>
        <Tooltip content="关闭（ESC）">
          <IconButton
            label="关闭"
            tooltip={false}
            size="sm"
            icon={<X />}
            onClick={onClose}
          />
        </Tooltip>
      </div>

      {/* Textbook-style body */}
      <div className="scroll-region flex-1 min-h-0 overflow-y-auto">
        <article className="px-4 py-4 flex flex-col gap-4 text-[13px] text-text-default leading-[1.75]">
          {/* Definition — opening paragraph */}
          {node.definition ? (
            <p>
              <strong>{node.name}</strong>
              {node.definition.startsWith(node.name) ? node.definition.slice(node.name.length) : `是${node.definition}`}
              {node.aliases?.length ? (
                <span className="text-text-muted">
                  （又称{node.aliases.join("、")}）
                </span>
              ) : null}
            </p>
          ) : node.aliases?.length ? (
            <p>
              <strong>{node.name}</strong>
              <span className="text-text-muted">
                （又称{node.aliases.join("、")}）
              </span>
            </p>
          ) : null}

          {/* Prose paragraphs from edges */}
          {GROUP_ORDER.map((group) => {
            const items = grouped.get(group);
            if (!items || items.length === 0) return null;
            const prose = buildProse(group, items, node.name);
            if (!prose) return null;

            const nodeLinks = items.map((item, i) => (
              <Fragment key={item.otherId}>
                {i > 0 && (i === items.length - 1 ? "和" : "、")}
                <NodeLink
                  name={item.otherName}
                  onClick={() => setSelectedNodeId(item.otherId)}
                />
              </Fragment>
            ));

            return (
              <div key={group} className="flex flex-col gap-1">
                <h3 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
                  {prose.heading}
                </h3>
                <p>{prose.template(nodeLinks)}。</p>
              </div>
            );
          })}

          {/* Evidence chunks — collapsed by default */}
          {chunks.length > 0 ? (
            <div className="border-t border-border-soft pt-3 mt-1">
              <button
                className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-text-muted font-medium hover:text-text-default transition-colors"
                onClick={() => setEvidenceOpen(!evidenceOpen)}
              >
                {evidenceOpen ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
                原文摘录（{chunks.length}）
              </button>
              {evidenceOpen ? (
                <div className="mt-2 flex flex-col gap-2">
                  {chunks.map((chunk) => (
                    <blockquote
                      key={chunk.id}
                      className="pl-3 border-l-2 border-brand-200 text-[12px] text-text-muted leading-relaxed"
                    >
                      {chunk.text}
                      <cite className="block mt-0.5 text-[11px] text-text-subtle not-italic">
                        — {chunk.source_locator.locator_text}
                      </cite>
                    </blockquote>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </article>

        {/* Source footer */}
        <div className="px-4 pb-3">
          <div className="flex items-center gap-2 p-2 rounded-control bg-surface-input text-[11px] text-text-muted">
            <BookOpen className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{node.source_locator.locator_text}</span>
            <span className="ml-auto tabular shrink-0">
              置信度 {(node.confidence * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function NodeLink({ name, onClick }: { name: string; onClick: () => void }) {
  return (
    <button
      className={cn(
        "inline text-brand-600 font-medium",
        "underline decoration-brand-200 underline-offset-2",
        "hover:decoration-brand-500 hover:text-brand-700",
        "transition-colors duration-micro cursor-pointer"
      )}
      onClick={(e) => { e.stopPropagation(); onClick(); }}
    >
      {name}
    </button>
  );
}
