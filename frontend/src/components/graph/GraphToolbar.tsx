/** 图谱顶部工具栏。模式切换、搜索（占位）、节点/边数显示。 */

import { Maximize2, PanelRightOpen, RefreshCw, Search, RotateCcw } from "lucide-react";
import { IconButton, SegmentedControl, Tag, Tooltip } from "@/components/_kit";
import { useUIStore, type GraphDisplayMode, type GraphMode } from "@/store/uiStore";

export interface GraphToolbarProps {
  nodeCount: number;
  edgeCount: number;
  fetching?: boolean;
  onResetView?: () => void;
  onRefresh?: () => void;
  onFullscreen?: () => void;
}

const modeOptions = [
  { value: "single" as GraphMode, label: "单本" },
  { value: "merged" as GraphMode, label: "并列" },
  { value: "compare" as GraphMode, label: "对照" }
];

const displayOptions = [
  { value: "core" as GraphDisplayMode, label: "核心" },
  { value: "full" as GraphDisplayMode, label: "完整" }
];

export function GraphToolbar({
  nodeCount,
  edgeCount,
  fetching,
  onResetView,
  onRefresh,
  onFullscreen
}: GraphToolbarProps) {
  const graphMode = useUIStore((s) => s.graphMode);
  const setGraphMode = useUIStore((s) => s.setGraphMode);
  const graphDisplayMode = useUIStore((s) => s.graphDisplayMode);
  const setGraphDisplayMode = useUIStore((s) => s.setGraphDisplayMode);
  const searchKeyword = useUIStore((s) => s.searchKeyword);
  const setSearchKeyword = useUIStore((s) => s.setSearchKeyword);
  const rightHidden = useUIStore((s) => s.rightHidden);
  const toggleRightHidden = useUIStore((s) => s.toggleRightHidden);

  return (
    <div className="h-12 px-3 border-b border-border-soft flex items-center gap-3 bg-surface-card/85 backdrop-blur-sm shrink-0 overflow-hidden">
      <SegmentedControl<GraphMode>
        value={graphMode}
        onChange={setGraphMode}
        options={modeOptions}
        ariaLabel="图谱模式"
      />

      <SegmentedControl<GraphDisplayMode>
        value={graphDisplayMode}
        onChange={setGraphDisplayMode}
        options={displayOptions}
        ariaLabel="图谱显示范围"
      />

      <div className="relative min-w-0 flex-1 max-w-56">
        <Search
          className="absolute left-2 top-1/2 -translate-y-1/2 size-3.5 text-text-subtle pointer-events-none"
          aria-hidden
        />
        <input
          type="search"
          value={searchKeyword}
          onChange={(e) => setSearchKeyword(e.target.value)}
          placeholder="搜索节点（⌘F）"
          className="h-7 w-full pl-7 pr-2 rounded-control border border-border-soft bg-surface-input text-meta text-text-default placeholder:text-text-subtle focus-visible:outline-none focus-visible:border-brand-500"
        />
      </div>

      <Tag variant={fetching ? "info" : "neutral"} size="sm">
        <span className="tabular">{nodeCount}</span>
        <span className="text-text-muted ml-0.5">节点</span>
        <span className="text-text-subtle mx-1">·</span>
        <span className="tabular">{edgeCount}</span>
        <span className="text-text-muted ml-0.5">边</span>
      </Tag>

      <div className="ml-auto flex items-center gap-1 shrink-0">
        {onRefresh ? (
          <Tooltip content="重新拉取">
            <IconButton
              label="刷新"
              tooltip={false}
              icon={<RefreshCw className="size-3.5" />}
              onClick={onRefresh}
            />
          </Tooltip>
        ) : null}
        {onResetView ? (
          <Tooltip content="重置视图（双击空白）">
            <IconButton
              label="重置视图"
              tooltip={false}
              icon={<RotateCcw className="size-3.5" />}
              onClick={onResetView}
            />
          </Tooltip>
        ) : null}
        {onFullscreen ? (
          <Tooltip content="全屏">
            <IconButton
              label="全屏"
              tooltip={false}
              icon={<Maximize2 className="size-3.5" />}
              onClick={onFullscreen}
            />
          </Tooltip>
        ) : null}
        {rightHidden ? (
          <>
            <span className="h-5 w-px bg-border-soft" aria-hidden />
            <Tooltip content="展开右栏（⌘B）">
              <IconButton
                label="展开右栏"
                tooltip={false}
                icon={<PanelRightOpen className="size-3.5" />}
                onClick={toggleRightHidden}
              />
            </Tooltip>
          </>
        ) : null}
      </div>
    </div>
  );
}
