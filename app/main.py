"""RAI (Resume-Agent-Interviewer) 后端入口。

启动：uvicorn app.main:app --reload --port 8000
"""
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import (routes_applications, routes_auth, routes_interview, routes_practice,
                     routes_report, routes_resume, routes_workbench)
from app.core.config import BASE_DIR, settings
from app.core.security import guard_http
from app.services.orchestrator import ORCHESTRATOR


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动时执行一次数据保留清理（RETENTION_DAYS=0 时跳过）
    try:
        from app.core.maintenance import sweep_expired

        stats = sweep_expired()
        if any(v for k, v in stats.items() if k != "skipped"):
            print(f"[RAI] 保留策略清理完成: {stats}")
    except Exception as e:  # noqa: BLE001
        print(f"[RAI] 保留策略清理失败: {e}")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Resume-Agent-Interviewer (RAI)",
        description="深度理解简历逻辑、具备工业级追问能力、可证伪评估报告的 AI 模拟面试官",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 请求级链路追踪：每个请求生成/透传 request_id，响应头可见
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 安全护栏：令牌 + 每日限额（未配置 ACCESS_TOKEN 时仅限流，本地开发零摩擦）
    guard = [Depends(guard_http)]
    app.include_router(routes_resume.router, dependencies=guard)
    app.include_router(routes_interview.router, dependencies=guard)
    app.include_router(routes_interview.ws_router)  # WebSocket 守卫在握手内完成
    app.include_router(routes_report.router, dependencies=guard)
    app.include_router(routes_workbench.router, dependencies=guard)
    app.include_router(routes_applications.router, dependencies=guard)
    app.include_router(routes_practice.router, dependencies=guard)
    app.include_router(routes_auth.router)

    @app.get("/api/health", tags=["system"])
    def health():
        return {
            "status": "ok",
            "llm_mode": "mock" if ORCHESTRATOR.llm.mock else "real",
            "llm_model": settings.llm_model,
            "knowledge_entries": len(ORCHESTRATOR.retriever.entries),
        }

    _mount_frontend(app)
    return app


def _mount_frontend(app: FastAPI) -> bool:
    """生产模式：托管前端构建产物（API 路由已先注册，优先匹配）。"""
    candidates = []
    if settings.static_dir:
        candidates.append(Path(settings.static_dir))
    candidates.append(BASE_DIR / "frontend" / "dist")
    candidates.append(BASE_DIR / "static")
    for c in candidates:
        if (c / "index.html").exists():
            app.mount("/", StaticFiles(directory=str(c), html=True), name="frontend")
            return True
    return False


app = create_app()
