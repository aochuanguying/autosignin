"""VSOL V2802RH 光猫数据采集器 - 最终版本。

使用 VSOL 专用命令获取信息。
"""
import asyncio
import logging
import re
import time

import telnetlib

from app.config import settings

logger = logging.getLogger(__name__)

_telnet_connection = None
_last_network_stats = {"rx_bytes": 0, "tx_bytes": 0, "timestamp": 0}


def _get_telnet_connection():
    """获取或创建 Telnet 连接。"""
    global _telnet_connection
    
    try:
        if _telnet_connection is not None:
            try:
                _telnet_connection.sock.getpeername()
                return _telnet_connection
            except:
                _telnet_connection = None
        
        host = settings.ont_host
        password = settings.ont_password
        
        tn = telnetlib.Telnet(host, timeout=10)
        
        tn.read_until(b"Username:", timeout=5)
        tn.write(b"admin\n")
        time.sleep(0.5)
        
        tn.read_until(b"Password:", timeout=5)
        tn.write(f"{password}\n".encode())
        time.sleep(1)
        
        # 登录成功后可能看到 AP# 或 # 提示符
        output = tn.read_until(b"#", timeout=3).decode('utf-8', errors='ignore')
        logger.info(f"VSOL 光猫登录成功，提示符输出：{output[:200]}")
        
        _telnet_connection = tn
        return _telnet_connection
        
    except Exception as e:
        logger.error(f"VSOL 光猫连接失败：{e}")
        _telnet_connection = None
        raise


def _run_command(tn, command: str) -> str:
    """执行命令并返回输出。"""
    try:
        tn.write(f"{command}\n".encode())
        time.sleep(1.0)  # VSOL 响应较慢
        
        try:
            output = tn.read_until(b"#", timeout=3).decode('utf-8', errors='ignore')
            return output.strip()
        except:
            return ""
    except:
        return ""


async def collect_ont() -> dict:
    """采集 VSOL V2802RH 光猫状态。"""
    global _last_network_stats
    
    result = {
        "name": "光猫 VSOL",
        "ip": "192.168.1.1",
        "model": "V2802RH",
        "status": "offline",
        "rx_power": None,
        "tx_power": None,
        "voltage": None,
        "temperature": None,
        "bias_current": None,
        "wan_ip": None,
        "wan_status": "unknown",
        "uptime_seconds": None,
        "uptime": None,
        "rx_rate": None,
        "tx_rate": None,
        "device_count": 0,
    }
    
    try:
        tn = _get_telnet_connection()
        result["status"] = "online"
        
        loop = asyncio.get_event_loop()
        
        # 获取系统信息 - 尝试多种命令格式
        def get_info():
            info = {}
            
            # VSOL V2802RH 使用专用命令集，尝试几种可能的格式
            
            # 1. 尝试进入 shell
            shell_output = _run_command(tn, "shell")
            logger.info(f"Shell 输出：{shell_output[:200] if shell_output else '空'}")
            
            # 2. 尝试 help 命令查看支持的命令
            help_output = _run_command(tn, "help")
            logger.info(f"Help 输出：{help_output[:300] if help_output else '空'}")
            
            # 3. 尝试 ? 命令
            question_output = _run_command(tn, "?")
            logger.info(f"? 输出：{question_output[:300] if question_output else '空'}")
            
            # 4. 尝试 list 命令
            list_output = _run_command(tn, "list")
            logger.info(f"List 输出：{list_output[:300] if list_output else '空'}")
            
            # 5. 尝试 show 命令
            show_output = _run_command(tn, "show")
            logger.info(f"Show 输出：{show_output[:300] if show_output else '空'}")
            
            # 6. 尝试 get 命令
            get_output = _run_command(tn, "get")
            logger.info(f"Get 输出：{get_output[:300] if get_output else '空'}")
            
            # 7. 尝试 cat 命令
            cat_output = _run_command(tn, "cat")
            logger.info(f"Cat 输出：{cat_output[:200] if cat_output else '空'}")
            
            # 8. 尝试 ls 命令
            ls_output = _run_command(tn, "ls")
            logger.info(f"LS 输出：{ls_output[:300] if ls_output else '空'}")
            
            return info
        
        info = await loop.run_in_executor(None, get_info)
        result.update(info)
        
        # 流量统计（如果有）
        if result["wan_status"] == "connected":
            def get_traffic():
                rx = _run_command(tn, "cat /sys/class/net/eth0/statistics/rx_bytes")
                tx = _run_command(tn, "cat /sys/class/net/eth0/statistics/tx_bytes")
                if rx and rx.isdigit() and tx and tx.isdigit():
                    return int(rx), int(tx)
                return None, None
            
            rx_bytes, tx_bytes = await loop.run_in_executor(None, get_traffic)
            if rx_bytes and tx_bytes:
                current_time = loop.time()
                
                if _last_network_stats["timestamp"] > 0:
                    time_delta = current_time - _last_network_stats["timestamp"]
                    if time_delta > 0:
                        result["rx_rate"] = int((rx_bytes - _last_network_stats["rx_bytes"]) / time_delta)
                        result["tx_rate"] = int((tx_bytes - _last_network_stats["tx_bytes"]) / time_delta)
                
                _last_network_stats = {
                    "rx_bytes": rx_bytes,
                    "tx_bytes": tx_bytes,
                    "timestamp": current_time,
                }
        
    except Exception as e:
        logger.error(f"VSOL 光猫采集失败：{e}")
        result["status"] = "offline"
    
    return result
