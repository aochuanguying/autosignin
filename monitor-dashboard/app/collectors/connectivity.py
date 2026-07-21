"""连通性探测器。

探测三条关键链路：翻墙(Google)、国内直连(百度)、公司内网。
"""
import asyncio
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def _probe(url: str, timeout: int) -> dict:
    """HTTP GET 探测，返回状态和延迟。"""
    try:
        start = time.monotonic()
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
        ) as client:
            resp = await client.get(url)
            elapsed_ms = round((time.monotonic() - start) * 1000)
            return {
                "url": url,
                "status": "ok" if resp.status_code == 200 else "error",
                "status_code": resp.status_code,
                "latency_ms": elapsed_ms,
            }
    except httpx.TimeoutException:
        return {
            "url": url,
            "status": "timeout",
            "status_code": None,
            "latency_ms": None,
        }
    except Exception as e:
        return {
            "url": url,
            "status": "error",
            "status_code": None,
            "latency_ms": None,
            "error": str(e),
        }


async def collect_connectivity() -> dict:
    """并发探测所有链路连通性。"""
    results = await asyncio.gather(
        _probe(settings.probe_google, settings.probe_timeout),
        _probe(settings.probe_baidu, 5),
        _probe(settings.probe_office, settings.probe_timeout),
    )

    return {
        "proxy": results[0],    # 翻墙
        "direct": results[1],   # 国内直连
        "office": results[2],   # 公司内网
    }
