"""面试对话路由：REST + WebSocket 流式。"""
import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.schemas.interview import (MessageRequest, MessageResponse, SessionStateResponse,
                                   StartResponse)
from app.services.orchestrator import (ORCHESTRATOR, InterviewFinished, SessionNotFound)

router = APIRouter(tags=["interview"])


def _map_orchestrator_error(e: Exception) -> HTTPException:
    if isinstance(e, SessionNotFound):
        return HTTPException(status_code=404, detail="会话不存在，请先上传简历")
    if isinstance(e, InterviewFinished):
        return HTTPException(status_code=409, detail="面试已结束，请查看评估报告")
    return HTTPException(status_code=500, detail=str(e))


@router.post("/api/interview/{session_id}/start", response_model=StartResponse)
def start_interview(session_id: str):
    try:
        r = ORCHESTRATOR.start(session_id)
    except (SessionNotFound, InterviewFinished) as e:
        raise _map_orchestrator_error(e) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return r


@router.post("/api/interview/{session_id}/message", response_model=MessageResponse)
def send_message(session_id: str, body: MessageRequest):
    try:
        r = ORCHESTRATOR.handle_message(session_id, body.message)
    except (SessionNotFound, InterviewFinished) as e:
        raise _map_orchestrator_error(e) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(e)) from e
    return r


@router.get("/api/interview/{session_id}/state", response_model=SessionStateResponse)
def get_state(session_id: str):
    try:
        return ORCHESTRATOR.state_payload(session_id)
    except SessionNotFound as e:
        raise _map_orchestrator_error(e) from e


@router.websocket("/ws/interview/{session_id}")
async def ws_interview(websocket: WebSocket, session_id: str):
    """流式面试通道。

    帧协议（JSON）：
      客户端 -> {"type": "start"} 或 {"type": "message", "data": "..."}
      服务端 <- {"type": "token", "data": "片段"} x N 后接 {"type": "final", ...完整元数据}
    """
    await websocket.accept()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def emit(chunk: str) -> None:
        loop.call_soon_threadsafe(queue.put_nowait, chunk)

    try:
        first = await websocket.receive_json()
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
