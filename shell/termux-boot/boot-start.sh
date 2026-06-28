#!/data/data/com.termux/files/usr/bin/bash
# Telecom API & 转发服务 开机自启动脚本

SCRIPT_DIR="/data/data/com.termux/files/home/android-telecom-api"
PID_FILE="/data/data/com.termux/files/home/.telecom-api/server.pid"

# 转发服务配置
FORWARD_SCRIPT="/data/data/com.termux/files/home/scripts/call_sms_forwarding.py"
FORWARD_PID_FILE="/data/data/com.termux/files/home/.telecom-api/forward.pid"

log() {
    /system/bin/log -t "Telecom-API" "$1"
}

log "=== 开机自启动脚本开始执行 ==="
log "等待系统启动完成..."
sleep 10

# ---- Telecom API 服务 ----

if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    log "Telecom API 已在运行 (PID: $(cat "$PID_FILE"))"
else
    log "正在启动 Telecom API 服务..."
    cd "$SCRIPT_DIR"

    if [ -f "/data/data/com.termux/files/home/.telecom-api/api_token" ]; then
        export TELECOM_API_TOKEN=$(cat "/data/data/com.termux/files/home/.telecom-api/api_token")
        log "已加载 API Token"
    fi

    nohup python3 "$SCRIPT_DIR/server.py" >/dev/null 2>&1 &
    SERVER_PID=$!
    echo $SERVER_PID > "$PID_FILE"

    sleep 3

    if kill -0 $SERVER_PID 2>/dev/null; then
        log "✓ Telecom API 启动成功 (PID: $SERVER_PID)"
    else
        log "✗ Telecom API 启动失败"
    fi
fi

# ---- 未接来电 & 短信转发服务 ----

if [ -f "$FORWARD_PID_FILE" ] && kill -0 $(cat "$FORWARD_PID_FILE") 2>/dev/null; then
    log "转发服务已在运行 (PID: $(cat "$FORWARD_PID_FILE"))"
else
    if [ -f "$FORWARD_SCRIPT" ]; then
        log "正在启动转发服务..."

        if [ -f "/data/data/com.termux/files/home/.telecom-api/forward_token" ]; then
            export FORWARD_API_TOKEN=$(cat "/data/data/com.termux/files/home/.telecom-api/forward_token")
            log "已加载转发 API Token"
        fi

        nohup python3 "$FORWARD_SCRIPT" >/dev/null 2>&1 &
        FORWARD_PID=$!
        echo $FORWARD_PID > "$FORWARD_PID_FILE"

        sleep 2

        if kill -0 $FORWARD_PID 2>/dev/null; then
            log "✓ 转发服务启动成功 (PID: $FORWARD_PID)"
        else
            log "✗ 转发服务启动失败"
        fi
    else
        log "转发脚本不存在: $FORWARD_SCRIPT"
    fi
fi

log "=== 开机自启动完成 ==="
