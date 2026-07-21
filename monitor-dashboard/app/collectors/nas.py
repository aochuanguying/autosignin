"""NAS 群晖 DS218+ (192.168.50.50) 数据采集器。

采集方式：Synology DSM API (HTTPS 8088 端口)
获取：CPU、内存、磁盘使用率、系统温度、硬盘温度、卷状态、运行时间
"""
import asyncio
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# DSM API session ID 缓存
_sid: Optional[str] = None


async def _ping(host: str, timeout: int = 3) -> bool:
    """ICMP ping 检测主机是否在线。"""
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", str(timeout), host,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    code = await proc.wait()
    return code == 0


async def _api_call(path: str, params: dict) -> Optional[dict]:
    """调用 DSM API。"""
    url = f"{settings.nas_base_url}/webapi/{path}"
    try:
        async with httpx.AsyncClient(timeout=settings.ssh_timeout, verify=False) as client:
            resp = await client.get(url, params=params)
            data = resp.json()
            if data.get("success"):
                return data.get("data")
            else:
                logger.debug(f"NAS API 失败: {data}")
    except Exception as e:
        logger.debug(f"NAS API 调用失败: {e}")
    return None


async def _login() -> Optional[str]:
    """登录 DSM API 获取 session ID。"""
    global _sid
    params = {
        "api": "SYNO.API.Auth",
        "version": "6",
        "method": "login",
        "account": settings.nas_user,
        "passwd": settings.nas_password,
        "format": "sid",
    }
    data = await _api_call("auth.cgi", params)
    if data:
        _sid = data.get("sid")
        return _sid
    _sid = None
    return None


async def _get_utilization(sid: str) -> Optional[dict]:
    """获取系统资源利用率。"""
    params = {
        "api": "SYNO.Core.System.Utilization",
        "version": "1",
        "method": "get",
        "_sid": sid,
    }
    return await _api_call("entry.cgi", params)


async def _get_system_info(sid: str) -> Optional[dict]:
    """获取系统信息（温度、运行时间等）。"""
    params = {
        "api": "SYNO.Core.System",
        "version": "3",
        "method": "info",
        "_sid": sid,
    }
    return await _api_call("entry.cgi", params)


async def _get_storage(sid: str) -> Optional[dict]:
    """获取存储信息。"""
    params = {
        "api": "SYNO.Storage.CGI.Storage",
        "version": "1",
        "method": "load_info",
        "_sid": sid,
    }
    return await _api_call("entry.cgi", params)


async def collect_nas() -> dict:
    """采集 NAS 状态。"""
    global _sid

    result = {
        "name": "NAS DS218+",
        "ip": settings.nas_host,
        "status": "offline",
        "cpu_percent": None,
        "mem_percent": None,
        "sys_temp": None,
        "disk_used_percent": None,
        "disk_used": None,
        "disk_total": None,
        "volume_status": None,
        "disk1_temp": None,
        "disk2_temp": None,
        "rx_rate": None,
        "tx_rate": None,
        "uptime": None,
    }

    # 先检查是否在线
    online = await _ping(settings.nas_host)
    if not online:
        return result

    result["status"] = "online"

    # 尝试用已有 session，失败则重新登录
    if not _sid:
        await _login()

    if not _sid:
        return result

    # 并发获取三个 API
    util_data, sys_data, storage_data = await asyncio.gather(
        _get_utilization(_sid),
        _get_system_info(_sid),
        _get_storage(_sid),
    )

    # 如果全部失败，可能 session 过期，重新登录再试一次
    if util_data is None and sys_data is None and storage_data is None:
        await _login()
        if _sid:
            util_data, sys_data, storage_data = await asyncio.gather(
                _get_utilization(_sid),
                _get_system_info(_sid),
                _get_storage(_sid),
            )

    # 解析资源利用率
    if util_data:
        cpu = util_data.get("cpu", {})
        user_load = cpu.get("user_load", 0)
        system_load = cpu.get("system_load", 0)
        result["cpu_percent"] = user_load + system_load

        mem = util_data.get("memory", {})
        real_usage = mem.get("real_usage")
        if real_usage is not None:
            result["mem_percent"] = real_usage

        # 网络流量（API 返回的 rx/tx 已经是 bytes/s）
        network = util_data.get("network", [])
        for net in network:
            if net.get("device") == "total":
                rx = net.get("rx")
                tx = net.get("tx")
                if rx is not None:
                    result["rx_rate"] = float(rx)
                if tx is not None:
                    result["tx_rate"] = float(tx)
                break

    # 解析系统信息
    if sys_data:
        result["sys_temp"] = sys_data.get("sys_temp")
        uptime_str = sys_data.get("up_time", "")
        # 格式 "15:42:15" 或秒数
        if uptime_str:
            try:
                if ":" in str(uptime_str):
                    parts = str(uptime_str).split(":")
                    if len(parts) == 3:
                        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
                        result["uptime"] = h * 3600 + m * 60 + s
                else:
                    result["uptime"] = int(uptime_str)
            except (ValueError, IndexError):
                pass

    # 解析存储信息
    if storage_data:
        volumes = storage_data.get("volumes", [])
        if volumes:
            vol = volumes[0]
            result["volume_status"] = vol.get("status")
            size = vol.get("size", {})
            try:
                total = int(size.get("total", 0))
                used = int(size.get("used", 0))
                if total > 0:
                    result["disk_total"] = total
                    result["disk_used"] = used
                    result["disk_used_percent"] = round(
                        (used / total) * 100, 1
                    )
            except (ValueError, TypeError):
                pass

        disks = storage_data.get("disks", [])
        if len(disks) >= 1:
            result["disk1_temp"] = disks[0].get("temp")
        if len(disks) >= 2:
            result["disk2_temp"] = disks[1].get("temp")

    return result
