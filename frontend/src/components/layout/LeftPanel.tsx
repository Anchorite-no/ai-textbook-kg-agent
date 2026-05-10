/** 左栏：教材区。UploadZone + TextbookList + ChapterTree。 */

import { BookOpen, Plus, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";
import { Button, EmptyState, IconButton, Tooltip } from "@/components/_kit";
import { useUIStore } from "@/store/uiStore";
import { useTextbooksQuery } from "@/hooks/useTextbooks";
import { UploadZone } from "@/components/textbooks/UploadZone";
import { TextbookList } from "@/components/textbooks/TextbookList";
import { ChapterTree } from "@/components/textbooks/ChapterTree";

export function LeftPanel() {
  const collapsed = useUIStore((s) => s.leftCollapsed);
  const toggleLeftCollapsed = useUIStore((s) => s.toggleLeftCollapsed);
  const { data: textbooks, isLoading } = useTextbooksQuery();
  const [selectedTextbookId, setSelectedTextbookId] = useState<string | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  function handleUpload(files: File[]) {
    console.log("Upload files:", files);
    // TODO: 接入 textbooks upload API
    setShowUpload(false);
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 py-2">
        <Tooltip content="展开侧栏（⌘\\）" side="right">
          <IconButton
            label="展开侧栏"
            icon={<PanelLeftOpen />}
            tooltip={false}
            onClick={toggleLeftCollapsed}
          />
        </Tooltip>
        <Tooltip content="导入教材" side="right">
          <IconButton
            label="导入教材"
            icon={<Plus />}
            tooltip={false}
            onClick={() => { toggleLeftCollapsed(); setShowUpload(true); }}
          />
        </Tooltip>
        <Tooltip content="教材列表" side="right">
          <IconButton label="教材列表" icon={<BookOpen />} tooltip={false} onClick={toggleLeftCollapsed} />
        </Tooltip>
      </div>
    );
  }

  const hasTextbooks = textbooks && textbooks.length > 0;

  return (
    <>
      <div className="px-3 h-11 border-b border-border-soft flex items-center justify-between shrink-0">
        <h2 className="text-h2 text-text-strong">教材</h2>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<Plus className="size-3.5" />}
            onClick={() => setShowUpload(!showUpload)}
          >
            {showUpload ? "取消" : "添加"}
          </Button>
          <Tooltip content={collapsed ? "展开（⌘\\）" : "折叠（⌘\\）"}>
            <IconButton
              label="折叠"
              tooltip={false}
              size="sm"
              icon={collapsed ? <PanelLeftOpen /> : <PanelLeftClose />}
              onClick={toggleLeftCollapsed}
            />
          </Tooltip>
        </div>
      </div>
      <div className="scroll-region flex flex-col">
        {showUpload ? <UploadZone onUpload={handleUpload} /> : null}

        {isLoading ? (
          <div className="p-3">
            <EmptyState compact title="加载中…" />
          </div>
        ) : !hasTextbooks ? (
          <div className="p-3">
            <EmptyState
              compact
              icon={<BookOpen />}
              title="还没有教材"
              description="点击「添加」按钮导入 PDF / Word / Excel / PPT。"
            />
          </div>
        ) : (
          <>
            <TextbookList
              textbooks={textbooks}
              selectedId={selectedTextbookId}
              onSelect={setSelectedTextbookId}
            />
            <div className="border-t border-border-soft">
              <div className="px-3 py-2 bg-surface-card">
                <h3 className="text-meta uppercase tracking-wide text-text-muted font-medium">
                  章节
                </h3>
              </div>
              <ChapterTree textbookId={selectedTextbookId} />
            </div>
          </>
        )}
      </div>
    </>
  );
}
