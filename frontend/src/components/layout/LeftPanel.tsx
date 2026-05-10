/** 左栏：教材区。当前为骨架；下个 batch 接 UploadZone / TextbookList / ChapterTree。 */

import { BookOpen, Plus, UploadCloud } from "lucide-react";
import { Button, EmptyState, IconButton, Tooltip } from "@/components/_kit";
import { useUIStore } from "@/store/uiStore";

export function LeftPanel() {
  const collapsed = useUIStore((s) => s.leftCollapsed);

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 py-2">
        <Tooltip content="导入教材" side="right">
          <IconButton label="导入教材" icon={<Plus />} tooltip={false} />
        </Tooltip>
        <Tooltip content="教材列表（折叠中）" side="right">
          <IconButton label="教材列表" icon={<BookOpen />} tooltip={false} />
        </Tooltip>
      </div>
    );
  }

  return (
    <>
      <div className="px-3 h-11 border-b border-border-soft flex items-center justify-between shrink-0">
        <h2 className="text-h2 text-text-strong">教材</h2>
        <Button size="sm" variant="ghost" leftIcon={<Plus className="size-3.5" />}>
          添加
        </Button>
      </div>
      <div className="scroll-region p-3">
        <EmptyState
          compact
          icon={<UploadCloud />}
          title="还没有教材"
          description="拖拽 PDF / Word / Excel / PPT 到此区域开始解析。"
          action={<Button size="sm">导入示例</Button>}
        />
      </div>
    </>
  );
}
