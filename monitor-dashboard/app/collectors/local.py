"""X5-Server (192.168.50.10) 本地数据采集器。

采集方式：直接读取 /proc、执行 df、通过 Docker API 获取容器状态。
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

import docker
import psutil

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2)


def _get_docker_info() -> dict:
    """通过 Docker socket 获取容器状态。"""
    try:
        client = docker.from_env(timeout=5)
        containers = client.containers.list(all=True)
        running = [c for c in containers if c.status == "running"]

        container_list = []
        for c in containers:
            container_list.append({
                "name": c.name,
                "status": c.status,
            })

        return {
            "running": len(running),
            "total": len(containers),
            "containers": container_list,
        }
    except Exception as e:
        logger.debug(f"Docker 采集失败: {e}")
        return {"running": 0, "total": 0, "containers": [], "error": str(e)}


def _get_system_info() -> dict:
    """同步采集系统信息（在线程池中运行）。"""
    result = {
        "cpu_percent": None,
        "mem_percent": None,
        "disk_percent": None,
    }

    try:
        result["cpu_percent"] = psutil.cpu_percent(interval=1)
    except Exception as e:
        logger.debug(f"CPU 采集失败: {e}")

    try:
        mem = psutil.virtual_memory()
        result["mem_percent"] = round(mem.percent, 1)
    except Exception as e:
        logger.debug(f"内存采集失败: {e}")

    try:
        disk = psutil.disk_usage("/")
        result["disk_percent"] = round(disk.percent, 1)
    except Exception as e:
        logger.debug(f"磁盘采集失败: {e}")

    return result


async def collect_local() -> dict:
    """采集 X5-Server 本地状态。"""
    result = {
        "name": "X5-Server",
        "ip": "192.168.50.10",
        "status": "online",  # 本机始终在线
        "cpu_percent": None,
        "mem_percent": None,
        "disk_percent": None,
        "docker": None,
    }

    loop = asyncio.get_event_loop()

    # 在线程池中执行同步阻塞操作
    sys_info, docker_info = await asyncio.gather(
        loop.run_in_executor(_executor, _get_system_info),
        loop.run_in_executor(_executor, _get_docker_info),
    )

    result["cpu_percent"] = sys_info["cpu_percent"]
    result["mem_percent"] = sys_info["mem_percent"]
    result["disk_percent"] = sys_info["disk_percent"]
    result["docker"] = docker_info

    return result
