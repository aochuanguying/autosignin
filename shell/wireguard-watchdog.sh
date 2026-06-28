#!/system/bin/sh
# WireGuard be86u 看门狗脚本（真正版本）
# 用途：持续监控 WireGuard 隧道状态，断开自动重连

LOG_TAG="WireGuard-Watchdog"
TUNNEL_NAME="be86u"
TARGET_IP="10.6.0.2"
CHECK_INTERVAL=30  # 每 30 秒检查一次
MAX_RETRY=3        # 最大重试次数
RETRY_DELAY=50     # 重试间隔（秒）- 覆盖 AutoJS 执行时间 + 缓冲

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

# 检查 tun0 接口是否存在且有正确的 IP
check_tunnel() {
    # 合并检查：接口存在且包含目标 IP
    if ip addr show tun0 2>/dev/null | grep -q "$TARGET_IP"; then
        return 0
    fi
    return 1
}

# 启动 WireGuard 隧道
start_tunnel() {
    # 方法 1: 发送启动隧道广播（快速尝试）
    log "  方法 1: 发送广播..."
    am broadcast --user 0 \
        -a com.wireguard.android.action.SET_TUNNEL_STATE \
        -e com.wireguard.android.extra.TUNNEL_NAME "$TUNNEL_NAME" \
        -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1
    
    # 循环检查广播是否生效（每 2 秒检查，最多 10 秒）
    for j in $(seq 1 5); do
        sleep 2
        if check_tunnel; then
            log "✓ 广播方式启动成功"
            return 0
        fi
        log "  等待广播生效... ($((j * 2))/10 秒)"
    done
    
    log "  广播方式未成功"
    
    # 方法 2: 调用 AutoJS 脚本点击开关（可靠）
    log "  方法 2: AutoJS 脚本..."
    am start -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
        -a android.intent.action.VIEW \
        -d "file:///sdcard/脚本/wireguard-connect.js" \
        -t "application/x-javascript" >/dev/null 2>&1
    
    # 循环检查 AutoJS 脚本执行（每 5 秒检查，最多 40 秒）
    for j in $(seq 1 8); do
        sleep 5
        if check_tunnel; then
            log "✓ AutoJS 方式启动成功"
            return 0
        fi
        log "  等待 AutoJS 执行... ($((j * 5))/40 秒)"
    done
    
    log "✗ AutoJS 方式超时"
    return 1
}

log "看门狗启动 - 监控隧道：$TUNNEL_NAME"
log "检查间隔：${CHECK_INTERVAL}秒"

# 等待系统完全启动
sleep 60

while true; do
    if check_tunnel; then
        # 隧道正常，等待下次检查
        sleep "$CHECK_INTERVAL"
    else
        log "⚠ 检测到隧道断开！准备重连..."
        
        # 尝试重连
        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "重试 $i/$MAX_RETRY"
            if start_tunnel; then
                success=1
                break
            fi
            log "等待 ${RETRY_DELAY}秒后重试..."
            sleep "$RETRY_DELAY"
        done
        
        if [ $success -eq 0 ]; then
            log "✗ 重连失败，将在下次循环继续尝试"
        fi
        
        # 重连后已等待足够时间，直接开始下次检查
    fi
done
