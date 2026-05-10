# 学科知识整合智能体

第一阶段目标是先跑通统一数据契约和证据链：`RawFile -> DocumentElement -> Section -> Chunk`。

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

上传解析文件：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8010/api/textbooks/upload -Form @{
  file = Get-Item .\sample.md
}
```

当前计划 02 支持：`txt`、`md`、`pdf`、`docx`、`xlsx`、`csv`、`pptx`。

查看已解析教材：

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/textbooks
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
