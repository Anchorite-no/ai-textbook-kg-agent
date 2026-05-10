import { Search, Send, BookOpen, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Button, EmptyState, Tag } from "@/components/_kit";
import { cn } from "@/utils/cn";
import { ragApi } from "@/api/rag";
import type { RAGQueryResponse, RAGCitation } from "@/types/api";

interface HistoryItem {
  question: string;
  answer: string;
  citations: RAGCitation[];
  loading?: boolean;
}

export function RAGPanel() {
  const [query, setQuery] = useState("");
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history]);

  async function handleSubmit() {
    const q = query.trim();
    if (!q) return;
    setQuery("");
    setHistory((h) => [...h, { question: q, answer: "", citations: [], loading: true }]);

    try {
      const res: RAGQueryResponse = await ragApi.queryRAG(q);
      setHistory((h) =>
        h.map((item, i) =>
          i === h.length - 1
            ? { question: q, answer: res.answer, citations: res.citations, loading: false }
            : item
        )
      );
    } catch (err) {
      const msg = err instanceof Error ? err.message : "请求失败";
      setHistory((h) =>
        h.map((item, i) =>
          i === h.length - 1
            ? { question: q, answer: `错误：${msg}`, citations: [], loading: false }
            : item
        )
      );
    }
  }

  if (history.length === 0) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center p-4">
          <EmptyState
            icon={<Search />}
            title="RAG 问答"
            description="输入问题，系统将从已解析教材中检索并生成回答。"
          />
        </div>
        <div className="p-3 border-t border-border-soft">
          <QueryInput value={query} onChange={setQuery} onSubmit={handleSubmit} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 scroll-region p-4">
        <div className="flex flex-col gap-4">
          {history.map((item, idx) => (
            <div key={idx} className="flex flex-col gap-2">
              <div className="rounded-card bg-brand-50 p-3">
                <p className="text-body text-text-strong">{item.question}</p>
              </div>
              <div className="rounded-card bg-surface-card border border-border-soft p-3">
                {item.loading ? (
                  <div className="flex items-center gap-2 text-meta text-text-muted">
                    <Loader2 className="size-3.5 animate-spin" />
                    正在检索与生成…
                  </div>
                ) : (
                  <>
                    <p className="text-body text-text-default leading-relaxed whitespace-pre-wrap">
                      {item.answer}
                    </p>
                    {item.citations.length > 0 ? (
                      <div className="mt-3 flex flex-col gap-1.5">
                        <span className="text-[11px] uppercase tracking-wide text-text-muted font-medium">
                          引用来源
                        </span>
                        {item.citations.map((c, ci) => (
                          <div
                            key={ci}
                            className="flex items-start gap-2 p-2 rounded-control bg-surface-input text-[12px]"
                          >
                            <BookOpen className="size-3 mt-0.5 text-text-muted shrink-0" />
                            <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                              <span className="text-text-default line-clamp-2">
                                {c.quote}
                              </span>
                              <span className="text-text-muted truncate">
                                {c.textbook}{c.chapter ? ` · ${c.chapter}` : ""}
                              </span>
                            </div>
                            <Tag size="sm" variant="outline" className="shrink-0">
                              {(c.relevance_score * 100).toFixed(0)}%
                            </Tag>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="p-3 border-t border-border-soft">
        <QueryInput value={query} onChange={setQuery} onSubmit={handleSubmit} />
      </div>
    </div>
  );
}

function QueryInput({
  value,
  onChange,
  onSubmit
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="flex items-end gap-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSubmit();
          }
        }}
        placeholder="输入问题（Enter 提交，Shift+Enter 换行）"
        rows={2}
        className={cn(
          "flex-1 px-3 py-2 rounded-control border border-border-soft bg-surface-input",
          "text-body text-text-default placeholder:text-text-subtle resize-none",
          "focus-visible:outline-none focus-visible:border-brand-500"
        )}
      />
      <Button
        size="md"
        variant="primary"
        leftIcon={<Send className="size-3.5" />}
        onClick={onSubmit}
        disabled={!value.trim()}
      >
        提交
      </Button>
    </div>
  );
}
