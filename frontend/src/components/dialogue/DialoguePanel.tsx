import { MessageSquare, Send, User, Bot, Loader2 } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, EmptyState } from "@/components/_kit";
import { cn } from "@/utils/cn";
import { dialogueApi } from "@/api/dialogue";
import type { DialogueMessage } from "@/types/api";

export function DialoguePanel() {
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ["dialogue-history"],
    queryFn: () => dialogueApi.getHistory(),
    staleTime: 30_000
  });

  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [localMessages, setLocalMessages] = useState<DialogueMessage[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);

  const messages = [...(data?.messages ?? []), ...localMessages];

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages.length]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);

    const tempUserMsg: DialogueMessage = {
      id: `temp_u_${Date.now()}`,
      role: "user",
      content: text,
      raw_file_ids: [],
      teacher_edit_ids: [],
      created_by: null,
      created_at: new Date().toISOString(),
      metadata: {}
    };
    setLocalMessages((prev) => [...prev, tempUserMsg]);

    try {
      const res = await dialogueApi.sendMessage({ message: text });
      setLocalMessages((prev) => [
        ...prev.filter((m) => m.id !== tempUserMsg.id),
        res.user_message,
        res.assistant_message
      ]);
      queryClient.invalidateQueries({ queryKey: ["dialogue-history"] });
    } catch (err) {
      const errorMsg: DialogueMessage = {
        id: `temp_e_${Date.now()}`,
        role: "assistant",
        content: `发送失败：${err instanceof Error ? err.message : "未知错误"}`,
        raw_file_ids: [],
        teacher_edit_ids: [],
        created_by: null,
        created_at: new Date().toISOString(),
        metadata: {}
      };
      setLocalMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
    }
  }

  if (messages.length === 0 && !sending) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center p-4">
          <EmptyState
            icon={<MessageSquare />}
            title="教师对话"
            description="可以问「为什么删除某节点？」或要求保留 / 拆分整合方案。"
          />
        </div>
        <div className="p-3 border-t border-border-soft">
          <MessageInput value={input} onChange={setInput} onSend={handleSend} disabled={sending} />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 scroll-region p-4">
        <div className="flex flex-col gap-3">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {sending ? (
            <div className="flex gap-2">
              <span className="inline-flex items-center justify-center size-7 rounded-full shrink-0 mt-1 bg-surface-input text-text-muted">
                <Bot className="size-3.5" />
              </span>
              <div className="rounded-card bg-surface-card border border-border-soft p-3 flex items-center gap-2 text-meta text-text-muted">
                <Loader2 className="size-3.5 animate-spin" />
                正在思考…
              </div>
            </div>
          ) : null}
        </div>
      </div>
      <div className="p-3 border-t border-border-soft">
        <MessageInput value={input} onChange={setInput} onSend={handleSend} disabled={sending} />
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: DialogueMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "inline-flex items-center justify-center size-7 rounded-full shrink-0 mt-1",
          isUser ? "bg-brand-500 text-text-inverse" : "bg-surface-input text-text-muted"
        )}
        aria-hidden
      >
        {isUser ? <User className="size-3.5" /> : <Bot className="size-3.5" />}
      </span>
      <div
        className={cn(
          "max-w-[75%] rounded-card p-3",
          isUser
            ? "bg-brand-500 text-text-inverse"
            : "bg-surface-card border border-border-soft text-text-default"
        )}
      >
        <p className="text-body leading-relaxed whitespace-pre-wrap">{message.content}</p>
      </div>
    </div>
  );
}

function MessageInput({
  value,
  onChange,
  onSend,
  disabled
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  disabled: boolean;
}) {
  return (
    <div className="flex items-end gap-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        placeholder="输入消息（Enter 发送，Shift+Enter 换行）"
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
        onClick={onSend}
        disabled={!value.trim() || disabled}
      >
        发送
      </Button>
    </div>
  );
}
