/** < 768px 屏障。plan 16 §3.4 规定移动端不支持。 */

import { Monitor } from "lucide-react";
import { breakpoints, useMediaQuery } from "@/hooks/useMediaQuery";

export function ResponsiveGate({ children }: { children: React.ReactNode }) {
  const supported = useMediaQuery(`(min-width: ${breakpoints.xs}px)`);

  if (!supported) {
    return (
      <div className="h-screen flex items-center justify-center px-6 bg-surface-app">
        <div className="max-w-sm flex flex-col items-center text-center gap-4 animate-fade-in-up">
          <span
            className="inline-flex items-center justify-center size-14 rounded-full bg-brand-50 text-brand-700"
            aria-hidden
          >
            <Monitor className="size-6" />
          </span>
          <div className="flex flex-col gap-1">
            <h1 className="text-display text-text-strong">需要桌面浏览器</h1>
            <p className="text-body text-text-muted leading-relaxed">
              学科知识整合智能体是为 ≥ 768px 的工作台屏幕设计的。请用桌面浏览器或拉宽窗口后重试。
            </p>
          </div>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
