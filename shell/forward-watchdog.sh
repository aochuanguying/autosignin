#!/system/bin/sh
# 未接来电 & 短信转发服务看门狗
# 用途：监控 call_sms_forwarding.py 进程，挂掉自动重启
# 放置位置：/data/adb/service.d/forward-watchdog.sh

LOG_TAG="Forward-Watchdog"
CHECK_INTERVAL=30
MAX_RETRY=3
RETRY_DELAY=5

FORWARD_SCRIPT="/data/data/com.termux/files/home/scripts/call_sms_forwarding.py"
PYTHON3="/data/data/com.termux/files/usr/bin/python3"
PID_FILE="/data/data/com.termux/files/home/.telecom-api/forward.pid"
TOKEN_FILE="/data/data/com.termux/files/home/.telecom-api/forward_token"
WATCHDOG_PID_FILE="/data/data/com.termux/files/home/.telecom-api/watchdog.pid"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

# 单实例保护：如果另一个看门狗在运行则退出
if [ -f "$WATCHDOG_PID_FILE" ]; then
    OLD_PID=$(cat "$WATCHDOG_PID_FILE" 2>/dev/null)
    if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        log "另一个看门狗实例已在运行 (PID: $OLD_PID)，退出"
        exit 0
    fi
fi

# 确保目录存在并写入 PID
mkdir -p /data/data/com.termux/files/home/.telecom-api
echo $$ > "$WATCHDOG_PID_FILE"

log "看门狗启动 (PID: $$)"
log "监控脚本：$FORWARD_SCRIPT"
log "检查间隔：${CHECK_INTERVAL}秒"

# 等待系统完全启动
sleep 60

while true; do
    # 使用精确计数，排除 grep 自身匹配
    RUNNING_COUNT=$(pgrep -f "call_sms_forwarding.py" 2>/dev/null | wc -l)
    if [ "$RUNNING_COUNT" -ge 1 ]; then
        sleep "$CHECK_INTERVAL"
    else
        log "⚠ 检测到转发服务未运行，准备启动..."

        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "  启动尝试 $i/$MAX_RETRY"

            # 加载 Token
            if [ -f "$TOKEN_FILE" ]; then
                export FORWARD_API_TOKEN=$(cat "$TOKEN_FILE")
            fi

            # 确保 PID 目录存在
            mkdir -p /data/data/com.termux/files/home/.telecom-api

            # 启动转发服务
            nohup $PYTHON3 "$FORWARD_SCRIPT" >/dev/null 2>&1 &
            FORWARD_PID=$!
            echo $FORWARD_PID > "$PID_FILE"
            log "  进程 PID: $FORWARD_PID"

            sleep 5

            if kill -0 $FORWARD_PID 2>/dev/null; then
                log "✓ 转发服务启动成功 (PID: $FORWARD_PID)"
                success=1
                break
            else
                log "  启动失败，${RETRY_DELAY}秒后重试..."
                sleep "$RETRY_DELAY"
            fi
        done

        if [ $success -eq 0 ]; then
            log "✗ 转发服务启动失败，将在下次循环继续尝试"
        fi
    fi
done
