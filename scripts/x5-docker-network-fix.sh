#!/bin/bash
# ============================================================
# X5 Server Docker 网络修复脚本
# 
# 问题：Docker bridge 容器无法正常访问外网
# 根因：X5 Server 默认网关是旁路由 (192.168.50.2)，旁路由 TPROXY 
#       透明代理在处理 Docker NAT 后的流量时存在回包路径异常
#
# 解决方案：为 Docker 容器流量配置策略路由，直接走主路由 (192.168.50.1)
#           出去，绕过旁路由的 TPROXY，让容器拥有和"直连主路由"一样的网络
#
# 部署：在 X5 Server (192.168.50.10) 上执行
# ============================================================

set -e

MAIN_ROUTER="192.168.50.1"
DOCKER_SUBNET="172.17.0.0/16"    # Docker 默认 bridge 网段
TABLE_ID=200
TABLE_NAME="docker-direct"

echo "=== X5 Server Docker 网络修复 ==="
echo ""
echo "策略：Docker 容器出站流量走主路由 $MAIN_ROUTER 直出"
echo "      宿主机自身流量仍走旁路由（保留翻墙能力）"
echo ""

# --- 1. 添加策略路由表名 ---
if ! grep -q "$TABLE_NAME" /etc/iproute2/rt_tables 2>/dev/null; then
    echo "$TABLE_ID $TABLE_NAME" >> /etc/iproute2/rt_tables
    echo "[✓] 添加路由表: $TABLE_ID $TABLE_NAME"
else
    echo "[•] 路由表已存在: $TABLE_ID $TABLE_NAME"
fi

# --- 2. 配置路由表 ---
# 清除旧规则（如果有）
ip route flush table $TABLE_NAME 2>/dev/null || true

# Docker 容器流量走主路由出去
ip route add default via $MAIN_ROUTER table $TABLE_NAME
echo "[✓] 路由表配置: default via $MAIN_ROUTER (table $TABLE_NAME)"

# --- 3. 添加策略路由规则 ---
# 来自 Docker bridge 网段的流量使用 docker-direct 表
# 先删除旧规则避免重复
ip rule del from $DOCKER_SUBNET table $TABLE_NAME 2>/dev/null || true
ip rule add from $DOCKER_SUBNET table $TABLE_NAME priority 100
echo "[✓] 策略规则: from $DOCKER_SUBNET → table $TABLE_NAME (priority 100)"

# --- 4. 确保 IP 转发开启 ---
current_forward=$(sysctl -n net.ipv4.ip_forward)
if [ "$current_forward" != "1" ]; then
    sysctl -w net.ipv4.ip_forward=1
    echo "[✓] 开启 IP 转发"
else
    echo "[•] IP 转发已开启"
fi

# --- 5. 确保 Docker NAT 规则正常 ---
# Docker 默认会添加 MASQUERADE 规则，确认它存在
if iptables -t nat -L POSTROUTING -n 2>/dev/null | grep -q "172.17.0.0/16"; then
    echo "[•] Docker MASQUERADE 规则已存在"
else
    echo "[!] 注意：Docker MASQUERADE 规则不存在，可能 Docker 尚未启动"
    echo "    Docker 启动后会自动添加"
fi

echo ""
echo "=== 完成 ==="
echo ""
echo "验证步骤："
echo "  1. docker exec <容器名> ping -c 3 baidu.com"
echo "  2. docker exec <容器名> curl -s https://httpbin.org/ip"
echo "  3. ip rule show  (确认 priority 100 规则存在)"
echo "  4. ip route show table $TABLE_NAME"
