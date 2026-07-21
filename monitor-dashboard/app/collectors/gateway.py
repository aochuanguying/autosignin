"""旁路由 倍控 G31 (192.168.50.2) 数据采集器。

采集方式：SSH 命令获取 CPU/内存/温度/流量、服务状态、conntrack、运行时间。
系统：Debian 13, Intel N305 5核, 4G RAM, enp2s0 网口
"""
import asyncio
import logging
import time
from typing import Optional

import asyncssh

from app.config import settings

logger = logging.getLogger(__name__)

# 上次流量字节数和时间，用于计算速率
_last_rx_bytes: Optional[int] = None
_last_tx_bytes: Optional[int] = None
_last_time: Optional[float] = None


async def collect_gateway() -> dict:
    """采集旁路由状态。"""
    global _last_rx_bytes, _last_tx_bytes, _last_time

    result = {
        "name": "旁路由 G31",
        "ip": settings.gateway_host,
        "status": "offline",
        "cpu_percent": None,
        "mem_percent": None,
        "cpu_temp": None,
        "xray_status": None,
        "mosdns_status": None,
        "nginx_status": None,
        "conntrack_count": None,
        "conntrack_max": None,
        "rx_rate": None,
        "tx_rate": None,
        "uptime": None,
    }

    try:
        async with asyncssh.connect(
            settings.gateway_host,
            port=settings.gateway_ssh_port,
            username=settings.gateway_ssh_user,
            password=settings.gateway_ssh_password,
            known_hosts=None,
            connect_timeout=settings.ssh_timeout,
        ) as conn:
            result["status"] = "online"

            # 一次性执行所有命令
            cmd = (
                "top -bn1 | grep 'Cpu(s)' | head -1; "
                "free | grep Mem; "
                "cat /sys/class/thermal/thermal_zone0/temp; "
                "systemctl is-active xray; "
                "systemctl is-active mosdns; "
                "systemctl is-active nginx; "
                "cat /proc/sys/net/netfilter/nf_conntrack_count; "
                "cat /proc/sys/net/netfilter/nf_conntrack_max; "
                "cat /sys/class/net/enp2s0/statistics/rx_bytes; "
                "cat /sys/class/net/enp2s0/statistics/tx_bytes; "
                "cat /proc/uptime"
            )

            r = await conn.run(cmd, timeout=settings.ssh_timeout)

            if r.exit_status == 0 and r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                # Line 0: %Cpu(s):  1.8 us,  1.8 sy, ... 96.5 id, ...
                # Line 1: Mem:  3665  682  753  1  2500  2982
                # Line 2: 27800 (millidegrees)
                # Line 3: active (xray)
                # Line 4: active (mosdns)
                # Line 5: active (nginx)
                # Line 6: conntrack_count
                # Line 7: conntrack_max
                # Line 8: rx_bytes
                # Line 9: tx_bytes
                # Line 10: uptime

                if len(lines) >= 11:
                    # CPU（从 idle 计算）
                    try:
                        cpu_line = lines[0]
                        # 格式: %Cpu(s):  1.8 us,  1.8 sy, 0.0 ni, 96.5 id, ...
                        for part in cpu_line.split(","):
                            if "id" in part:
                                idle = float(part.strip().split()[0])
                                result["cpu_percent"] = round(100 - idle, 1)
                                break
                    except (ValueError, IndexError):
                        pass

                    # 内存
                    try:
                        parts = lines[1].split()
                        # Mem: total used free shared buff/cache available
                        total = int(parts[1])
                        used = int(parts[2])
                        if total > 0:
                            result["mem_percent"] = round(
                                (used / total) * 100, 1
                            )
                    except (ValueError, IndexError):
                        pass

                    # CPU 温度
                    try:
                        temp_raw = int(lines[2].strip())
                        result["cpu_temp"] = round(temp_raw / 1000, 1)
                    except (ValueError, IndexError):
                        pass

                    # 服务状态
                    result["xray_status"] = lines[3].strip()
                    result["mosdns_status"] = lines[4].strip()
                    result["nginx_status"] = lines[5].strip()

                    # 连接跟踪
                    try:
                        result["conntrack_count"] = int(lines[6].strip())
                        result["conntrack_max"] = int(lines[7].strip())
                    except (ValueError, IndexError):
                        pass

                    # 网口流量速率
                    try:
                        rx_bytes = int(lines[8].strip())
                        tx_bytes = int(lines[9].strip())
                        now = time.time()

                        if _last_rx_bytes is not None and _last_time is not None:
                            elapsed = now - _last_time
                            if elapsed > 0:
                                result["rx_rate"] = round(
                                    (rx_bytes - _last_rx_bytes) / elapsed, 1
                                )
                                result["tx_rate"] = round(
                                    (tx_bytes - _last_tx_bytes) / elapsed, 1
                                )

                        _last_rx_bytes = rx_bytes
                        _last_tx_bytes = tx_bytes
                        _last_time = now
                    except (ValueError, IndexError):
                        pass

                    # 运行时间
                    try:
                        uptime_sec = float(lines[10].split()[0])
                        result["uptime"] = int(uptime_sec)
                    except (ValueError, IndexError):
                        pass

    except asyncio.TimeoutError:
        logger.warning(f"旁路由 SSH 连接超时: {settings.gateway_host}")
    except Exception as e:
        logger.warning(f"旁路由采集失败: {e}")

    return result
