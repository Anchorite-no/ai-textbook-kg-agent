/** 全局 Toast 容器 + provider。plan 16 §9.1：右上、最多 3 条、error 不自动消失。 */

import * as ToastPrimitive from "@radix-ui/react-toast";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { create } from "zustand";
import { cn } from "@/utils/cn";
import { IconButton } from "@/components/_kit";

export type ToastTone = "success" | "info" | "warning" | "error";

export interface ToastItem {
  id: string;
  tone: ToastTone;
  title: string;
  description?: string;
  /** 不传走默认（success 3s / info 4s / warning 5s / error 不自动消失） */
  duration?: number | null;
  action?: { label: string; onClick: () => void };
}

interface ToastStore {
  toasts: ToastItem[];
  push: (toast: Omit<ToastItem, "id">) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (toast) => {
    const id = `t_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
    set((s) => ({ toasts: [...s.toasts, { ...toast, id }].slice(-3) }));
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] })
}));

/** 在 React 组件外触发 Toast 时使用。 */
export const toastStore = {
  push: (toast: Omit<ToastItem, "id">) => useToastStore.getState().push(toast),
  dismiss: (id: string) => useToastStore.getState().dismiss(id),
  clear: () => useToastStore.getState().clear()
};

export function useToast() {
  return useToastStore((s) => ({ push: s.push, dismiss: s.dismiss, clear: s.clear }));
}

const defaultDuration: Record<ToastTone, number | null> = {
  success: 3000,
  info: 4000,
  warning: 5000,
  error: null
};

const toneClass: Record<ToastTone, string> = {
  success: "border-status-success/40 bg-status-success/5",
  info: "border-status-running/40 bg-status-running/5",
  warning: "border-status-warning/40 bg-status-warning/5",
  error: "border-status-error/40 bg-status-error/5"
};

const iconMap: Record<ToastTone, typeof CheckCircle2> = {
  success: CheckCircle2,
  info: Info,
  warning: AlertTriangle,
  error: AlertCircle
};

const iconColor: Record<ToastTone, string> = {
  success: "text-status-success",
  info: "text-status-running",
  warning: "text-status-warning",
  error: "text-status-error"
};

export function ToastViewport() {
  const toasts = useToastStore((s) => s.toasts);
  const dismiss = useToastStore((s) => s.dismiss);

  return (
    <ToastPrimitive.Provider duration={4000} swipeDirection="right">
      {toasts.map((t) => {
        const Icon = iconMap[t.tone];
        const duration =
          t.duration === null
            ? Infinity
            : t.duration ?? defaultDuration[t.tone] ?? 4000;
        return (
          <ToastPrimitive.Root
            key={t.id}
            duration={duration === Infinity ? 1_000_000_000 : duration}
            onOpenChange={(open) => !open && dismiss(t.id)}
            className={cn(
              "group relative flex items-start gap-3 w-80 p-3 pr-9 rounded-card border shadow-overlay",
              "bg-surface-card",
              toneClass[t.tone],
              "data-[state=open]:animate-[slide-in-right_240ms_var(--ease-decelerate)]",
              "data-[state=closed]:animate-[slide-out-right_200ms_var(--ease-accelerate)]"
            )}
          >
            <Icon className={cn("size-4 mt-0.5 shrink-0", iconColor[t.tone])} aria-hidden />
            <div className="flex flex-col gap-1 min-w-0">
              <ToastPrimitive.Title className="text-body font-medium text-text-strong leading-tight">
                {t.title}
              </ToastPrimitive.Title>
              {t.description ? (
                <ToastPrimitive.Description className="text-meta text-text-muted leading-relaxed clamp-3">
                  {t.description}
                </ToastPrimitive.Description>
              ) : null}
              {t.action ? (
                <ToastPrimitive.Action
                  asChild
                  altText={t.action.label}
                  onClick={t.action.onClick}
                >
                  <button className="self-start mt-1 text-meta font-medium text-brand-700 hover:text-brand-600">
                    {t.action.label}
                  </button>
                </ToastPrimitive.Action>
              ) : null}
            </div>
            <ToastPrimitive.Close asChild>
              <IconButton
                label="关闭"
                tooltip={false}
                size="sm"
                icon={<X />}
                className="absolute top-2 right-2"
              />
            </ToastPrimitive.Close>
          </ToastPrimitive.Root>
        );
      })}
      <ToastPrimitive.Viewport className="fixed top-4 right-4 z-toast flex flex-col gap-2 outline-none" />
    </ToastPrimitive.Provider>
  );
}
