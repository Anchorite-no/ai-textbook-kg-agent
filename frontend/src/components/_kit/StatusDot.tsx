import { cn } from "@/utils/cn";
import type { StatusVariant } from "@/types/api";

const colorMap: Record<StatusVariant, string> = {
  pending: "bg-status-pending",
  running: "bg-status-running",
  success: "bg-status-success",
  warning: "bg-status-warning",
  error: "bg-status-error"
};

const sizeMap = {
  xs: "size-1.5",
  sm: "size-2",
  md: "size-2.5"
};

export interface StatusDotProps {
  status: StatusVariant;
  size?: keyof typeof sizeMap;
  /** running 时是否做呼吸脉动；其他状态忽略 */
  pulse?: boolean;
  className?: string;
}

export function StatusDot({ status, size = "sm", pulse = true, className }: StatusDotProps) {
  const showPulse = pulse && status === "running";
  return (
    <span className={cn("relative inline-flex shrink-0", sizeMap[size], className)} aria-hidden>
      {showPulse ? (
        <span
          className={cn(
            "absolute inset-0 rounded-full animate-ping opacity-60",
            colorMap[status]
          )}
        />
      ) : null}
      <span className={cn("relative rounded-full", sizeMap[size], colorMap[status])} />
    </span>
  );
}
