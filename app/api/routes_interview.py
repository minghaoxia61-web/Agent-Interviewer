"""面试对话路由：REST + WebSocket 流式。"""
import asyncio

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import limiter, guard_ws, ensure_owner, visitor_id_ws
from app.schemas.interview import (MessageRequest, MessageResponse, SessionStateResponse,
                                   StartResponse)
from app.services.orchestrator import (ORCHESTRATOR, AnalysisInProgress,
                                       InterviewFinished, SessionNotFound)
from app.storage.session_store import STORE

router = APIRouter(tags=["interview"])
ws_router = APIRouter(tags=["interview-ws"])


def _require_owned(session_id: str, request: Request):
    """归属预校验：不存在/不属于当前访客一律 404。"""
    sess = STORE.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    if sess.owner and sess.owner != (request.headers.get("X-Visitor-Id")
                                     or request.query_params.get("vid") or "anonymous"):
        raise HTTPException(status_code=404, detail="会话不存在")
    return sess


def _map_orchestrator_error(e: Exception) -> HTTPException:
    if isinstance(e, SessionNotFound):
        return HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    if isinstance(e, InterviewFinished):
        return HTTPException(status_code=409, detail="面试已结束，请查看评估报告")
    if isinstance(e, AnalysisInProgress):
        return HTTPException(status_code=409, detail="简历 AI 分析仍在进行中，请稍候几秒再开始面试")
    return HTTPException(status_code=500, detail=str(e))


@router.post("/api/interview/{session_id}/start", response_model=StartResponse)
def start_interview(session_id: str, request: Request):
    _require_owned(session_id, request)
    try:
        r = ORCHESTRATOR.start(session_id)
    except (SessionNotFound, InterviewFinished, AnalysisInProgress) as e:
        raise _map_orchestrator_error(e) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return r


@router.post("/api/interview/{session_id}/message", response_model=MessageResponse)
def send_message(session_id: str, body: MessageRequest, request: Request):
    _require_owned(session_id, request)
    try:
        r = ORCHESTRATOR.handle_message(session_id, body.message)
    except (SessionNotFound, InterviewFinished, AnalysisInProgress) as e:
        raise _map_orchestrator_error(e) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return r


@router.get("/api/interview/{session_id}/state", response_model=SessionStateResponse)
def get_state(session_id: str, request: Request):
    _require_owned(session_id, request)
    try:
        return ORCHESTRATOR.state_payload(session_id)
    except SessionNotFound as e:
        raise _map_orchestrator_error(e) from e


@ws_router.websocket("/ws/interview/{session_id}")
async def ws_interview(websocket: WebSocket, session_id: str):
    """流式面试通道。

    帧协议（JSON）：
      客户端 -> {"type": "start"} 或 {"type": "message", "data": "..."}
      服务端 <- {"type": "token", "data": "片段"} x N 后接 {"type": "final", ...完整元数据}

    鉴权：配置了 ACCESS_TOKEN 时握手需带 ?token=；每条消息计入当日限额。
    """
    if not guard_ws(websocket):
        await websocket.accept()
        await websocket.close(code=4401, reason="missing or invalid token")
        return
    sess = STORE.get(session_id)
    if sess is None:
        await websocket.accept()
        await websocket.close(code=4404, reason="session not found")
        return
    if sess.owner and sess.owner != visitor_id_ws(websocket):
        await websocket.accept()
        await websocket.close(code=4403, reason="not your session")
        return
    ws_ip = websocket.client.host if websocket.client else "unknown"

    async def _limited() -> bool:
        # limiter 非线程安全仅靠 GIL 粗粒度可靠，demo 场景可接受
        return limiter.hit(f"ws:{ws_ip}", settings.rate_limit_daily)

    await websocket.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(chunk: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, chunk)

    try:
        first = await websocket.receive_json()
        if not await _limited():
            await websocket.send_json({"type": "error", "message": "今日调用已达上限，请明天再试"})
            await websocket.close()
            return
        if first.get("type") == "start":
            result = await asyncio.to_thread(ORCHESTRATOR.start, session_id)
            text = result["assistant_message"]
            for i in range(0, len(text), 8):
                await websocket.send_json({"type": "token", "data": text[i:i + 8]})
            await websocket.send_json({"type": "final", **result})

        while True:
            msg = await websocket.receive_json()
            if msg.get("type") != "message":
                continue
            if not await _limited():
                await websocket.send_json({"type": "error", "message": "今日调用已达上限，请明天再试"})
                continue
            payload = str(msg.get("data", ""))
            task = asyncio.create_task(
                asyncio.to_thread(ORCHESTRATOR.handle_message, session_id, payload, emit)
            )
            while not task.done() or not queue.empty():
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=0.05)
                    await websocket.send_json({"type": "token", "data": chunk})
                except asyncio.TimeoutError:
                    continue
            result = task.result()
            await websocket.send_json({"type": "final", **result})
    except WebSocketDisconnect:
        return
    except Exception as e:  # noqa: BLE001
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass
