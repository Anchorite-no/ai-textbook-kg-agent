/** 图谱图例：节点类型 + 边类型。左下角浮层。 */

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import { getRelationStyle } from "./colors";
import { cn } from "@/utils/cn";
import type { KnowledgeRelationType } from "@/types/api";

const NODE_TYPES: Array<{ type: string; label: string; color: string }> = [
  { type: "Structure", label: "结构", color: "var(--book-1)" },
  { type: "Process", label: "过程", color: "var(--book-4)" },
  { type: "Concept", label: "概念", color: "var(--book-2)" },
  { type: "Disease", label: "疾病", color: "var(--book-5)" },
  { type: "Symptom", label: "症状", color: "var(--book-8)" },
  { type: "Treatment", label: "治疗", color: "var(--book-6)" },
  { type: "Mechanism", label: "机制", color: "var(--book-7)" }
];

const EDGE_TYPES: Array<{ type: KnowledgeRelationType; label: string }> = [
  { type: "CONTAINS", label: "包含" },
  { type: "PART_OF", label: "组成" },
  { type: "CAUSES", label: "导致" },
  { type: "LEADS_TO", label: "引起" },
  { type: "PARALLEL_WITH", label: "并列" },
  { type: "APPLIES_TO", label: "作用于" },
  { type: "CONFLICTS_WITH", label: "冲突" },
  { type: "PREREQUISITE_OF", label: "前置" }
];

export function EdgeLegend() {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="absolute left-3 bottom-3 rounded-card border border-border-soft bg-surface-card/95 backdrop-blur-sm shadow-card overflow-hidden" style={{ maxWidth: 200 }}>
      {/* 标题栏（可折叠） */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-[11px] uppercase tracking-wide text-text-muted font-medium hover:bg-surface-input transition-colors"
      >
        <span>图例</span>
        {expanded ? <ChevronDown className="size-3" /> : <ChevronUp className="size-3" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-3">
          {/* 节点类型 */}
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-text-subtle mb-1.5">节点类型</h4>
            <div className="flex flex-col gap-1">
              {NODE_TYPES.map(({ type, label, color }) => (
                <div key={type} className="flex items-center gap-2">
                  <span
                    className="inline-block size-3 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="text-meta text-text-default">{label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 分隔线 */}
          <div className="h-px bg-border-soft" />

          {/* 边类型 */}
          <div>
            <h4 className="text-[10px] uppercase tracking-wider text-text-subtle mb-1.5">关系类型</h4>
            <div className="flex flex-col gap-1">
              {EDGE_TYPES.map(({ type, label }) => {
                const style = getRelationStyle(type);
                return (
                  <div key={type} className="flex items-center gap-2">
                    <svg width="24" height="10" className="shrink-0">
                      <line
                        x1="0"
                        y1="5"
                        x2="24"
                        y2="5"
                        stroke={style.color}
                        strokeWidth={Math.max(1.5, style.width)}
                        strokeDasharray={style.dasharray ?? undefined}
                      />
                      {style.arrow && (
                        <polygon points="20,2 24,5 20,8" fill={style.color} />
                      )}
                    </svg>
                    <span className="text-meta text-text-default">{label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
