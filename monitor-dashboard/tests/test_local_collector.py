#!/usr/bin/env python3
"""
本地测试脚本 - 测试 X5-Server 采集器功能

用法：
    cd monitor-dashboard
    source .venv/bin/activate
    python tests/test_local_collector.py
"""
import asyncio
import sys
from pathlib import Path

# 添加 app 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from collectors.local import collect_local


async def test_local_collector():
    """测试本地采集器。"""
    print("=" * 60)
    print("X5-Server 本地采集器测试")
    print("=" * 60)
    print()
    
    # 第一次采集（用于初始化网络统计）
    print("第一次采集（初始化网络统计）...")
    result1 = await collect_local()
    print(f"  状态：{result1['status']}")
    print(f"  CPU: {result1['cpu_percent']}%")
    print(f"  内存：{result1['mem_percent']}%")
    print(f"  磁盘：{result1['disk_percent']}%")
    print(f"  CPU 温度：{result1['cpu_temp']}°C" if result1['cpu_temp'] else "  CPU 温度：--")
    print(f"  网络接口：{result1['network_iface']}" if result1['network_iface'] else "  网络接口：--")
    print(f"  Docker: {result1['docker']['running']}/{result1['docker']['total']}" if result1['docker'] else "  Docker: --")
    print()
    
    # 等待 2 秒
    print("等待 2 秒...")
    await asyncio.sleep(2)
    
    # 第二次采集（计算网络速率）
    print("第二次采集（计算网络速率）...")
    result2 = await collect_local()
    print()
    print("=" * 60)
    print("采集结果详情")
    print("=" * 60)
    print()
    
    print(f"设备名称：{result2['name']}")
    print(f"IP 地址：{result2['ip']}")
    print(f"状态：{result2['status']}")
    print()
    
    print("系统资源:")
    print(f"  CPU 使用率：{result2['cpu_percent']}%" if result2['cpu_percent'] else "  CPU 使用率：--")
    print(f"  内存使用率：{result2['mem_percent']}%" if result2['mem_percent'] else "  内存使用率：--")
    print(f"  磁盘使用率：{result2['disk_percent']}%" if result2['disk_percent'] else "  磁盘使用率：--")
    print(f"  CPU 温度：{result2['cpu_temp']}°C" if result2['cpu_temp'] else "  CPU 温度：--")
    print()
    
    print("网络流量:")
    print(f"  网络接口：{result2['network_iface']}" if result2['network_iface'] else "  网络接口：--")
    if result2['rx_rate'] is not None:
        rx_mbps = result2['rx_rate'] * 8 / 1000000
        print(f"  下行速率：{result2['rx_rate']} B/s ({rx_mbps:.2f} Mbps)")
    else:
        print(f"  下行速率：--")
    if result2['tx_rate'] is not None:
        tx_mbps = result2['tx_rate'] * 8 / 1000000
        print(f"  上行速率：{result2['tx_rate']} B/s ({tx_mbps:.2f} Mbps)")
    else:
        print(f"  上行速率：--")
    print()
    
    print("Docker 容器:")
    if result2['docker']:
        print(f"  运行中：{result2['docker']['running']}")
        print(f"  总计：{result2['docker']['total']}")
        if result2['docker'].get('containers'):
            print("  容器列表:")
            for c in result2['docker']['containers'][:5]:  # 只显示前 5 个
                status_badge = "✓" if c['status'] == 'running' else "✗"
                print(f"    {status_badge} {c['name']} ({c['status']})")
            if len(result2['docker']['containers']) > 5:
                print(f"    ... 还有 {len(result2['docker']['containers']) - 5} 个容器")
    else:
        print("  Docker: --")
    print()
    
    print("运行时间:")
    if result2['uptime_seconds']:
        days = result2['uptime_seconds'] // 86400
        hours = (result2['uptime_seconds'] % 86400) // 3600
        minutes = (result2['uptime_seconds'] % 3600) // 60
        print(f"  {days}天 {hours}小时 {minutes}分钟")
    else:
        print(f"  --")
    print()
    
    print("=" * 60)
    print("测试完成！")
    print("=" * 60)
    
    return result2


if __name__ == "__main__":
    try:
        result = asyncio.run(test_local_collector())
    except KeyboardInterrupt:
        print("\n测试被用户中断")
        sys.exit(0)
    except Exception as e:
        print(f"\n测试失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
