"""连通性探测器。

探测三条关键链路：翻墙(Google)、国内直连(百度)、公司内网。

翻墙和内网探测通过旁路由 SSH 执行 curl，因为：
- X5-Server 网关是主路由(192.168.50.1)，不走代理
- 旁路由才是透明代理节点，从它发请求才能验证代理链路
- 直连（百度）从本地发即可验证基本网络连通性
"""
import asyncio
import logging
import time

import asyncssh
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


async def _probe_local(url: str, timeout: int) -> dict:
    """本地 HTTP 探测。"""
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
        return {"url": url, "status": "timeout", "status_code": None, "latency_ms": None}
    except Exception as e:
        return {"url": url, "status": "error", "status_code": None, "latency_ms": None, "error": str(e)}


async def _probe_via_gateway(url: str, timeout: int) -> dict:
    """通过旁路由 SSH 执行 curl 探测。"""
    try:
        async with asyncssh.connect(
            settings.gateway_host,
            port=settings.gateway_ssh_port,
            username=settings.gateway_ssh_user,
            password=settings.gateway_ssh_password,
            known_hosts=None,
            connect_timeout=5,
        ) as conn:
            cmd = f'curl -so /dev/null -w "%{{http_code}} %{{time_total}}" --max-time {timeout} -L -k "{url}"'
            r = await asyncio.wait_for(conn.run(cmd, timeout=timeout + 3), timeout=timeout + 5)

            output = (r.stdout or "").strip()
            if output and " " in output:
                parts = output.split()
                status_code = int(parts[0])
                latency_ms = round(float(parts[1]) * 1000)
                return {
                    "url": url,
                    "status": "ok" if status_code == 200 else "error",
                    "status_code": status_code,
                    "latency_ms": latency_ms,
                }
            else:
                # curl 超时时返回 000
                if output.startswith("000"):
                    return {"url": url, "status": "timeout", "status_code": None, "latency_ms": None}
                return {"url": url, "status": "error", "status_code": None, "latency_ms": None, "error": output}

    except asyncio.TimeoutError:
        return {"url": url, "status": "timeout", "status_code": None, "latency_ms": None}
    except Exception as e:
        logger.debug(f"旁路由探测失败: {e}")
        return {"url": url, "status": "error", "status_code": None, "latency_ms": None, "error": str(e)}


async def collect_connectivity() -> dict:
    """并发探测所有链路连通性。"""
    results = await asyncio.gather(
        _probe_via_gateway(settings.probe_google, settings.probe_timeout),
        _probe_local(settings.probe_baidu, 5),
        _probe_via_gateway(settings.probe_office, settings.probe_timeout),
    )

    return {
        "proxy": results[0],    # 翻墙（通过旁路由）
        "direct": results[1],   # 国内直连（本地）
        "office": results[2],   # 公司内网（通过旁路由）
    }
