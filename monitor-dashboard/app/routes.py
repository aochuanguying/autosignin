import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.collector import get_status, subscribe

router = APIRouter()


@router.get("/health")
async def health():
    """健康检查端点，供 Docker 和 Uptime Kuma 监控。"""
    status = get_status()
    return {
        "status": "ok",
        "last_poll": status.get("timestamp"),
    }


@router.get("/api/status")
async def api_status():
    """返回当前缓存的全量状态数据快照。"""
    return get_status()


@router.get("/api/events")
async def api_events(request: Request):
    """SSE 端点，实时推送数据更新。"""

    async def event_generator():
        queue = subscribe()
        try:
            # 立即推送当前数据
            current = get_status()
            yield {"event": "status", "data": json.dumps(current, ensure_ascii=False)}

            # 持续等待新数据
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {"event": "status", "data": json.dumps(data, ensure_ascii=False)}
                except asyncio.TimeoutError:
                    # 发送心跳保持连接
                    yield {"event": "ping", "data": ""}
        except asyncio.CancelledError:
            pass

    return EventSourceResponse(event_generator())
