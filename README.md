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

计划 02 后端烟测：

```powershell
cd D:\Hackathon
$env:PYTHONPATH=(Resolve-Path backend).Path
backend\.venv\Scripts\python.exe backend\scripts\smoke_phase2.py
backend\.venv\Scripts\python.exe backend\scripts\smoke_00_stage3_async.py
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
