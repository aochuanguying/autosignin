#!/data/data/com.termux/files/usr/bin/bash
# Telecom API 开机自启动脚本
# 在设备启动后自动启动服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_SCRIPT="$SCRIPT_DIR/start-service.sh"
PID_FILE="$HOME/.telecom-api/server.pid"
LOG_FILE="$HOME/.telecom-api/boot-start.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== 开机自启动脚本开始执行 ==="

# 等待系统完全启动（可选延迟）
log "等待系统启动完成..."
sleep 30

# 检查服务是否已经在运行
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    log "服务已在运行 (PID: $(cat "$PID_FILE"))，无需启动"
    exit 0
fi

# 确保服务脚本存在且可执行
if [ ! -x "$SERVICE_SCRIPT" ]; then
    log "错误：服务脚本不存在或不可执行：$SERVICE_SCRIPT"
    exit 1
fi

# 启动服务
log "正在启动 Telecom API 服务..."
cd "$SCRIPT_DIR"

# 加载 API Token
if [ -f "$HOME/.telecom-api/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$HOME/.telecom-api/api_token")
    log "已加载 API Token"
fi

# 启动服务
nohup python3 "$SCRIPT_DIR/server.py" > "$HOME/.telecom-api/server.log" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PID_FILE"

# 等待并验证服务是否启动成功
sleep 3

if kill -0 $SERVER_PID 2>/dev/null; then
    log "服务启动成功 (PID: $SERVER_PID)"
    log "=== 开机自启动完成 ==="
    exit 0
else
    log "服务启动失败，PID: $SERVER_PID 不存在"
    log "=== 开机自启动失败 ==="
    exit 1
fi
