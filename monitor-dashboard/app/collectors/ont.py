"""光猫 VSOL V2802RH (192.168.1.1) 数据采集器。

采集方式：通过主路由 SSH 跳转 → Telnet 到光猫。
光猫 Telnet 从 Mac/X5 直连不稳定，但从主路由（WAN 口直连光猫）连接稳定。

采集指标：
- CPU 占用率
- 光功率（RX/TX dBm）
- 端口状态（LAN/WAN UP/DOWN）
- 以太网流量统计（RX/TX bytes）
- ARP 设备数
- 系统运行时间
"""
import asyncio
import logging
import re
import time
from typing import Optional

import asyncssh

from app.config import settings

logger = logging.getLogger(__name__)

# 上次流量字节数，用于计算速率
_last_rx_bytes: Optional[int] = None
_last_tx_bytes: Optional[int] = None
_last_time: Optional[float] = None


def _parse_optical_power(hex_str: str) -> float:
    """将光功率 16位 hex 值转换为 dBm。
    
    GPON ANI-G 的 OpticalSignalLevel 和 TranOpticLevel
    是 16位无符号整数，单位 0.002 dBm（有符号解释）。
    """
    val = int(hex_str, 16)
    # 有符号转换
    if val >= 0x8000:
        val = val - 0x10000
    return round(val * 0.002, 2)


def _parse_telnet_output(output: str) -> dict:
    """解析光猫 Telnet 命令的组合输出。"""
    result = {
        "cpu_percent": None,
        "rx_power_dbm": None,
        "tx_power_dbm": None,
        "lan_status": None,
        "wan_status": None,
        "rx_bytes": None,
        "tx_bytes": None,
        "arp_count": None,
        "uptime": None,
    }

    # CPU 占用: "cpu occupancy 1%"
    m = re.search(r'cpu occupancy\s+(\d+)%', output)
    if m:
        result["cpu_percent"] = int(m.group(1))

    # 光功率: OpticalSignalLevel: 0xd56a
    m = re.search(r'OpticalSignalLevel:\s+(0x[0-9a-fA-F]+)', output)
    if m:
        result["rx_power_dbm"] = _parse_optical_power(m.group(1))

    # 发射功率: TranOpticLevel: 0x0407
    m = re.search(r'TranOpticLevel:\s+(0x[0-9a-fA-F]+)', output)
    if m:
        result["tx_power_dbm"] = _parse_optical_power(m.group(1))

    # 端口状态: "Test Switch LAN PORT 1 UP" / "Test WAN PORT UP"
    if 'LAN PORT 1 UP' in output:
        result["lan_status"] = "up"
    elif 'LAN PORT 1' in output:
        result["lan_status"] = "down"

    if 'WAN PORT UP' in output:
        result["wan_status"] = "up"
    elif 'WAN PORT' in output:
        result["wan_status"] = "down"

    # 以太网流量: RxBytes : 31810898  TxBytes : 286482345
    m = re.search(r'RxBytes\s*:\s+(\d+)', output)
    if m:
        result["rx_bytes"] = int(m.group(1))
    m = re.search(r'TxBytes\s*:\s+(\d+)', output)
    if m:
        result["tx_bytes"] = int(m.group(1))

    # ARP 设备数（数非标题行）
    arp_lines = [l for l in output.split('\n') if re.match(r'^0x[0-9a-f]+', l.strip())]
    if arp_lines:
        result["arp_count"] = len(arp_lines)

    # 运行时间: SysUpTime: 2800（单位是 10 秒，即 hectoseconds）
    m = re.search(r'SysUpTime:\s+(\d+)', output)
    if m:
        # ONT2G 的 SysUpTime 单位是 10 秒 (hectoseconds)
        result["uptime"] = int(m.group(1)) * 10

    return result


async def collect_ont() -> dict:
    """通过主路由 SSH 跳转 Telnet 采集光猫状态。"""
    global _last_rx_bytes, _last_tx_bytes, _last_time

    result = {
        "name": "光猫 VSOL",
        "ip": settings.ont_host,
        "status": "offline",
        "cpu_percent": None,
        "rx_power_dbm": None,
        "tx_power_dbm": None,
        "lan_status": None,
        "wan_status": None,
        "rx_rate": None,
        "tx_rate": None,
        "arp_count": None,
        "uptime": None,
    }

    try:
        # SSH 到主路由
        async with asyncssh.connect(
            settings.router_host,
            port=settings.router_ssh_port,
            username=settings.router_ssh_user,
            password=settings.router_ssh_password,
            known_hosts=None,
            connect_timeout=settings.ssh_timeout,
        ) as conn:
            # 通过主路由 telnet 到光猫，用 expect 脚本自动化交互
            # 华硕路由器上没有 expect，用 shell 脚本 + 管道模拟
            script = (
                '('
                'sleep 2; echo "admin"; '
                'sleep 2; echo "Wfw7539148@"; '
                'sleep 2; echo "cpuocpy"; '
                'sleep 2; echo "omcicli mib get Anig"; '
                'sleep 2; echo "omcicli mib get Ont2g"; '
                'sleep 2; echo "ethstatus"; '
                'sleep 2; echo "show arp"; '
                'sleep 2; echo "show ethernet"; '
                'sleep 2; echo "logout"; '
                ') | telnet 192.168.1.1'
            )

            r = await asyncio.wait_for(
                conn.run(script, timeout=30),
                timeout=35,
            )

            output = r.stdout or ""
            if not output:
                output = r.stderr or ""

            if "AP#" in output:
                result["status"] = "online"
                parsed = _parse_telnet_output(output)

                result["cpu_percent"] = parsed["cpu_percent"]
                result["rx_power_dbm"] = parsed["rx_power_dbm"]
                result["tx_power_dbm"] = parsed["tx_power_dbm"]
                result["lan_status"] = parsed["lan_status"]
                result["wan_status"] = parsed["wan_status"]
                result["arp_count"] = parsed["arp_count"]
                result["uptime"] = parsed["uptime"]

                # 计算流量速率
                if parsed["rx_bytes"] is not None and parsed["tx_bytes"] is not None:
                    now = time.time()
                    if _last_rx_bytes is not None and _last_time is not None:
                        elapsed = now - _last_time
                        if elapsed > 0:
                            result["rx_rate"] = round(
                                (parsed["rx_bytes"] - _last_rx_bytes) / elapsed, 1
                            )
                            result["tx_rate"] = round(
                                (parsed["tx_bytes"] - _last_tx_bytes) / elapsed, 1
                            )
                    _last_rx_bytes = parsed["rx_bytes"]
                    _last_tx_bytes = parsed["tx_bytes"]
                    _last_time = now
            else:
                # Telnet 连接失败但主路由在线，标记为 ping-only
                logger.debug(f"光猫 Telnet 无 AP# 响应")
                # 尝试 ping
                ping_r = await conn.run(
                    f"ping -c 1 -W 2 {settings.ont_host}",
                    timeout=5,
                )
                if ping_r.exit_status == 0:
                    result["status"] = "online"

    except asyncio.TimeoutError:
        logger.warning("光猫采集超时")
    except Exception as e:
        logger.warning(f"光猫采集失败: {e}")

    return result
