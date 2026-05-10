import type { ReactNode } from "react";
import { Inbox } from "lucide-react";
import { cn } from "@/utils/cn";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
  /** 紧凑布局，用于在小区域内 */
  compact?: boolean;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  compact = false
}: EmptyStateProps) {
  return (
    <div
      role="status"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        "text-text-muted animate-fade-in",
        compact ? "gap-2 p-4" : "gap-3 p-8",
        className
      )}
    >
      <span
        className={cn(
          "inline-flex items-center justify-center rounded-full bg-surface-input text-text-subtle",
          compact ? "size-8 [&>svg]:size-4" : "size-12 [&>svg]:size-6"
        )}
        aria-hidden
      >
        {icon ?? <Inbox />}
      </span>
      <div className={cn("flex flex-col", compact ? "gap-0.5" : "gap-1")}>
        <p
          className={cn(
            "font-medium text-text-default",
            compact ? "text-body" : "text-h2"
          )}
        >
          {title}
        </p>
        {description ? (
          <p className="text-meta text-text-muted max-w-xs leading-relaxed">{description}</p>
        ) : null}
      </div>
      {action ? <div className="mt-1">{action}</div> : null}
    </div>
  );
}
