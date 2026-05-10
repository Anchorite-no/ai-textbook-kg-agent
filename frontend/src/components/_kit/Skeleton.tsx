import { cn } from "@/utils/cn";

export interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  rounded?: "none" | "control" | "card" | "pill" | "full";
  className?: string;
}

const radiusClass = {
  none: "rounded-none",
  control: "rounded-control",
  card: "rounded-card",
  pill: "rounded-pill",
  full: "rounded-full"
};

export function Skeleton({ width, height = 16, rounded = "control", className }: SkeletonProps) {
  return (
    <span
      role="status"
      aria-label="加载中"
      className={cn("block shimmer", radiusClass[rounded], className)}
      style={{
        width: width === undefined ? "100%" : typeof width === "number" ? `${width}px` : width,
        height: typeof height === "number" ? `${height}px` : height
      }}
    />
  );
}

export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          height={12}
          width={i === lines - 1 ? "70%" : "100%"}
          rounded="control"
        />
      ))}
    </div>
  );
}
