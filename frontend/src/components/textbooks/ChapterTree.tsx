import { ChevronRight, FileText, Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import { cn } from "@/utils/cn";
import { EmptyState, Tag } from "@/components/_kit";
import { useTextbookDetailQuery } from "@/hooks/useTextbooks";
import type { Section } from "@/types/api";

export interface ChapterTreeProps {
  textbookId: string | null;
}

interface SectionNode {
  section: Section;
  children: SectionNode[];
  chunkCount: number;
}

export function ChapterTree({ textbookId }: ChapterTreeProps) {
  const { data, isLoading, error } = useTextbookDetailQuery(textbookId);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);

  const chunkCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const chunk of data?.chunks ?? []) {
      counts.set(chunk.section_id, (counts.get(chunk.section_id) ?? 0) + 1);
    }
    return counts;
  }, [data?.chunks]);

  const tree = useMemo(() => buildSectionTree(data?.sections ?? [], chunkCounts), [data?.sections, chunkCounts]);
  const selectedSection = data?.sections.find((section) => section.id === selectedSectionId) ?? null;
  const selectedChunks = selectedSection
    ? data?.chunks.filter((chunk) => chunk.section_id === selectedSection.id).slice(0, 2) ?? []
    : [];

  if (!textbookId) {
    return (
      <div className="p-3">
        <EmptyState
          compact
          icon={<FileText />}
          title="选择教材查看章节"
          description="点击左侧教材列表中的任意一本。"
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="p-3 flex items-center gap-2 text-meta text-text-muted">
        <Loader2 className="size-3.5 animate-spin" />
        正在读取教材结构…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-3">
        <EmptyState compact icon={<FileText />} title="教材结构读取失败" description={error instanceof Error ? error.message : "请稍后重试。"} />
      </div>
    );
  }

  return (
    <div className="p-2">
      <div className="mb-2 flex items-center gap-2 px-1 text-meta text-text-muted">
        <span>{data.sections.length.toLocaleString()} 章节</span>
        <span className="text-text-subtle">·</span>
        <span>{data.chunks.length.toLocaleString()} chunks</span>
      </div>
      <div className="flex flex-col gap-0.5">
        {tree.slice(0, 260).map((node) => (
          <SectionTreeNode
            key={node.section.id}
            node={node}
            selectedId={selectedSectionId}
            onSelect={setSelectedSectionId}
          />
        ))}
      </div>
      {tree.length > 260 ? (
        <p className="px-2 py-2 text-[11px] text-text-subtle">仅显示前 260 个章节，完整内容仍可由 RAG/GraphRAG 检索。</p>
      ) : null}
      {selectedSection ? (
        <div className="mt-3 rounded-card border border-border-soft bg-surface-card p-2">
          <div className="flex items-center gap-2">
            <h4 className="text-meta font-medium text-text-strong truncate">{selectedSection.title}</h4>
            <Tag size="sm" variant="outline" className="ml-auto">{selectedChunks.length || chunkCounts.get(selectedSection.id) || 0} chunks</Tag>
          </div>
          <p className="mt-1 text-[11px] text-text-muted truncate">{selectedSection.source_locator.locator_text}</p>
          {selectedChunks.length ? (
            <div className="mt-2 flex flex-col gap-1.5">
              {selectedChunks.map((chunk) => (
                <blockquote key={chunk.id} className="text-[12px] text-text-muted leading-relaxed line-clamp-3 border-l-2 border-brand-200 pl-2">
                  {chunk.text}
                </blockquote>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function SectionTreeNode({
  node,
  selectedId,
  onSelect
}: {
  node: SectionNode;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const [open, setOpen] = useState(node.section.level <= 1);
  const hasChildren = node.children.length > 0;
  const selected = selectedId === node.section.id;

  return (
    <Collapsible.Root open={open} onOpenChange={setOpen}>
      <div
        className={cn(
          "group flex items-center gap-1.5 px-2 py-1.5 rounded-control text-left",
          "text-meta transition-colors duration-micro",
          selected ? "bg-brand-50 text-brand-800" : "text-text-default hover:bg-surface-input"
        )}
        style={{ paddingLeft: `${Math.max(0, node.section.level - 1) * 12 + 8}px` }}
      >
        <Collapsible.Trigger asChild>
          <button
            className="size-4 inline-flex items-center justify-center rounded-control hover:bg-surface-card shrink-0"
            aria-label={open ? "折叠章节" : "展开章节"}
            disabled={!hasChildren}
          >
            {hasChildren ? (
              <ChevronRight className={cn("size-3 text-text-subtle transition-transform duration-micro", open && "rotate-90")} />
            ) : (
              <span className="size-3" />
            )}
          </button>
        </Collapsible.Trigger>
        <button className="min-w-0 flex-1 text-left truncate" onClick={() => onSelect(node.section.id)}>
          {node.section.title}
        </button>
        <span className="text-[11px] text-text-subtle tabular shrink-0">{node.chunkCount}</span>
      </div>
      {hasChildren ? (
        <Collapsible.Content className="flex flex-col gap-0.5">
          {node.children.map((child) => (
            <SectionTreeNode key={child.section.id} node={child} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </Collapsible.Content>
      ) : null}
    </Collapsible.Root>
  );
}

function buildSectionTree(sections: Section[], chunkCounts: Map<string, number>): SectionNode[] {
  const nodes = new Map<string, SectionNode>();
  for (const section of sections) {
    nodes.set(section.id, {
      section,
      children: [],
      chunkCount: chunkCounts.get(section.id) ?? 0
    });
  }

  const roots: SectionNode[] = [];
  for (const node of nodes.values()) {
    const parentId = node.section.parent_section_id;
    const parent = parentId ? nodes.get(parentId) : null;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }

  const sortNodes = (items: SectionNode[]) => {
    items.sort((a, b) => a.section.order_index - b.section.order_index);
    items.forEach((item) => sortNodes(item.children));
  };
  sortNodes(roots);
  return roots;
}
