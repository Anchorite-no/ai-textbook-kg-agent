# 阶段 9 GraphRAG 问答审计

## 阶段边界

阶段 9 是查询方法层，不引入外部重型 GraphRAG 框架，也不替代已有图层。它组合已有资产：

- 阶段 4：`Chunk` Evidence Index。
- 阶段 5/6：`KnowledgeNode`、`KnowledgeEdge`、Concept KG、Evidence Graph。
- 阶段 7：Alias / Alignment。
- 阶段 8：`IntegrationDecision`。

## 当前实现

- API：`GET /api/graphrag/status`、`POST /api/graphrag/query`。
- 响应：`GraphRagQueryResponse`。
- 输出：`answer`、`citations`、`source_chunks`、`node_hits`、`paths`、`decisions`。
- 查询链路：术语识别 -> alias 扩展 -> chunk 检索 -> node 检索 -> graph path -> decision lookup -> evidence rerank。

## 问题清单对齐

| 问题 | 当前回答 | 验证方式 |
| --- | --- | --- |
| 如何查找相关知识点？ | 先用 node name/alias/canonical 精确匹配，再用 token overlap 补充。 | `node_hit_rate` |
| 如何结合 RAG 和图谱？ | 先调用阶段 4 chunk 检索，再补 node evidence、edge evidence 和 decision evidence。 | `citation_grounding_rate` |
| 如何展示知识路径？ | `GraphRagPath.steps` 返回节点、关系类型、边证据和 `source_locator`。 | `path_question_hit_rate` |
| 如何处理比较问题？ | 按教材分组展示同一 canonical/alias 下的节点定义和来源。 | comparison case |
| 如何处理前置知识？ | 优先用 `PREREQUISITE_OF`，必要时用原文“X 是 Y 的基础/前提”兜底。 | prerequisite case |
| 如何解释合并/删除？ | 查询 `IntegrationDecision`，返回 action、reason、retained/removed 和证据。 | `decision_question_hit_rate` |
| 如何拒答？ | 无 chunk 命中且无精确术语命中时拒答；低 coverage 的混合关系问题拒答。 | `no_answer_rejection_rate` |

## Benchmark

命令：

```powershell
cd D:\Hackathon
$env:PYTHONPATH=(Resolve-Path backend).Path
backend\.venv\Scripts\python.exe backend\scripts\benchmark_00_stage9_graphrag.py
```

最近一次结果：

```json
{
  "question_count": 9,
  "answerable_count": 7,
  "no_answer_count": 2,
  "citation_grounding_rate": 1.0,
  "node_hit_rate": 1.0,
  "path_question_hit_rate": 1.0,
  "decision_question_hit_rate": 1.0,
  "answer_term_hit_rate": 1.0,
  "no_answer_rejection_rate": 1.0
}
```

## 剩余风险

- 当前答案是确定性拼装，优先安全和证据链；后续若接 LLM，需要严格限制只能基于 `citations/node_hits/paths/decisions` 回答。
- 路径搜索当前是轻量 BFS，不做图社区摘要或复杂规划。
- 兜底抽取产生的部分节点名仍可能偏粗糙，GraphRAG 已做拒答和前置路径过滤，但后续需要继续增强知识抽取质量。
