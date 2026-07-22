"""兮克 SKS3200-8E2X 交换机 (192.168.10.12) 数据采集器。

采集方式：HTTP JSON API（MD5 认证登录）。
获取：温度、端口状态、端口流量统计。
"""
import hashlib
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Session cookie 缓存
_cookie: Optional[str] = None


def _md5(text: str) -> str:
    """计算 MD5 哈希。"""
    return hashlib.md5(text.encode()).hexdigest()


async def _login() -> Optional[str]:
    """登录交换机，返回 cookie 值。"""
    global _cookie
    usr_md5 = _md5(settings.switch_user)
    pwd_md5 = _md5(settings.switch_password)
    url = f"http://{settings.switch_host}/authorize?loginusr={usr_md5}&loginpwd={pwd_md5}"

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
            # 登录成功会返回 Set-Cookie
            cookies = resp.cookies
            if cookies:
                # httpx 的 cookies 对象，转为 jar
                _cookie = dict(cookies)
                return _cookie
            # 有时候返回的是重定向文本，但 cookie 已设置
            if resp.status_code == 200:
                _cookie = dict(resp.cookies) if resp.cookies else None
                return _cookie
    except Exception as e:
        logger.debug(f"交换机登录失败: {e}")
    _cookie = None
    return None


async def _api_get(path: str) -> Optional[dict]:
    """调用交换机 API。"""
    global _cookie
    url = f"http://{settings.switch_host}/{path}"

    try:
        async with httpx.AsyncClient(timeout=5, cookies=_cookie) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
    except Exception as e:
        logger.debug(f"交换机 API 调用失败 ({path}): {e}")
    return None


async def collect_switch() -> dict:
    """采集交换机状态。"""
    global _cookie

    result = {
        "name": "交换机 SKS3200",
        "ip": settings.switch_host,
        "status": "offline",
        "temperature": None,
        "firmware": None,
        "ports": [],
        "ports_up": None,
        "ports_total": None,
    }

    # 登录
    if not _cookie:
        await _login()
    if not _cookie:
        return result

    # 获取系统状态
    status_data = await _api_get("status.json")
    if status_data is None:
        # cookie 可能过期，重新登录
        await _login()
        if _cookie:
            status_data = await _api_get("status.json")

    if status_data is None:
        return result

    result["status"] = "online"
    result["temperature"] = int(status_data.get("temperature", 0)) if status_data.get("temperature") else None
    result["firmware"] = status_data.get("fw_ver")

    # 获取端口统计
    port_data = await _api_get("port_statistics.json")
    if port_data:
        port_num = int(port_data.get("PortNum", 10))
        ports = []
        up_count = 0

        for i in range(1, port_num + 1):
            port_key = f"Port_{i}"
            port_info = port_data.get(port_key, {})
            link_status = port_info.get("Link_Status", "Link Down")
            is_up = "Link Down" not in link_status

            port_entry = {
                "id": i,
                "link": link_status,
                "tx_pkts": int(port_info.get("TxGoodPkt", 0)),
                "rx_pkts": int(port_info.get("RxGoodPkt", 0)),
                "tx_bad": int(port_info.get("TxBadPkt", 0)),
                "rx_bad": int(port_info.get("RxBadPkt", 0)),
            }
            ports.append(port_entry)

            if is_up:
                up_count += 1

        result["ports"] = ports
        result["ports_up"] = up_count
        result["ports_total"] = port_num

    return result
