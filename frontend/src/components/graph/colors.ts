/** 图谱视觉映射：教材染色 + 关系样式。
 *  与 plan 16 §10 的视觉规则对齐。 */

import type { KnowledgeRelationType } from "@/types/api";

const BOOK_PALETTE = [
  "var(--book-1)",
  "var(--book-2)",
  "var(--book-3)",
  "var(--book-4)",
  "var(--book-5)",
  "var(--book-6)",
  "var(--book-7)",
  "var(--book-8)"
];

const bookHueCache = new Map<string, number>();

/** 给 textbook id 稳定分配一个 0-7 的 hue 索引。 */
export function getBookHue(textbookId: string): number {
  const cached = bookHueCache.get(textbookId);
  if (cached !== undefined) return cached;
  let hash = 0;
  for (let i = 0; i < textbookId.length; i += 1) {
    hash = (hash * 31 + textbookId.charCodeAt(i)) >>> 0;
  }
  const idx = hash % BOOK_PALETTE.length;
  bookHueCache.set(textbookId, idx);
  return idx;
}

export function getBookColor(textbookId: string): string {
  return BOOK_PALETTE[getBookHue(textbookId)];
}

/** 关系类型 → 视觉样式映射。dasharray null 表示实线。 */
export interface RelationStyle {
  /** 边宽（基础值，会再乘 weight） */
  width: number;
  /** 虚线 dasharray，null = 实线 */
  dasharray: string | null;
  /** 是否带箭头 */
  arrow: boolean;
  /** 曲率（0-0.4 间，越大越弯） */
  curvature: number;
  /** 边颜色（默认 border-strong） */
  color: string;
}

const DEFAULT_STYLE: RelationStyle = {
  width: 1.5,
  dasharray: null,
  arrow: false,
  curvature: 0.12,
  color: "var(--border-strong)"
};

const relationStyleMap: Partial<Record<KnowledgeRelationType, RelationStyle>> = {
  PREREQUISITE_OF: { width: 2, dasharray: null, arrow: true, curvature: 0.1, color: "var(--brand-600)" },
  CONTAINS: { width: 2.5, dasharray: null, arrow: false, curvature: 0.06, color: "var(--text-muted)" },
  PART_OF: { width: 2, dasharray: null, arrow: true, curvature: 0.08, color: "var(--text-muted)" },
  PARALLEL_WITH: { width: 1.5, dasharray: "4 3", arrow: false, curvature: 0.18, color: "var(--text-subtle)" },
  APPLIES_TO: { width: 1.5, dasharray: "1 3", arrow: true, curvature: 0.18, color: "var(--brand-500)" },
  IS_A: { width: 2, dasharray: null, arrow: true, curvature: 0.08, color: "var(--text-default)" },
  CAUSES: { width: 2, dasharray: null, arrow: true, curvature: 0.14, color: "var(--status-warning)" },
  LEADS_TO: { width: 2, dasharray: null, arrow: true, curvature: 0.14, color: "var(--status-warning)" },
  EXPLAINS: { width: 1.5, dasharray: "6 3", arrow: false, curvature: 0.18, color: "var(--brand-500)" },
  EVIDENCED_BY: { width: 1.5, dasharray: "1 4", arrow: false, curvature: 0.18, color: "var(--text-subtle)" },
  CONTRASTS_WITH: { width: 1.5, dasharray: "8 4", arrow: false, curvature: 0.22, color: "var(--status-error)" },
  CONFLICTS_WITH: { width: 1.8, dasharray: "8 4", arrow: true, curvature: 0.22, color: "var(--status-error)" },
  REFINES: { width: 1.5, dasharray: "2 3", arrow: true, curvature: 0.14, color: "var(--brand-500)" },
  ALIAS_OF: { width: 1.5, dasharray: null, arrow: false, curvature: 0.04, color: "var(--text-subtle)" },
  SAME_AS: { width: 1.5, dasharray: null, arrow: false, curvature: 0.04, color: "var(--text-subtle)" },
  MENTIONED_IN: { width: 1.5, dasharray: "1 4", arrow: false, curvature: 0.2, color: "var(--text-subtle)" }
};

export function getRelationStyle(relation: KnowledgeRelationType): RelationStyle {
  return relationStyleMap[relation] ?? DEFAULT_STYLE;
}

/** 节点大小：基础 + 频次加成（plan 16 §10 节点映射） */
export function getNodeRadius(frequency: number, nodeType: string): number {
  // 不同类型基础半径不同
  const baseByType: Record<string, number> = {
    Structure: 10,
    Process: 9,
    Function: 8,
    Concept: 9,
    Disease: 11,
    Symptom: 7,
    Treatment: 8,
    Diagnosis: 9,
    Mechanism: 8,
    Experiment: 7,
    Term: 6
  };
  const base = baseByType[nodeType] ?? 8;
  return base + Math.min(frequency, 6) * 1.5;
}

/** 节点类型 → 图标映射（Lucide icon name） */
export function getNodeIcon(nodeType: string): string | null {
  const iconMap: Record<string, string> = {
    Structure: "box",
    Process: "activity",
    Function: "zap",
    Concept: "lightbulb",
    Disease: "alert-circle",
    Symptom: "thermometer",
    Treatment: "pill",
    Diagnosis: "stethoscope",
    Mechanism: "cog",
    Experiment: "flask-conical",
    Term: "tag"
  };
  return iconMap[nodeType] ?? null;
}
