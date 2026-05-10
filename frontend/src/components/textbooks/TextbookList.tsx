/** 教材列表。plan 16 §11.2。
 *  - 虚拟滚动（react-window）
 *  - 选中态 + hover
 *  - 教材色点 + 标题 + 格式 Tag + 统计（页数 / chunks）
 *  - 点击选中 → 右侧显示章节树 */

import { FixedSizeList as List } from "react-window";
import { FileText, Trash2 } from "lucide-react";
import { IconButton, Tag, Tooltip } from "@/components/_kit";
import { cn } from "@/utils/cn";
import { getBookColor } from "@/components/graph/colors";
import type { TextbookSummary } from "@/types/api";

export interface TextbookListProps {
  textbooks: TextbookSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
  height?: number;
}

export function TextbookList({ textbooks, selectedId, onSelect, onDelete, height = 400 }: TextbookListProps) {
  if (textbooks.length === 0) return null;

  return (
    <div className="flex-1 min-h-0">
      <List
        height={height}
        itemCount={textbooks.length}
        itemSize={72}
        width="100%"
        itemData={{ textbooks, selectedId, onSelect, onDelete }}
      >
        {Row}
      </List>
    </div>
  );
}

interface RowData {
  textbooks: TextbookSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete?: (id: string) => void;
}

function Row({ index, style, data }: { index: number; style: React.CSSProperties; data: RowData }) {
  const { textbooks, selectedId, onSelect, onDelete } = data;
  const book = textbooks[index];
  const isSelected = selectedId === book.raw_file_id;

  return (
    <div
      style={style}
      className={cn(
        "group px-3 py-2 border-b border-border-soft cursor-pointer transition-colors duration-micro",
        isSelected ? "bg-brand-50" : "hover:bg-surface-input"
      )}
      onClick={() => onSelect(book.raw_file_id)}
    >
      <div className="flex items-start gap-2">
        <span
          className="mt-1 inline-block size-2.5 rounded-full shrink-0"
          style={{ backgroundColor: getBookColor(book.raw_file_id) }}
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h3 className="text-body font-medium text-text-strong truncate flex-1">
              {book.title}
            </h3>
            <Tag variant="neutral" size="sm">
              {book.format.toUpperCase()}
            </Tag>
          </div>
          <div className="flex items-center gap-3 text-meta text-text-muted tabular">
            <span className="inline-flex items-center gap-1">
              <FileText className="size-3" aria-hidden />
              {book.page_count ?? book.element_count} 页
            </span>
            <span>{book.chunk_count.toLocaleString()} chunks</span>
            <span>{book.section_count} 章节</span>
          </div>
        </div>
        {onDelete ? (
          <Tooltip content="删除教材">
            <IconButton
              label="删除"
              tooltip={false}
              size="sm"
              icon={<Trash2 className="size-3" />}
              onClick={(e) => {
                e.stopPropagation();
                onDelete(book.raw_file_id);
              }}
              className="opacity-0 group-hover:opacity-100 transition-opacity"
            />
          </Tooltip>
        ) : null}
      </div>
    </div>
  );
}
