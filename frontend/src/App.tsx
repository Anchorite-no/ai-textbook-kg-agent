/** 临时验证页：foundation smoke test。
 *  下一阶段会替换为 AppShell（plan 16 §11）。 */

import { useState } from "react";
import {
  Activity,
  BookOpen,
  Database,
  FileText,
  Plus,
  Search,
  Settings
} from "lucide-react";
import {
  Button,
  EmptyState,
  ErrorState,
  IconButton,
  Skeleton,
  SkeletonText,
  StatusDot,
  Tag,
  Tooltip
} from "@/components/_kit";
import { apiMode } from "@/api/registry";
import { request } from "@/api/client";
import type { HealthResponse } from "@/types/api";

function App() {
  const [healthState, setHealthState] = useState<
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ok"; data: HealthResponse }
    | { kind: "error"; message: string }
  >({ kind: "idle" });

  async function checkHealth() {
    setHealthState({ kind: "loading" });
    try {
      const data = await request<HealthResponse>("/api/health");
      setHealthState({ kind: "ok", data });
    } catch (err) {
      setHealthState({
        kind: "error",
        message: err instanceof Error ? err.message : "未知错误"
      });
    }
  }

  return (
    <div className="app-shell">
      {/* TopBar 占位 */}
      <header className="flex items-center justify-between px-4 border-b border-border-soft bg-surface-card">
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center justify-center size-7 rounded-control bg-brand-500 text-text-inverse">
            <BookOpen className="size-4" />
          </span>
          <div className="flex items-baseline gap-2">
            <h1 className="text-h2 text-text-strong">学科知识整合智能体</h1>
            <span className="text-meta text-text-muted">Foundation Smoke Test</span>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Tooltip content="搜索（⌘K）">
            <IconButton label="搜索" icon={<Search />} />
          </Tooltip>
          <Tooltip content="数据集">
            <IconButton label="数据集" icon={<Database />} />
          </Tooltip>
          <Tooltip content="设置">
            <IconButton label="设置" icon={<Settings />} />
          </Tooltip>
        </div>
      </header>

      {/* 主工作区占位 */}
      <main className="workspace overflow-hidden">
        {/* 左栏 */}
        <aside
          className="panel border-r border-border-soft"
          style={{ width: "var(--left-default)" }}
        >
          <div className="px-4 py-3 border-b border-border-soft flex items-center justify-between">
            <h2 className="text-h2 text-text-strong">教材</h2>
            <Button size="sm" variant="ghost" leftIcon={<Plus className="size-3.5" />}>
              添加
            </Button>
          </div>
          <div className="scroll-region p-4">
            <EmptyState
              icon={<BookOpen />}
              title="还没有教材"
              description="拖拽 PDF / Word / Excel / PPT 到此处开始解析。"
              action={<Button size="sm">导入示例</Button>}
            />
          </div>
        </aside>

        {/* 中栏 */}
        <section className="panel flex-1 grid-bg">
          <div className="h-12 px-4 border-b border-border-soft flex items-center gap-3 bg-surface-card/80 backdrop-blur-sm">
            <Tag variant="brand" size="md">
              单本图谱
            </Tag>
            <span className="text-meta text-text-muted tabular">0 节点 · 0 边</span>
            <div className="ml-auto flex items-center gap-1">
              <Tooltip content="重置视图">
                <IconButton label="重置视图" icon={<Activity className="size-4" />} />
              </Tooltip>
            </div>
          </div>
          <div className="scroll-region flex items-center justify-center">
            <EmptyState
              title="导入教材并构建图谱后显示"
              description="工作台中央保留给力导向图谱。"
            />
          </div>
        </section>

        {/* 右栏 */}
        <aside
          className="panel border-l border-border-soft"
          style={{ width: "var(--right-default)" }}
        >
          <div className="px-4 py-3 border-b border-border-soft">
            <h2 className="text-h2 text-text-strong">原子组件试运行</h2>
            <p className="text-meta text-text-muted mt-0.5">
              验证 token / 动效 / 五状态可工作。
            </p>
          </div>
          <div className="scroll-region p-4 flex flex-col gap-5">
            <DemoBlock title="按钮">
              <div className="flex flex-wrap gap-2">
                <Button>主要操作</Button>
                <Button variant="secondary">次要</Button>
                <Button variant="ghost">无底</Button>
                <Button variant="destructive">删除</Button>
                <Button loading>加载</Button>
                <Button disabled>禁用</Button>
              </div>
            </DemoBlock>

            <DemoBlock title="标签">
              <div className="flex flex-wrap gap-2">
                <Tag variant="neutral">中性</Tag>
                <Tag variant="brand">主色</Tag>
                <Tag variant="success" dot>
                  完成
                </Tag>
                <Tag variant="warning" dot>
                  警告
                </Tag>
                <Tag variant="error" dot>
                  错误
                </Tag>
                <Tag variant="info" dot>
                  运行中
                </Tag>
                <Tag variant="outline">虚线</Tag>
              </div>
            </DemoBlock>

            <DemoBlock title="状态点">
              <div className="flex items-center gap-4 text-meta text-text-default">
                <span className="inline-flex items-center gap-2">
                  <StatusDot status="pending" /> 等待
                </span>
                <span className="inline-flex items-center gap-2">
                  <StatusDot status="running" /> 运行
                </span>
                <span className="inline-flex items-center gap-2">
                  <StatusDot status="success" /> 完成
                </span>
                <span className="inline-flex items-center gap-2">
                  <StatusDot status="warning" /> 警告
                </span>
                <span className="inline-flex items-center gap-2">
                  <StatusDot status="error" /> 失败
                </span>
              </div>
            </DemoBlock>

            <DemoBlock title="骨架">
              <div className="flex flex-col gap-3">
                <Skeleton height={32} rounded="control" />
                <SkeletonText lines={3} />
              </div>
            </DemoBlock>

            <DemoBlock title="错误态">
              <ErrorState
                compact
                title="解析失败"
                description="文件格式不受支持。"
                detail="UnsupportedFormat: .doc"
                onRetry={() => undefined}
              />
            </DemoBlock>

            <DemoBlock title="后端连通性">
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="secondary" onClick={checkHealth}>
                    GET /api/health
                  </Button>
                  {healthState.kind === "loading" ? (
                    <Tag variant="info" dot>
                      请求中
                    </Tag>
                  ) : healthState.kind === "ok" ? (
                    <Tag variant="success" dot>
                      {healthState.data.status} · v{healthState.data.version}
                    </Tag>
                  ) : healthState.kind === "error" ? (
                    <Tag variant="error" dot>
                      {healthState.message}
                    </Tag>
                  ) : (
                    <Tag variant="neutral">未请求</Tag>
                  )}
                </div>
                <div className="flex items-center gap-2 text-meta text-text-muted">
                  <FileText className="size-3.5" />
                  <span>
                    API 模式：textbooks=
                    <code className="font-mono">{apiMode.textbooks}</code> ·
                    graph=<code className="font-mono">{apiMode.graph}</code>
                  </span>
                </div>
              </div>
            </DemoBlock>
          </div>
        </aside>
      </main>
    </div>
  );
}

function DemoBlock({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-card border border-border-soft bg-surface-card p-3">
      <h3 className="text-meta uppercase tracking-wide text-text-muted mb-2">{title}</h3>
      {children}
    </section>
  );
}

export default App;
