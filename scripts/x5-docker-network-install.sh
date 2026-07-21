#!/bin/bash
# ============================================================
# X5 Server Docker 网络修复 - 安装脚本
# 
# 在 X5 Server (192.168.50.10) 上执行此脚本完成一键部署
# 效果：所有 Docker 容器的出站流量直接走主路由 192.168.50.1
#       不经过旁路由 TPROXY 透明代理，避免连接异常
#
# 用法: ssh root@192.168.50.10
#       将此脚本和 x5-docker-network.service 拷贝到服务器后执行
#       bash x5-docker-network-install.sh
# ============================================================

set -e

MAIN_ROUTER="192.168.50.1"
TABLE_ID=200
TABLE_NAME="docker-direct"
SERVICE_NAME="x5-docker-network"

echo "=== X5 Server Docker 网络修复 - 安装 ==="
echo ""

# --- 1. 注册路由表 ---
if ! grep -q "$TABLE_NAME" /etc/iproute2/rt_tables 2>/dev/null; then
    echo "$TABLE_ID $TABLE_NAME" >> /etc/iproute2/rt_tables
    echo "[✓] 注册路由表: $TABLE_ID $TABLE_NAME"
else
    echo "[•] 路由表已注册"
fi

# --- 2. 获取所有 Docker 网段 ---
echo ""
echo "检测 Docker 网段..."
DOCKER_SUBNETS=$(docker network ls -q | xargs -I {} docker network inspect {} --format '{{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null | sort -u | grep -v '^$')

if [ -z "$DOCKER_SUBNETS" ]; then
    # Docker 还没有创建网络，使用默认网段
    DOCKER_SUBNETS="172.17.0.0/16"
fi

echo "  检测到 Docker 网段:"
for subnet in $DOCKER_SUBNETS; do
    echo "    - $subnet"
done

# --- 3. 安装 systemd service ---
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=Docker container network policy routing (bypass tproxy)
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes

# 添加路由表（幂等）
ExecStartPre=/bin/bash -c 'grep -q "$TABLE_ID $TABLE_NAME" /etc/iproute2/rt_tables || echo "$TABLE_ID $TABLE_NAME" >> /etc/iproute2/rt_tables'

# 配置路由和规则 - 覆盖所有 Docker 网段
ExecStart=/bin/bash -c '\\
  ip route replace default via $MAIN_ROUTER table $TABLE_NAME; \\
  for subnet in 172.16.0.0/12; do \\
    ip rule del from \$subnet table $TABLE_NAME 2>/dev/null; \\
    ip rule add from \$subnet table $TABLE_NAME priority 100; \\
  done'

# 停止时清理
ExecStop=/bin/bash -c '\\
  for subnet in 172.16.0.0/12; do \\
    ip rule del from \$subnet table $TABLE_NAME 2>/dev/null; \\
  done; \\
  ip route flush table $TABLE_NAME 2>/dev/null'

[Install]
WantedBy=multi-user.target
EOF

echo ""
echo "[✓] 安装 systemd 服务: /etc/systemd/system/${SERVICE_NAME}.service"

# --- 4. 启用并启动服务 ---
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl start ${SERVICE_NAME}

echo "[✓] 服务已启动并设置开机自启"
echo ""

# --- 5. 验证 ---
echo "=== 验证 ==="
echo ""
echo "路由表:"
ip route show table $TABLE_NAME
echo ""
echo "策略规则:"
ip rule show | grep $TABLE_NAME
echo ""

# 测试 Docker 容器联网
echo "测试容器网络连通性..."
TEST_CONTAINER=$(docker ps -q | head -1)
if [ -n "$TEST_CONTAINER" ]; then
    CONTAINER_NAME=$(docker inspect --format '{{.Name}}' $TEST_CONTAINER | tr -d '/')
    echo "  使用容器: $CONTAINER_NAME"
    
    # 尝试 ping
    if docker exec $TEST_CONTAINER ping -c 2 -W 3 baidu.com >/dev/null 2>&1; then
        echo "  [✓] 容器可以 ping 通 baidu.com"
    elif docker exec $TEST_CONTAINER wget -q --spider --timeout=5 http://baidu.com 2>/dev/null; then
        echo "  [✓] 容器可以访问 http://baidu.com (wget)"
    else
        echo "  [!] 容器网络测试未通过，请手动检查:"
        echo "      docker exec $CONTAINER_NAME ping baidu.com"
    fi
else
    echo "  [!] 没有运行中的容器，跳过测试"
fi

echo ""
echo "=== 安装完成 ==="
echo ""
echo "管理命令:"
echo "  systemctl status $SERVICE_NAME    # 查看状态"
echo "  systemctl restart $SERVICE_NAME   # 重启"
echo "  systemctl stop $SERVICE_NAME      # 停止（恢复原样）"
echo "  journalctl -u $SERVICE_NAME       # 查看日志"
