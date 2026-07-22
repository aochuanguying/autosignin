import asyncio
import logging
from datetime import datetime
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# 内存缓存：最新采集数据
_current_status: dict[str, Any] = {
    "devices": {},
    "connectivity": {},
    "timestamp": None,
}

# SSE 订阅者队列列表
_subscribers: list[asyncio.Queue] = []


def get_status() -> dict[str, Any]:
    """获取当前缓存的状态数据。"""
    return _current_status.copy()


def subscribe() -> asyncio.Queue:
    """订阅数据更新，返回一个队列。"""
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _subscribers.append(queue)
    return queue


def _notify_subscribers(data: dict[str, Any]):
    """向所有订阅者推送数据。"""
    disconnected = []
    for queue in _subscribers:
        try:
            queue.put_nowait(data)
        except asyncio.QueueFull:
            # 队列满了说明客户端消费太慢，跳过
            pass
        except Exception:
            disconnected.append(queue)
    for q in disconnected:
        _subscribers.remove(q)


async def start_collector():
    """采集调度器主循环。"""
    from app.collectors.router import collect_router
    from app.collectors.gateway import collect_gateway
    from app.collectors.nas import collect_nas
    from app.collectors.local import collect_local
    from app.collectors.ont import collect_ont
    from app.collectors.switch import collect_switch
    from app.collectors.connectivity import collect_connectivity

    global _current_status

    logger.info(f"采集器启动，间隔 {settings.poll_interval}s")

    while True:
        try:
            # 并发采集所有数据
            results = await asyncio.gather(
                collect_router(),
                collect_gateway(),
                collect_nas(),
                collect_local(),
                collect_ont(),
                collect_switch(),
                collect_connectivity(),
                return_exceptions=True,
            )

            # 解析结果
            devices = {}
            connectivity = {}

            # 主路由
            if isinstance(results[0], dict):
                devices["router"] = results[0]
            else:
                logger.error(f"主路由采集异常: {results[0]}")
                devices["router"] = {"status": "error", "error": str(results[0])}

            # 旁路由
            if isinstance(results[1], dict):
                devices["gateway"] = results[1]
            else:
                logger.error(f"旁路由采集异常: {results[1]}")
                devices["gateway"] = {"status": "error", "error": str(results[1])}

            # NAS
            if isinstance(results[2], dict):
                devices["nas"] = results[2]
            else:
                logger.error(f"NAS采集异常: {results[2]}")
                devices["nas"] = {"status": "error", "error": str(results[2])}

            # X5-Server
            if isinstance(results[3], dict):
                devices["x5server"] = results[3]
            else:
                logger.error(f"X5-Server 采集异常：{results[3]}")
                devices["x5server"] = {"status": "error", "error": str(results[3])}

            # 光猫
            if isinstance(results[4], dict):
                devices["ont"] = results[4]
            else:
                logger.error(f"光猫采集异常：{results[4]}")
                devices["ont"] = {"status": "error", "error": str(results[4])}

            # 交换机
            if isinstance(results[5], dict):
                devices["switch"] = results[5]
            else:
                logger.error(f"交换机采集异常：{results[5]}")
                devices["switch"] = {"status": "error", "error": str(results[5])}

            # 连通性
            if isinstance(results[6], dict):
                connectivity = results[6]
            else:
                logger.error(f"连通性探测异常：{results[6]}")
                connectivity = {"error": str(results[6])}

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _current_status = {
                "devices": devices,
                "connectivity": connectivity,
                "timestamp": now,
            }

            # 通知所有 SSE 客户端
            _notify_subscribers(_current_status)
            logger.debug(f"采集完成: {now}")

        except Exception as e:
            logger.error(f"采集循环异常: {e}")

        await asyncio.sleep(settings.poll_interval)
