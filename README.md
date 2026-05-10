# 学科知识整合智能体

当前已完成计划 01，并在计划 02 中跑通多格式解析、统一 JSON 和证据链：
`RawFile -> DocumentElement -> Section -> Chunk`。

## 后端启动

```powershell
cd D:\Hackathon\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
```

## LLM 配置

后端 KG 抽取支持 OpenAI-compatible Responses API。复制 `.env.example` 为 `.env` 后填写：

```env
LLM_PROVIDER=openai-compatible
LLM_API_STYLE=responses
OPENAI_BASE_URL=http://your-api-gateway/
OPENAI_MODEL=gpt5.4
OPENAI_API_KEY=your-api-key
LLM_TIMEOUT_SECONDS=120
LLM_MAX_TOKENS=2200
```

后端会优先调用 `/v1/responses`，并在兼容服务不支持时回退到 chat completions。密钥文件 `.env` 已被 gitignore，禁止提交。

单书 LLM KG 试跑：

```powershell
cd D:\Hackathon
$env:PYTHONPATH=(Resolve-Path backend).Path
backend\.venv\Scripts\python.exe backend\scripts\trial_kg_llm_one_book.py --title '05_病理学' --max-sections 12 --max-nodes-per-section 10
```

导入一本已转换教材：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/textbooks/upload
```

上传解析单个文件：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/textbooks/upload -Form @{
  file = Get-Item .\sample.md
}
```

异步上传解析：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/textbooks/upload-async -Form @{
  file = Get-Item .\sample.md
}
```

返回 `job.id` 后轮询：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/jobs/{job_id}
```

失败任务可重试：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/jobs/{job_id}/retry
```

批量上传解析文件：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/textbooks/upload-batch -Form @{
  files = Get-Item .\sample.md, .\sample.xlsx
}
```

当前计划 02 支持：`txt`、`md`、`markdown`、`pdf`、`docx`、`xlsx`、`csv`、`tsv`、`pptx`。
旧版 `doc/xls/ppt` 暂不直接解析，会返回清晰错误，后续接 LibreOffice 转换兜底。

大文件分片上传：

```powershell
$body = @{
  filename = "large_sample.md"
  total_size_bytes = 1024
  total_chunks = 4
  chunk_size_bytes = 256
  sha256 = "完整文件 sha256"
  content_type = "text/markdown"
  parse_on_complete = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/uploads/sessions -Body $body -ContentType "application/json"
```

之后按 `PUT /api/uploads/sessions/{session_id}/chunks/{chunk_index}` 上传分片，最后调用 `POST /api/uploads/sessions/{session_id}/complete` 合并并解析。
如果不希望 complete 请求阻塞，调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/uploads/sessions/{session_id}/complete-async
```

查看已解析教材：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/textbooks
```

重新解析已上传文件：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8010/api/textbooks/{raw_file_id}/parse
```

后端阶段烟测：

```powershell
cd D:\Hackathon
$env:PYTHONPATH=(Resolve-Path backend).Path
backend\.venv\Scripts\python.exe backend\scripts\smoke_phase2.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage3_async.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage4_rag.py
backend\.venv\Scripts\python.exe backend\scripts\benchmark_00_stage4_rag.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_phase3.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage6_layered_kg.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage7_alignment.py
backend\.venv\Scripts\python.exe backend\scripts\benchmark_00_stage7_alignment.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage8_integration.py
backend\.venv\Scripts\python.exe backend\scripts\benchmark_00_stage8_integration.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage9_graphrag.py
backend\.venv\Scripts\python.exe backend\scripts\benchmark_00_stage9_graphrag.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage10_teacher_edit.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_frontend_dataset_workflow.py
```

导出前后端契约快照：

```powershell
cd D:\Hackathon
$env:PYTHONPATH=(Resolve-Path backend).Path
backend\.venv\Scripts\python.exe backend\scripts\export_openapi.py
```

快照输出到 `docs\openapi.snapshot.json`。前端离线 codegen 使用该文件；live codegen 使用 `http://127.0.0.1:8010/openapi.json`。

构建单本教材知识图谱：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/graph/build -Body (@{
  raw_file_id = "raw_xxx"
  force_rebuild = $false
  max_sections = 20
  max_nodes_per_section = 8
  use_llm = $true
} | ConvertTo-Json) -ContentType "application/json"
```

读取图谱和节点详情：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/graph?raw_file_id=raw_xxx&top_n=200"
Invoke-RestMethod "http://127.0.0.1:8010/api/graph/nodes/{node_id}"
```

未配置 LLM 时，后端会使用确定性兜底抽取，便于 demo 和测试继续推进。

构建多层 KG：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/kg/layers/build -Body (@{
  raw_file_id = "raw_xxx"
  force_rebuild = $false
  build_missing_concept_graph = $true
  use_llm = $true
} | ConvertTo-Json) -ContentType "application/json"
```

读取多层 KG：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/kg/layers?raw_file_id=raw_xxx"
```

当前阶段 6 只生成 `document_tree`、`concept_kg`、`evidence_graph`，其余层保持 reserved，等待后续阶段。

构建跨教材术语对齐：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/alignment/build -Body (@{
  raw_file_ids = @("raw_a", "raw_b")
  force_rebuild = $false
  min_confidence = 0.62
  include_singletons = $false
} | ConvertTo-Json) -ContentType "application/json"
```

读取术语对齐：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/alignment?raw_file_ids=raw_a,raw_b"
```

阶段 7 只输出 `ConceptCluster`、`CanonicalConcept`、`AliasRecord` 和对齐候选，不做 merge/remove 压缩决策。

构建跨教材整合与压缩决策：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/integration/build -Body (@{
  raw_file_ids = @("raw_a", "raw_b")
  force_rebuild = $false
  target_compression_ratio = 0.30
  alignment_min_confidence = 0.62
  include_keep_decisions = $true
} | ConvertTo-Json) -ContentType "application/json"
```

读取整合结果：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/integration?raw_file_ids=raw_a,raw_b"
```

阶段 8 输出 `merge/keep/remove/refine/conflict` 决策、`IntegratedConcept` 和 `CompressionStats`。`remove` 只表示从整合正文移出，不删除原始 KG 和证据。

GraphRAG 问答：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/graphrag/query -Body (@{
  question = "学习动作电位前要先学什么？"
  top_k = 5
  raw_file_ids = @("raw_a", "raw_b")
  include_decisions = $true
} | ConvertTo-Json) -ContentType "application/json"
```

GraphRAG 状态：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/graphrag/status?raw_file_ids=raw_a,raw_b"
```

阶段 9 返回 `citations`、`source_chunks`、`node_hits`、`paths` 和 `decisions`，用于回答定义、教材来源、差异、前置知识、关系路径和整合决策原因。

七本书全量 demo 数据集：

```powershell
Invoke-RestMethod "http://127.0.0.1:8010/api/datasets/seven-books"
```

该接口只返回七本书在正式数据目录中的状态和入口；前端拿到 `raw_file_ids` 后继续使用 `/api/textbooks`、`/api/graph`、`/api/rag`、`/api/alignment`、`/api/integration`、`/api/graphrag`。如果需要从 `materials\converted_textbooks` 重新准备七本书：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/datasets/seven-books/prepare -Body (@{
  force_rebuild = $false
  build_graph = $true
  build_layered_graph = $true
  build_rag = $true
  build_alignment = $true
  build_integration = $true
  use_llm = $false
} | ConvertTo-Json) -ContentType "application/json"
```

前端上传一个或多个文件并直接整理生成：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/workflows/organize -Form @{
  files = Get-Item .\book_a.md, .\book_b.md
  build_graph = $true
  build_layered_graphs = $true
  build_rag = $true
  build_alignment_graph = $true
  build_integration_result = $true
  use_llm = $false
}
```

返回 `job.id` 后轮询 `/api/jobs/{job_id}`；完成时 `job.result.raw_file_ids` 和 `job.result.endpoints` 就是正式读取入口。

教师覆盖整合决策：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/integration/decisions/{decision_id}/override -Body (@{
  raw_file_ids = @("raw_a", "raw_b")
  action = "conflict"
  retained_content = "教师要求保留两种说法，课堂上单独说明差异。"
  reason = "该合并存在教学风险，需要复核。"
  confidence = 1.0
  created_by = "teacher"
} | ConvertTo-Json) -ContentType "application/json"
```

教师对话修改：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/dialogue/messages -Body (@{
  raw_file_ids = @("raw_a", "raw_b")
  message = "请把 integration_decision_xxx 改为保留，避免误删课堂重点。"
  created_by = "teacher"
  retained_content = "教师要求保留该知识点。"
} | ConvertTo-Json) -ContentType "application/json"
```

前端对接接口清单见 `docs\后端接口对接清单.md`。

建立 RAG 证据索引：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/rag/index -Body (@{
  raw_file_ids = @("raw_xxx")
  force_rebuild = $true
} | ConvertTo-Json) -ContentType "application/json"
```

查询并返回引用：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/rag/query -Body (@{
  question = "动作电位是什么？"
  top_k = 5
  raw_file_ids = @("raw_xxx")
} | ConvertTo-Json) -ContentType "application/json"
```

当前 RAG 是本地混合 Evidence Index：BM25 + lightweight hash embedding + query coverage，先保证 `citations`、`source_chunks`、拒答和 benchmark 稳定，后续再替换为 FAISS / Chroma / 模型 embedding。

阶段 4 benchmark 结果会写入：

```text
data\indexes\stage4_rag_benchmark_latest.json
```

阶段 7 benchmark 结果会写入：

```text
data\alignments\stage7_alignment_benchmark_latest.json
```

阶段 8 benchmark 结果会写入：

```text
data\integrations\stage8_integration_benchmark_latest.json
```

阶段 9 benchmark 结果会写入：

```text
data\indexes\stage9_graphrag_benchmark_latest.json
```

## 前端启动

```powershell
cd D:\Hackathon\frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

## 当前已完成

- FastAPI + React/Vite 项目骨架。
- 后端 Pydantic 数据契约。
- 前端 TypeScript 数据契约。
- `/api/health`。
- `/api/textbooks/upload` mock 导入接口。
- `/api/jobs/{job_id}` mock 任务状态接口。
- `/api/textbooks` 和 `/api/textbooks/{raw_file_id}` 读取解析结果。
- 从 `materials/converted_textbooks` 导入一本教材并输出统一 JSON 到 `data/parsed`。
- 上传常见教学资料并输出统一 JSON 到 `data/parsed`。
- `/api/textbooks/upload-batch` 批量上传，单文件失败不会阻断其它文件。
- `/api/textbooks/{raw_file_id}/parse` 对已保存上传文件重新解析。
- `/api/rag/index`、`/api/rag/query` 本地混合证据索引。
- `/api/graph/build` 单本教材知识点和关系抽取。
- `/api/kg/layers/build` 多层 KG 基础构建。
- `/api/alignment/build` 跨教材术语对齐候选和 ConceptCluster。
- `/api/integration/build` 跨教材整合与压缩决策。
- `/api/graphrag/query` GraphRAG 问答，返回引用、知识点、路径和整合决策证据。
- `/api/integration/decisions/{decision_id}/override` 教师覆盖整合决策。
- `/api/dialogue/messages` 教师对话修改决策并记录历史。
- `/api/datasets/seven-books` 七本书全量 demo 数据集状态，使用正式数据目录和正式读取接口。
- `/api/workflows/organize` 前端上传一个或多个文件后，一键生成 parsed/KG/RAG/对齐/整合。
