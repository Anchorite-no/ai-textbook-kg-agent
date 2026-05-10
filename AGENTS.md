前后端契约协议（plan 17 摘要）

事实来源：backend/app/models/schemas.py → /openapi.json
GPT 必守：不准 rename / 不准删字段 / 加 endpoint 必须同步 schemas + 数据契约.md + openapi.snapshot.json
Claude 必守：不读 backend 代码做实现假设 / 不手改 api.generated.ts / 错误第一反应改 adapter 不改后端
错误格式：{ message, code, detail }
同步流程：GPT 推后端 → export_openapi → Claude 跑 sync:api → 修 adapter
未建接口：用 fixture，UI 不阻塞

当前后端 live 地址：http://127.0.0.1:8010
离线契约快照：docs/openapi.snapshot.json
导出命令：backend\.venv\Scripts\python.exe backend\scripts\export_openapi.py
契约相关 commit message 必须包含 [contract]
