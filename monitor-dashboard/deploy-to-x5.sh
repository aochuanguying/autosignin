#!/bin/bash
#
# X5-Server 一键部署脚本
# 用途：自动化部署监控大屏到 X5-Server 并配置 Kiosk 模式
#
# 用法：
#   1. 在 Mac 上执行：./deploy-to-x5.sh
#   2. 或先上传到 X5-Server 再执行：bash deploy-to-x5.sh
#

set -e

# 配置
X5_HOST="192.168.50.10"
X5_USER="root"
DEPLOY_DIR="/opt/docker/monitor-dashboard"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否在 Mac 上运行
check_local() {
    if [[ "$(uname)" == "Darwin" ]]; then
        log_info "检测到 macOS 环境"
        return 0
    else
        log_info "检测到 Linux 环境（可能在 X5-Server 上）"
        return 1
    fi
}

# SSH 执行命令
ssh_exec() {
    ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 "${X5_USER}@${X5_HOST}" "$1"
}

# SCP 上传文件
scp_upload() {
    scp -r "$1" "${X5_USER}@${X5_HOST}:$2"
}

# ============================================
# 阶段 1: 上传代码
# ============================================
upload_code() {
    log_info "阶段 1: 上传代码到 X5-Server..."
    
    if check_local; then
        log_info "从 Mac 上传 monitor-dashboard 目录..."
        cd "$SCRIPT_DIR/.."
        scp_upload "monitor-dashboard" "${DEPLOY_DIR}/.."
        log_info "代码上传完成"
    else
        log_warn "当前在 X5-Server 上，跳过上传步骤"
    fi
}

# ============================================
# 阶段 2: 配置环境变量
# ============================================
configure_env() {
    log_info "阶段 2: 配置环境变量..."
    
    ssh_exec "cd ${DEPLOY_DIR} && cp .env.example .env"
    
    # 创建 .env ��件
    cat > /tmp/monitor_env << 'EOF'
# 采集间隔（秒）
POLL_INTERVAL=15

# 主路由 BE86U
ROUTER_IP=192.168.50.1
ROUTER_SSH_PORT=22
ROUTER_SSH_USER=wangfuwei
ROUTER_SSH_PASSWORD=Wfw7539148@

# 旁路由 G31
GATEWAY_IP=192.168.50.2
GATEWAY_SSH_PORT=22
GATEWAY_SSH_USER=root
GATEWAY_SSH_PASSWORD=Wfw7539148@

# NAS DS218+
NAS_IP=192.168.50.50
NAS_API_PORT=8088
NAS_API_PROTO=https
NAS_API_USER=wangfuwei
NAS_API_PASSWORD=Wfw7539148@

# 连通性探测
PROBE_GOOGLE_URL=https://www.google.com
PROBE_BAIDU_URL=https://www.baidu.com
PROBE_OFFICE_URL=http://10.19.0.1
OFFICE_NETWORK_URL=http://10.19.0.1
EOF
    
    scp_upload "/tmp/monitor_env" "${X5_USER}@${X5_HOST}:${DEPLOY_DIR}/.env"
    ssh_exec "chmod 600 ${DEPLOY_DIR}/.env"
    
    log_info "环境变量配置完成"
}

# ============================================
# 阶段 3: 配置 SSH 免密登录
# ============================================
configure_ssh_keys() {
    log_info "阶段 3: 配置 SSH 免密登录..."
    
    # 测试旁路由
    log_info "测试旁路由 SSH 连接..."
    if ssh_exec "ssh -o ConnectTimeout=5 root@192.168.50.2 'uptime'"; then
        log_info "旁路由 SSH 免密已配置"
    else
        log_warn "旁路由 SSH 需要密码，正在配置免密..."
        ssh_exec "ssh-copy-id -o StrictHostKeyChecking=no root@192.168.50.2"
    fi
    
    # 测试主路由
    log_info "测试主路由 SSH 连接..."
    if ssh_exec "ssh -o ConnectTimeout=5 wangfuwei@192.168.50.1 'uptime'"; then
        log_info "主路由 SSH 免密已配置"
    else
        log_warn "主路由 SSH 需要密码，正在配置免密..."
        ssh_exec "ssh-copy-id -o StrictHostKeyChecking=no wangfuwei@192.168.50.1"
    fi
    
    log_info "SSH 密钥配置完成"
}

# ============================================
# 阶段 4: 构建并启动 Docker 容器
# ============================================
deploy_docker() {
    log_info "阶段 4: 构建并启动 Docker 容器..."
    
    ssh_exec "cd ${DEPLOY_DIR} && docker compose up -d --build"
    
    log_info "等待容器启动..."
    sleep 10
    
    # 验证容器状态
    if ssh_exec "docker compose ps | grep -q 'monitor-dashboard.*Up'"; then
        log_info "Docker 容器启动成功"
    else
        log_error "Docker 容器启动失败，请检查日志"
        ssh_exec "docker compose logs monitor-dashboard"
        exit 1
    fi
    
    # 验证 API
    if ssh_exec "curl -s http://localhost:3030/health | grep -q 'ok'"; then
        log_info "API 健康检查通过"
    else
        log_error "API 健康检查失败"
        ssh_exec "curl -v http://localhost:3030/health"
        exit 1
    fi
    
    log_info "Docker 部署完成"
    log_info "Dashboard 访问地址：http://${X5_HOST}:3030"
}

# ============================================
# 阶段 5: 安装 Kiosk 依赖
# ============================================
install_kiosk_deps() {
    log_info "阶段 5: 安装 Kiosk 模式依赖..."
    
    ssh_exec "apt update && apt install -y xorg chromium openbox xdotool scrot unclutter"
    
    log_info "Kiosk 依赖安装完成"
}

# ============================================
# 阶段 6: 配置自动登录和 Kiosk
# ============================================
configure_kiosk() {
    log_info "阶段 6: 配置 Kiosk 模式..."
    
    # 6.2 配置 getty 自动登录
    log_info "配置 getty 自动登录..."
    ssh_exec "mkdir -p /etc/systemd/system/getty@tty1.service.d"
    ssh_exec "cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I \$TERM
EOF"
    ssh_exec "systemctl daemon-reload"
    
    # 6.3 配置 .bash_profile
    log_info "配置 .bash_profile 自动 startx..."
    ssh_exec "cat >> ~/.bash_profile << 'EOF'

# 自动启动 X11 在 tty1
if [[ \$(tty) == /dev/tty1 ]]; then
    startx
fi
EOF"
    
    # 6.4-6.5 编写 ~/.xinitrc
    log_info "编写 ~/.xinitrc..."
    ssh_exec "cat > ~/.xinitrc << 'EOF'
#!/bin/sh

# 禁用屏保和 DPMS
xset s off
xset -dpms
xset s noblank

# 设置光标自动隐藏
unclutter -idle 3 -root &

# 启动 Chromium Kiosk 模式
chromium \\
    --kiosk \\
    --noerrdialogs \\
    --disable-infobars \\
    --no-first-run \\
    --disable-check-for-default-browser \\
    --disable-background-networking \\
    --disable-default-apps \\
    --disable-extensions \\
    --disable-sync \\
    --disable-translate \\
    --hide-scrollbars \\
    --window-size=1920,1080 \\
    http://localhost:3030 &

# 启动窗口管理器
exec openbox
EOF"
    ssh_exec "chmod +x ~/.xinitrc"
    
    log_info "Kiosk 配置完成"
}

# ============================================
# 阶段 7: 测试显示
# ============================================
test_display() {
    log_info "阶段 7: 测试显示..."
    
    log_warn "即将手动测试 X11 和 Chromium，请观察显示器..."
    log_warn "按 Ctrl+C 可跳过此步骤"
    read -p "是否继续测试？(y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "启动 X11 测试..."
        ssh_exec "startx" &
        sleep 15
        
        log_info "测试 SSH 远程管理..."
        ssh_exec "DISPLAY=:0 xdotool key F5"
        log_info "页面刷新命令已发送"
        
        log_info "截屏检查..."
        ssh_exec "DISPLAY=:0 scrot /tmp/test_screen.png"
        scp "${X5_USER}@${X5_HOST}:/tmp/test_screen.png" /tmp/test_screen.png
        log_info "截屏已保存到 /tmp/test_screen.png"
        
        log_info "停止测试..."
        ssh_exec "pkill chromium || true"
        ssh_exec "pkill openbox || true"
    else
        log_warn "跳过显示测试"
    fi
}

# ============================================
# 阶段 8: 重启验证
# ============================================
test_reboot() {
    log_info "阶段 8: 重启验证..."
    
    log_warn "即将重启 X5-Server，请观察显示器是否自动显示 Dashboard..."
    read -p "是否继续重启测试？(y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "重启 X5-Server..."
        ssh_exec "reboot" || true
        
        log_info "等待 3 分钟..."
        sleep 180
        
        log_info "验证服务恢复..."
        if ssh_exec "ps aux | grep -q '[c]hromium'"; then
            log_info "Chromium 进程已启动"
        else
            log_warn "Chromium 进程未检测到，请检查显示器"
        fi
        
        log_info "截屏验证..."
        ssh_exec "DISPLAY=:0 scrot /tmp/boot_test.png"
        scp "${X5_USER}@${X5_HOST}:/tmp/boot_test.png" /tmp/boot_test.png
        log_info "重启测试截屏已保存到 /tmp/boot_test.png"
    else
        log_warn "跳过重启测试"
    fi
}

# ============================================
# 主流程
# ============================================
main() {
    echo "=========================================="
    echo "X5-Server 监控大屏自动化部署脚本"
    echo "=========================================="
    echo
    
    if check_local; then
        # 在 Mac 上执行完整流程
        upload_code
        configure_env
        configure_ssh_keys
        deploy_docker
        install_kiosk_deps
        configure_kiosk
        test_display
        test_reboot
    else
        # 在 X5-Server 上执行（假设代码已上传）
        configure_env
        configure_ssh_keys
        deploy_docker
        install_kiosk_deps
        configure_kiosk
    fi
    
    echo
    echo "=========================================="
    log_info "部署完成！"
    echo "=========================================="
    echo
    echo "Dashboard 访问地址：http://${X5_HOST}:3030"
    echo
    echo "下一步："
    echo "  1. 在浏览器访问 Dashboard 验证显示"
    echo "  2. 执行验收测试（参见 DEPLOY-X5.md）"
    echo "  3. 如需重启验证：ssh root@${X5_HOST} 'reboot'"
    echo
}

# 执行
main "$@"
