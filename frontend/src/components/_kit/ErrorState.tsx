import type { ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "./Button";
import { cn } from "@/utils/cn";

export interface ErrorStateProps {
  title?: string;
  description?: string;
  detail?: string;
  onRetry?: () => void;
  retryLabel?: string;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = "出错了",
  description,
  detail,
  onRetry,
  retryLabel = "重试",
  action,
  className,
  compact = false
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center text-center animate-fade-in",
        "border border-status-error/30 bg-status-error/5 rounded-card",
        compact ? "gap-2 p-4" : "gap-3 p-6",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex items-center justify-center rounded-full bg-status-error/15 text-status-error",
          compact ? "size-8 [&>svg]:size-4" : "size-10 [&>svg]:size-5"
        )}
        aria-hidden
      >
        <AlertCircle />
      </span>
      <div className="flex flex-col gap-1 max-w-sm">
        <p className={cn("font-medium text-status-error", compact ? "text-body" : "text-h2")}>
          {title}
        </p>
        {description ? (
          <p className="text-meta text-text-default leading-relaxed">{description}</p>
        ) : null}
        {detail ? (
          <p className="text-[11px] text-text-muted font-mono break-all leading-snug mt-1 max-h-20 overflow-y-auto">
            {detail}
          </p>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        {onRetry ? (
          <Button
            size="sm"
            variant="secondary"
            leftIcon={<RefreshCw className="size-3.5" />}
            onClick={onRetry}
          >
            {retryLabel}
          </Button>
        ) : null}
        {action}
      </div>
    </div>
  );
}
