import { useEffect, useMemo, useState } from "react";
import { getTextbook, importConvertedTextbook, listTextbooks } from "./api/client";
import type { JobRecord, ParsedTextbook, TextbookSummary } from "./types/api";

function App() {
  const [parsed, setParsed] = useState<ParsedTextbook | null>(null);
  const [job, setJob] = useState<JobRecord | null>(null);
  const [textbooks, setTextbooks] = useState<TextbookSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const firstChunks = useMemo(() => parsed?.chunks.slice(0, 4) ?? [], [parsed]);
  const firstSections = useMemo(() => parsed?.sections.slice(0, 36) ?? [], [parsed]);

  useEffect(() => {
    void refreshTextbooks(true);
  }, []);

  async function refreshTextbooks(loadLatest = false) {
    const result = await listTextbooks();
    setTextbooks(result.textbooks);
    if (loadLatest && result.textbooks[0]) {
      const latest = await getTextbook(result.textbooks[0].raw_file_id);
      setParsed(latest);
    }
  }

  async function handleImport() {
    setLoading(true);
    setError(null);
    try {
      const result = await importConvertedTextbook();
      setParsed(result.parsed_textbook);
      setJob(result.job);
      await refreshTextbooks(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导入失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectTextbook(rawFileId: string) {
    setLoading(true);
    setError(null);
    try {
      setParsed(await getTextbook(rawFileId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="workspace">
      <aside className="panel sidebar">
        <header className="panelHeader">
          <span className="eyebrow">教材管理</span>
          <h1>学科知识整合智能体</h1>
        </header>

        <button className="primaryButton" onClick={handleImport} disabled={loading}>
          {loading ? "导入中..." : "导入示例教材"}
        </button>

        {error ? <p className="errorText">{error}</p> : null}

        <section className="summaryBlock">
          <h2>任务状态</h2>
          <dl>
            <div>
              <dt>状态</dt>
              <dd>{job?.status ?? "未开始"}</dd>
            </div>
            <div>
              <dt>进度</dt>
              <dd>{job ? `${job.progress}%` : "-"}</dd>
            </div>
            <div>
              <dt>消息</dt>
              <dd>{job?.message ?? "-"}</dd>
            </div>
          </dl>
        </section>

        <section className="summaryBlock">
          <h2>当前教材</h2>
          <dl>
            <div>
              <dt>名称</dt>
              <dd>{parsed?.raw_file.title ?? "-"}</dd>
            </div>
            <div>
              <dt>页数</dt>
              <dd>{parsed?.raw_file.page_count ?? "-"}</dd>
            </div>
            <div>
              <dt>输出</dt>
              <dd className="pathText">
                {textbooks.find((item) => item.raw_file_id === parsed?.raw_file.id)?.parsed_output_path ?? "-"}
              </dd>
            </div>
          </dl>
        </section>

        <section className="summaryBlock">
          <h2>已解析教材</h2>
          <div className="bookList">
            {textbooks.length === 0 ? (
              <p className="emptyText">暂无解析结果。</p>
            ) : (
              textbooks.map((book) => (
                <button
                  className={book.raw_file_id === parsed?.raw_file.id ? "bookItem active" : "bookItem"}
                  key={book.raw_file_id}
                  onClick={() => void handleSelectTextbook(book.raw_file_id)}
                  type="button"
                >
                  <span>{book.title}</span>
                  <small>
                    {book.section_count} sections / {book.chunk_count} chunks
                  </small>
                </button>
              ))
            )}
          </div>
        </section>
      </aside>

      <section className="panel mainCanvas">
        <header className="panelHeader compact">
          <span className="eyebrow">统一 JSON</span>
          <h2>Document Tree</h2>
        </header>

        <div className="metricsGrid">
          <Metric label="RawFile" value={parsed ? 1 : 0} />
          <Metric label="Elements" value={parsed?.elements.length ?? 0} />
          <Metric label="Sections" value={parsed?.sections.length ?? 0} />
          <Metric label="Chunks" value={parsed?.chunks.length ?? 0} />
        </div>

        <div className="sectionList">
          {firstSections.length === 0 ? (
            <p className="emptyText">等待导入教材。</p>
          ) : (
            firstSections.map((section) => (
              <article className="sectionRow" key={section.id}>
                <div className={`sectionTitle level${Math.min(section.level, 3)}`}>
                  <strong>{section.title}</strong>
                  <span>{section.source_locator.locator_text}</span>
                </div>
                <code>{section.id}</code>
              </article>
            ))
          )}
        </div>
      </section>

      <aside className="panel inspector">
        <header className="panelHeader compact">
          <span className="eyebrow">证据预览</span>
          <h2>Chunks</h2>
        </header>

        <div className="chunkList">
          {firstChunks.length === 0 ? (
            <p className="emptyText">导入后显示前几个 chunk。</p>
          ) : (
            firstChunks.map((chunk) => (
              <article className="chunkCard" key={chunk.id}>
                <div className="chunkMeta">
                  <code>{chunk.id}</code>
                  <span>{chunk.source_locator.locator_text}</span>
                </div>
                <p>{chunk.text}</p>
              </article>
            ))
          )}
        </div>
      </aside>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
