/** 节点详情浮层。plan 09 §5.3 + plan 16 §10.4。
 *  右下角 16px 偏移，宽 360，最大高 60vh，内部滚动。 */

import { BookOpen, ExternalLink, X } from "lucide-react";
import { IconButton, Tag, Tooltip } from "@/components/_kit";
import { cn } from "@/utils/cn";
import { useNodeDetailQuery } from "@/hooks/useGraph";
import { getBookColor } from "./colors";

export interface NodeInspectorProps {
  nodeId: string | null;
  onClose: () => void;
}

export function NodeInspector({ nodeId, onClose }: NodeInspectorProps) {
  const { data, isLoading, error } = useNodeDetailQuery(nodeId);
  if (!nodeId) return null;

  const node = data?.node ?? null;

  return (
    <div
      className={cn(
        "absolute right-4 bottom-4 w-[360px] max-h-[60vh] flex flex-col",
        "rounded-card border border-border-soft bg-surface-card shadow-overlay",
        "animate-scale-in"
      )}
      role="dialog"
      aria-label="节点详情"
    >
      <div className="px-3 py-2.5 border-b border-border-soft flex items-start gap-2">
        {node ? (
          <>
            <span
              className="mt-0.5 inline-block size-2.5 rounded-full shrink-0"
              style={{ backgroundColor: getBookColor(node.source_locator.raw_file_id) }}
              aria-hidden
            />
            <div className="flex-1 min-w-0">
              <h3 className="text-h2 text-text-strong truncate">{node.name}</h3>
              <div className="flex items-center gap-2 mt-1">
                <Tag size="sm" variant="brand">
                  {node.node_type}
                </Tag>
                <span className="text-meta text-text-muted tabular">
                  置信度 {(node.confidence * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </>
        ) : (
          <h3 className="text-h2 text-text-muted flex-1">
            {isLoading ? "加载节点详情…" : "节点未找到"}
          </h3>
        )}
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

      <div className="scroll-region p-3 flex flex-col gap-3">
        {error ? (
          <p className="text-meta text-status-error">详情加载失败</p>
        ) : null}

        {node?.definition ? (
          <Section title="定义">
            <p className="text-body text-text-default leading-relaxed">{node.definition}</p>
          </Section>
        ) : null}

        {node?.aliases?.length ? (
          <Section title="别名">
            <div className="flex flex-wrap gap-1.5">
              {node.aliases.map((alias: string) => (
                <Tag key={alias} variant="outline" size="sm">
                  {alias}
                </Tag>
              ))}
            </div>
          </Section>
        ) : null}

        {node ? (
          <Section title="来源">
            <div className="flex items-start gap-2 p-2 rounded-control bg-surface-input">
              <BookOpen className="size-3.5 text-text-muted mt-0.5 shrink-0" aria-hidden />
              <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                <span className="text-meta text-text-default truncate">
                  {node.source_locator.raw_file_id}
                </span>
                <span className="text-[11px] text-text-muted truncate">
                  {node.source_locator.locator_text}
                </span>
              </div>
              <Tooltip content="打开来源 chunk（todo）">
                <IconButton
                  label="打开来源"
                  size="sm"
                  tooltip={false}
                  icon={<ExternalLink className="size-3" />}
                />
              </Tooltip>
            </div>
          </Section>
        ) : null}

        {node?.evidence_chunk_ids?.length ? (
          <Section title="证据 chunk">
            <ul className="flex flex-col gap-1 text-meta text-text-muted font-mono">
              {node.evidence_chunk_ids.slice(0, 6).map((chunkId: string) => (
                <li key={chunkId} className="truncate">{chunkId}</li>
              ))}
              {node.evidence_chunk_ids.length > 6 ? (
                <li className="text-text-subtle">…还有 {node.evidence_chunk_ids.length - 6} 条</li>
              ) : null}
            </ul>
          </Section>
        ) : null}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1.5">
      <h4 className="text-[11px] uppercase tracking-wide text-text-muted font-medium">{title}</h4>
      {children}
    </section>
  );
}
