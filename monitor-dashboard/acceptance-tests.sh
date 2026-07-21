#!/bin/bash
#
# 监控大屏验收测试脚本
# 用途：自动化执行任务 7.1-7.5 的验收测试
#
# 用法：
#   ssh root@192.168.50.10 "bash /opt/docker/monitor-dashboard/acceptance-tests.sh"
#

set -e

# 配置
DASHBOARD_URL="http://localhost:3030"
X5_HOST="192.168.50.10"
GATEWAY_IP="192.168.50.2"
GATEWAY_SSH_USER="root"
GATEWAY_SSH_PASS="Wfw7539148@"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TEST_PASSED=0
TEST_FAILED=0

log_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TEST_PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((TEST_FAILED++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

# ============================================
# 测试 7.1: 所有设备在线时 Dashboard 正常
# ============================================
test_all_devices_online() {
    log_test "7.1: 验证所有设备在线时 Dashboard 正常展示"
    
    # 检查 API 响应
    log_info "检查 /api/status API 响应..."
    STATUS_RESPONSE=$(curl -s "${DASHBOARD_URL}/api/status")
    
    # 检查是否包含所有设备
    if echo "$STATUS_RESPONSE" | grep -q '"router"'; then
        log_pass "主路由数据存在"
    else
        log_fail "主路由数据缺失"
    fi
    
    if echo "$STATUS_RESPONSE" | grep -q '"gateway"'; then
        log_pass "旁路由数据存在"
    else
        log_fail "旁路由数据缺失"
    fi
    
    if echo "$STATUS_RESPONSE" | grep -q '"nas"'; then
        log_pass "NAS 数据存在"
    else
        log_fail "NAS 数据缺失"
    fi
    
    if echo "$STATUS_RESPONSE" | grep -q '"local"'; then
        log_pass "X5-Server 数据存在"
    else
        log_fail "X5-Server 数据缺失"
    fi
    
    # 检查连通性数据
    if echo "$STATUS_RESPONSE" | grep -q '"connectivity"'; then
        log_pass "连通性数据存在"
    else
        log_fail "连通性数据缺失"
    fi
    
    # 检查健康状态
    HEALTH_RESPONSE=$(curl -s "${DASHBOARD_URL}/health")
    if echo "$HEALTH_RESPONSE" | grep -q '"status": "ok"'; then
        log_pass "健康检查通过"
    else
        log_fail "健康检查失败"
    fi
    
    echo
}

# ============================================
# 测试 7.2: 单设备离线测试
# ============================================
test_device_offline() {
    log_test "7.2: 验证单设备离线时对应卡片变红，其他设备不受影响"
    
    log_info "此测试需要手动操作："
    echo "  1. 拔掉 NAS 的网线（或关闭旁路由）"
    echo "  2. 等待 30 秒"
    echo "  3. 观察 Dashboard"
    echo
    echo -n "  是否已完成操作并观察到对应设备变红？(y/N): "
    read -r response
    
    if [[ $response =~ ^[Yy]$ ]]; then
        log_pass "单设备离线测试通过"
        
        # 检查其他设备是否正常
        echo -n "  其他设备是否保持绿色？(y/N): "
        read -r response
        if [[ $response =~ ^[Yy]$ ]]; then
            log_pass "其他设备不受影响测试通过"
        else
            log_fail "其他设备受到影响"
        fi
    else
        log_fail "测试未执行"
    fi
    
    echo
}

# ============================================
# 测试 7.3: 翻墙中断测试
# ============================================
test_vpn_interrupt() {
    log_test "7.3: 验证翻墙中断时连通性面板正确标红"
    
    log_info "停止旁路由 xray 服务..."
    sshpass -p "${GATEWAY_SSH_PASS}" ssh -o StrictHostKeyChecking=no "${GATEWAY_SSH_USER}@${GATEWAY_IP}" "systemctl stop xray"
    
    log_info "等待 30 秒..."
    sleep 30
    
    # 检查连通性状态
    STATUS_RESPONSE=$(curl -s "${DASHBOARD_URL}/api/status")
    
    if echo "$STATUS_RESPONSE" | grep -q '"google"'; then
        GOOGLE_STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"google":{[^}]*}' | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        log_info "Google 探测状态：$GOOGLE_STATUS"
        
        if [[ "$GOOGLE_STATUS" == "offline" || "$GOOGLE_STATUS" == "error" ]]; then
            log_pass "翻墙中断检测正确"
        else
            log_fail "翻墙中断未检测到（状态：$GOOGLE_STATUS）"
        fi
    else
        log_fail "Google 探测数据缺失"
    fi
    
    log_info "恢复 xray 服务..."
    sshpass -p "${GATEWAY_SSH_PASS}" ssh -o StrictHostKeyChecking=no "${GATEWAY_SSH_USER}@${GATEWAY_IP}" "systemctl start xray"
    
    log_info "等待 30 秒恢复..."
    sleep 30
    
    # 验证恢复
    STATUS_RESPONSE=$(curl -s "${DASHBOARD_URL}/api/status")
    if echo "$STATUS_RESPONSE" | grep -q '"google"'; then
        GOOGLE_STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"google":{[^}]*}' | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        if [[ "$GOOGLE_STATUS" == "online" ]]; then
            log_pass "翻墙服务恢复检测正确"
        else
            log_info "翻墙服务状态：$GOOGLE_STATUS（可能需要更长时间恢复）"
        fi
    fi
    
    echo
}

# ============================================
# 测试 7.4: SSE 断线重连测试
# ============================================
test_sse_reconnect() {
    log_test "7.4: 验证 SSE 断线后 5 秒内自动重连"
    
    log_info "此测试需要手动操作："
    echo "  1. 打开浏览器访问 http://${X5_HOST}:3030"
    echo "  2. 按 F12 打开开发者工具 → Network 标签"
    echo "  3. 找到 /api/events 连接，右键 → Close connection"
    echo "  4. 观察 Console 日志和 Network 标签"
    echo
    echo "  预期结果："
    echo "    - 5 秒内自动重连"
    echo "    - Console 显示 'SSE reconnected' 或类似消息"
    echo "    - Dashboard 数据继续更新"
    echo
    echo -n "  SSE 是否在 5 秒内重连？(y/N): "
    read -r response
    
    if [[ $response =~ ^[Yy]$ ]]; then
        log_pass "SSE 断线重连测试通过"
    else
        log_fail "SSE 重连超时或未重连"
    fi
    
    echo
}

# ============================================
# 测试 7.5: 容器重启测试
# ============================================
test_container_restart() {
    log_test "7.5: 验证容器重启后服务自动恢复"
    
    log_info "重启 Docker 容器..."
    cd /opt/docker/monitor-dashboard
    docker compose restart monitor-dashboard
    
    log_info "等待 30 秒..."
    sleep 30
    
    # 验证容器状态
    if docker compose ps | grep -q "monitor-dashboard.*Up"; then
        log_pass "容器��启成功"
    else
        log_fail "容器重启失败"
        docker compose logs monitor-dashboard
        return 1
    fi
    
    # 验证 API 恢复
    if curl -s "${DASHBOARD_URL}/health" | grep -q '"status": "ok"'; then
        log_pass "API 恢复成功"
    else
        log_fail "API 恢复失败"
    fi
    
    # 验证 Dashboard 显示
    echo -n "  Dashboard 是否恢复正常显示？(y/N): "
    read -r response
    
    if [[ $response =~ ^[Yy]$ ]]; then
        log_pass "Dashboard 显示恢复测试通过"
    else
        log_fail "Dashboard 显示未恢复"
    fi
    
    echo
}

# ============================================
# 生成测试报告
# ============================================
generate_report() {
    echo "=========================================="
    echo "验收测试报告"
    echo "=========================================="
    echo
    echo "测试时间：$(date '+%Y-%m-%d %H:%M:%S')"
    echo "测试主机：${X5_HOST}"
    echo
    echo "通过测试：${TEST_PASSED}"
    echo "失败测试：${TEST_FAILED}"
    echo "总计测试：$((TEST_PASSED + TEST_FAILED))"
    echo
    
    if [[ $TEST_FAILED -eq 0 ]]; then
        echo -e "${GREEN}所有测试通过！${NC}"
        echo
        echo "监控大屏已准备就绪，可以投入生产使用。"
        return 0
    else
        echo -e "${RED}部分测试失败，请检查上述错误。${NC}"
        echo
        echo "建议："
        echo "  1. 查看 DEPLOY-X5.md 故障排查章节"
        echo "  2. 检查 Docker 日志：docker compose logs monitor-dashboard"
        echo "  3. 验证网络连接和 SSH 配置"
        return 1
    fi
}

# ============================================
# 主流程
# ============================================
main() {
    echo "=========================================="
    echo "监控大屏验收测试"
    echo "=========================================="
    echo
    
    # 检查依赖
    if ! command -v curl &> /dev/null; then
        echo "错误：curl 未安装"
        exit 1
    fi
    
    if ! command -v sshpass &> /dev/null; then
        log_info "sshpass 未安装，部分测试可能无法执行"
        log_info "安装：apt install -y sshpass"
    fi
    
    # 执行测试
    test_all_devices_online
    test_device_offline
    test_vpn_interrupt
    test_sse_reconnect
    test_container_restart
    
    # 生成报告
    generate_report
}

# 执行
main "$@"
