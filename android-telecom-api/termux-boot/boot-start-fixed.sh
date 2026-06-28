#!/data/data/com.termux/files/usr/bin/bash
# Telecom API 开机自启动脚本

SCRIPT_DIR="/data/data/com.termux/files/home/android-telecom-api"
PID_FILE="/data/data/com.termux/files/home/.telecom-api/server.pid"
LOG_FILE="/data/data/com.termux/files/home/.telecom-api/boot-start.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== 开机自启动脚本开始执行 ==="
log "等待系统启动完成..."
sleep 10

if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    log "服务已在运行 (PID: $(cat "$PID_FILE"))，无需启动"
    exit 0
fi

log "正在启动 Telecom API 服务..."
cd "$SCRIPT_DIR"

if [ -f "/data/data/com.termux/files/home/.telecom-api/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "/data/data/com.termux/files/home/.telecom-api/api_token")
    log "已加载 API Token"
fi

nohup python3 "$SCRIPT_DIR/server.py" > "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PID_FILE"

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
