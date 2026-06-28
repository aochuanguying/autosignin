#!/system/bin/sh
# SSH 看门狗脚本
# 用途：持续监控 SSH 服务，挂掉自动重启

LOG_TAG="SSHD-Watchdog"
SSHD_PATH="/data/data/com.termux/files/usr/bin/sshd"
CHECK_INTERVAL=30  # 每 30 秒检查一次
MAX_RETRY=3        # 最大重试次数
RETRY_DELAY=2      # 重试间隔（秒）

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "启动 SSH 看门狗"
log "检查间隔：${CHECK_INTERVAL}秒"

# 等待系统完全启动
sleep 60

while true; do
    if ! pgrep -f sshd >/dev/null 2>&1; then
        log "⚠ 检测到 SSH 未运行，准备启动..."
        
        # 尝试启动 SSH，最多重试 MAX_RETRY 次
        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "  启动尝试 $i/$MAX_RETRY"
            $SSHD_PATH
            sleep 8
            
            if pgrep -f sshd >/dev/null 2>&1; then
                log "✓ SSH 启动成功"
                success=1
                break
            else
                log "  启动失败，${RETRY_DELAY}秒后重试..."
                sleep "$RETRY_DELAY"
            fi
        done
        
        if [ $success -eq 0 ]; then
            log "✗ SSH 启动失败，将在下次循环继续尝试"
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
