from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import GraphRagQueryRequest, GraphRagQueryResponse, GraphRagStatus
from app.services.graphrag_query import get_graphrag_status, query_graphrag


router = APIRouter(prefix="/graphrag", tags=["graphrag"])


@router.get("/status", response_model=GraphRagStatus)
def graph_rag_status(raw_file_ids: str | None = None) -> GraphRagStatus:
    ids = [item.strip() for item in raw_file_ids.split(",") if item.strip()] if raw_file_ids else []
    return get_graphrag_status(ids)


@router.post("/query", response_model=GraphRagQueryResponse)
def graph_rag_query(payload: GraphRagQueryRequest) -> GraphRagQueryResponse:
    try:
        return query_graphrag(payload)
    except Exception as exc:  # noqa: BLE001 - keep normalized API error shape.
        raise HTTPException(
            status_code=400,
            detail={"message": "GraphRAG 查询失败", "code": "GRAPHRAG_QUERY_FAILED", "detail": str(exc)},
        ) from exc
