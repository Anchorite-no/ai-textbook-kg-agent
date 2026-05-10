from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import graph, health, jobs, kg, rag, textbooks, uploads
from app.core.config import settings
from app.models.schemas import ApiErrorResponse


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="学科知识整合智能体 API：多格式解析、统一 JSON、证据链和任务状态接口。",
        responses={
            400: {"model": ApiErrorResponse},
            404: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
        },
    )
    _install_exception_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(textbooks.router, prefix=settings.api_prefix)
    app.include_router(uploads.router, prefix=settings.api_prefix)
    app.include_router(graph.router, prefix=settings.api_prefix)
    app.include_router(kg.router, prefix=settings.api_prefix)
    app.include_router(rag.router, prefix=settings.api_prefix)
    app.include_router(jobs.router, prefix=settings.api_prefix)
    return app


def _install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def normalize_http_exception(_request: Request, exc: HTTPException) -> JSONResponse:
        payload = _error_payload(exc.detail, f"HTTP_{exc.status_code}")
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def normalize_validation_exception(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "message": "请求参数校验失败",
                "code": "VALIDATION_ERROR",
                "detail": str(exc),
            },
        )


def _error_payload(detail: Any, fallback_code: str) -> dict[str, str | None]:
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail") or "请求失败"
        code = detail.get("code") or fallback_code
        extra_detail = detail.get("detail")
        return {
            "message": str(message),
            "code": str(code),
            "detail": None if extra_detail is None else str(extra_detail),
        }
    return {
        "message": str(detail),
        "code": fallback_code,
        "detail": str(detail),
    }


app = create_app()
