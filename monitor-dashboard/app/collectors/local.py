"""X5-Server (192.168.50.10) 数据采集器。

采集方式：通过 SSH 远程执行命令获取系统信息。
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

import asyncssh

from app.config import settings

logger = logging.getLogger(__name__)

# SSH 连接缓存
_ssh_connection = None
_last_network_stats = {"rx_bytes": 0, "tx_bytes": 0, "timestamp": 0}


async def _get_ssh_connection():
    """获取或创建 SSH 连接。"""
    global _ssh_connection
    
    try:
        if _ssh_connection is not None and not _ssh_connection.is_closed():
            return _ssh_connection
        
        # 使用配置文件中的 SSH 设置
        ssh_settings = {
            'host': settings.x5server_ip,
            'username': 'root',
            'password': settings.x5server_ssh_password,
            'known_hosts': None,  # 跳过 known_hosts 检查
            'connect_timeout': 10,
        }
        
        logger.debug(f"正在连接 SSH: {ssh_settings['host']}")
        _ssh_connection = await asyncssh.connect(**ssh_settings)
        logger.info(f"SSH 连接成功：{ssh_settings['host']}")
        return _ssh_connection
        
    except Exception as e:
        logger.error(f"SSH 连接失败：{e}")
        _ssh_connection = None
        raise


async def _run_ssh_command(conn, command: str) -> str:
    """执行 SSH 命令并返回输出。"""
    try:
        result = await conn.run(command)
        return result.stdout.strip()
    except Exception as e:
        logger.debug(f"SSH 命令执行失败 [{command}]: {e}")
        return ""


async def _get_system_info(conn) -> dict:
    """获取系统信息。"""
    result = {
        "cpu_percent": None,
        "mem_percent": None,
        "disk_percent": None,
        "cpu_temp": None,
        "uptime_seconds": None,
        "network": None,
    }
    
    try:
        # 执行多个命令获取系统信息
        commands = await asyncio.gather(
            _run_ssh_command(conn, "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"),
            _run_ssh_command(conn, "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100}'"),
            _run_ssh_command(conn, "df / | tail -1 | awk '{printf \"%.1f\", $5}' | tr -d '%'"),
            _run_ssh_command(conn, "cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo ''"),
            _run_ssh_command(conn, "cat /proc/uptime | awk '{print int($1)}'"),
            _run_ssh_command(conn, "cat /sys/class/net/eno0/statistics/rx_bytes 2>/dev/null || cat /sys/class/net/eth0/statistics/rx_bytes 2>/dev/null || cat /sys/class/net/enp2s0/statistics/rx_bytes 2>/dev/null"),
            _run_ssh_command(conn, "cat /sys/class/net/eno0/statistics/tx_bytes 2>/dev/null || cat /sys/class/net/eth0/statistics/tx_bytes 2>/dev/null || cat /sys/class/net/enp2s0/statistics/tx_bytes 2>/dev/null"),
        )
        
        # CPU 使用率
        if commands[0]:
            try:
                result["cpu_percent"] = round(float(commands[0]), 1)
            except:
                pass
        
        # 内存使用率
        if commands[1]:
            try:
                result["mem_percent"] = round(float(commands[1]), 1)
            except:
                pass
        
        # 磁盘使用率
        if commands[2]:
            try:
                result["disk_percent"] = round(float(commands[2]), 1)
            except:
                pass
        
        # CPU 温度
        if commands[3]:
            try:
                temp = int(commands[3])
                if temp > 1000:  # 毫度
                    result["cpu_temp"] = round(temp / 1000, 1)
                elif temp > 0:  # 度
                    result["cpu_temp"] = round(temp, 1)
            except:
                pass
        
        # 运行时间
        if commands[4]:
            try:
                result["uptime_seconds"] = int(commands[4])
            except:
                pass
        
        # 网络统计
        if commands[5] and commands[6]:
            try:
                result["network"] = {
                    "rx_bytes": int(commands[5]),
                    "tx_bytes": int(commands[6]),
                }
            except:
                pass
        
    except Exception as e:
        logger.error(f"获取系统信息失败：{e}")
    
    return result


async def _get_docker_info(conn) -> dict:
    """获取 Docker 容器信息。"""
    try:
        # 获取所有容器
        output = await _run_ssh_command(conn, "docker ps -a --format '{{.Names}},{{.Status}}'")
        
        containers = []
        running = 0
        
        for line in output.split('\n'):
            if line.strip():
                parts = line.split(',')
                name = parts[0]
                status_str = ','.join(parts[1:]) if len(parts) > 1 else ""
                
                # 判断状态
                status = "running" if "Up" in status_str else "exited"
                if status == "running":
                    running += 1
                
                containers.append({
                    "name": name,
                    "status": status,
                })
        
        return {
            "running": running,
            "total": len(containers),
            "containers": containers,
        }
        
    except Exception as e:
        logger.debug(f"Docker 信息采集失败：{e}")
        return {"running": 0, "total": 0, "containers": [], "error": str(e)}


async def collect_local() -> dict:
    """采集 X5-Server 状态。"""
    global _last_network_stats
    
    result = {
        "name": "X5-Server",
        "ip": "192.168.50.10",
        "status": "offline",
        "cpu_percent": None,
        "mem_percent": None,
        "disk_percent": None,
        "cpu_temp": None,
        "uptime_seconds": None,
        "rx_rate": None,
        "tx_rate": None,
        "network_iface": None,
        "docker": None,
    }
    
    try:
        # 获取 SSH 连接
        conn = await _get_ssh_connection()
        result["status"] = "online"
        
        # 获取系统信息和 Docker 信息
        sys_info, docker_info = await asyncio.gather(
            _get_system_info(conn),
            _get_docker_info(conn),
        )
        
        result["cpu_percent"] = sys_info["cpu_percent"]
        result["mem_percent"] = sys_info["mem_percent"]
        result["disk_percent"] = sys_info["disk_percent"]
        result["cpu_temp"] = sys_info["cpu_temp"]
        result["uptime_seconds"] = sys_info["uptime_seconds"]
        
        # 计算网络速率
        if sys_info["network"]:
            current_rx = sys_info["network"]["rx_bytes"]
            current_tx = sys_info["network"]["tx_bytes"]
            current_time = datetime.now().timestamp()
            
            if _last_network_stats["timestamp"] > 0:
                time_delta = current_time - _last_network_stats["timestamp"]
                if time_delta > 0:
                    rx_delta = current_rx - _last_network_stats["rx_bytes"]
                    tx_delta = current_tx - _last_network_stats["tx_bytes"]
                    result["rx_rate"] = int(rx_delta / time_delta)
                    result["tx_rate"] = int(tx_delta / time_delta)
            
            # 更新上次数据
            _last_network_stats = {
                "rx_bytes": current_rx,
                "tx_bytes": current_tx,
                "timestamp": current_time,
            }
        
        result["docker"] = docker_info
        
    except Exception as e:
        logger.error(f"X5-Server 采集失败：{e}")
        result["status"] = "offline"
    
    return result
