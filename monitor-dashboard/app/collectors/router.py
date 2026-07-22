"""主路由 BE86U (192.168.50.1) 数据采集器。

采集方式：SSH 获取 CPU、内存、公网 IP、WAN 流量、在线设备数。
固件：ASUSWRT-Merlin-KoolShare (aarch64)
"""
import asyncio
import logging
import time
from typing import Optional

import asyncssh

from app.config import settings

logger = logging.getLogger(__name__)

# 上次采集的流量字节数和时间，用于计算速率
_last_rx_bytes: Optional[int] = None
_last_tx_bytes: Optional[int] = None
_last_time: Optional[float] = None


async def _ping(host: str, timeout: int = 3) -> bool:
    """ICMP ping 检测主机是否在线。"""
    proc = await asyncio.create_subprocess_exec(
        "ping", "-c", "1", "-W", str(timeout), host,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    code = await proc.wait()
    return code == 0


async def collect_router() -> dict:
    """采集主路由状态。"""
    global _last_rx_bytes, _last_tx_bytes, _last_time

    result = {
        "name": "主路由 BE86U",
        "ip": settings.router_host,
        "status": "offline",
        "cpu_percent": None,
        "mem_percent": None,
        "cpu_temp": None,
        "wan_ip": None,
        "rx_rate": None,
        "tx_rate": None,
        "clients": None,
        "uptime": None,
    }

    # 先 ping 检测
    online = await _ping(settings.router_host)
    if not online:
        return result

    result["status"] = "online"

    # SSH 采集详细数据
    try:
        async with asyncssh.connect(
            settings.router_host,
            port=settings.router_ssh_port,
            username=settings.router_ssh_user,
            password=settings.router_ssh_password,
            known_hosts=None,
            connect_timeout=10,
        ) as conn:
            # 一次性执行所有命令，减少 SSH 开销
            cmd = (
                "top -bn1 | grep 'CPU:' | head -1; "
                "free | grep Mem; "
                "nvram get wan0_ipaddr; "
                "cat /sys/class/net/eth0/statistics/rx_bytes; "
                "cat /sys/class/net/eth0/statistics/tx_bytes; "
                "arp -a | wc -l; "
                "cat /proc/uptime; "
                "cat /sys/class/thermal/thermal_zone0/temp"
            )
            r = await conn.run(cmd, timeout=10)

            if r.exit_status == 0 and r.stdout.strip():
                lines = r.stdout.strip().split("\n")
                # 解析各行数据
                # Line 0: CPU: 0.0% usr  2.3% sys  0.0% nic 97.6% idle ...
                # Line 1: Mem:  1017300  633696  383604  4636  11856  53032
                # Line 2: 218.57.80.23
                # Line 3: rx_bytes
                # Line 4: tx_bytes
                # Line 5: client count
                # Line 6: uptime
                # Line 7: temperature (millidegrees)

                if len(lines) >= 7:
                    # CPU（从 idle 计算）
                    cpu_line = lines[0]
                    try:
                        # 提取 idle 百分比
                        parts = cpu_line.split()
                        for i, p in enumerate(parts):
                            if p == "idle" or p.endswith("idle"):
                                idle_str = parts[i - 1].replace("%", "")
                                idle = float(idle_str)
                                result["cpu_percent"] = round(100 - idle, 1)
                                break
                    except (ValueError, IndexError):
                        pass

                    # 内存
                    mem_line = lines[1]
                    try:
                        parts = mem_line.split()
                        # Mem: total used free shared buffers cached
                        if len(parts) >= 3:
                            total = int(parts[1])
                            used = int(parts[2])
                            if total > 0:
                                result["mem_percent"] = round(
                                    (used / total) * 100, 1
                                )
                    except (ValueError, IndexError):
                        pass

                    # 公网 IP
                    result["wan_ip"] = lines[2].strip()

                    # 流量速率
                    try:
                        rx_bytes = int(lines[3].strip())
                        tx_bytes = int(lines[4].strip())
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

                    # 在线设备数
                    try:
                        result["clients"] = int(lines[5].strip())
                    except ValueError:
                        pass

                    # 运行时间（秒）
                    try:
                        uptime_sec = float(lines[6].split()[0])
                        result["uptime"] = int(uptime_sec)
                    except (ValueError, IndexError):
                        pass

                    # CPU 温度（毫度转摄氏度）
                    if len(lines) >= 8:
                        try:
                            temp_raw = int(lines[7].strip())
                            result["cpu_temp"] = round(temp_raw / 1000, 1)
                        except (ValueError, IndexError):
                            pass

    except asyncio.TimeoutError:
        logger.warning(f"主路由 SSH 连接超时: {settings.router_host}")
    except Exception as e:
        logger.warning(f"主路由 SSH 采集失败: {e}")

    return result
