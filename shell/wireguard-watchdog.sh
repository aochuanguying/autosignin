#!/system/bin/sh
# WireGuard be86u 看门狗脚本
# 功能：监控 WireGuard 连接（含 ping 连通性检查），断联时重启隧道
# 前提：be86u 端不要下发 DNS（否则 DNS 走隧道，隧道不通时 DNS 也不通导致 Endpoint 域名无法解析）
# 放置位置：/data/adb/service.d/wireguard-watchdog.sh

LOG_TAG="WireGuard-Watchdog"
TUNNEL_NAME="be86u"
TARGET_IP="10.6.0.2"
GATEWAY_IP="10.6.0.1"
CHECK_INTERVAL=30        # 常规检查间隔（秒）
MAX_RETRY=3              # 最大重试次数
RETRY_DELAY=60           # 重试间隔（秒）

log() {
    /system/bin/log -t "$LOG_TAG" "$1" < /dev/null
}

# 检查 tun0 接口是否存在且有正确的 IP
check_interface() {
    ip addr show tun0 2>/dev/null | grep -q "$TARGET_IP"
    return $?
}

# 检查 WireGuard 连接是否真正可用（ping 网关）
check_connectivity() {
    ping -c 1 -W 3 "$GATEWAY_IP" >/dev/null 2>&1
    return $?
}

# 综合检查：接口存在 + ping 通网关
check_tunnel() {
    if ! check_interface; then
        return 1
    fi
    if ! check_connectivity; then
        return 1
    fi
    return 0
}

# 重启 WireGuard 隧道（先关后开，WireGuard app 会用系统 DNS 重新解析 Endpoint 域名）
restart_tunnel() {
    # Step 1: 先关闭隧道
    log "  关闭隧道..."
    am broadcast --user 0 \
        -a com.wireguard.android.action.SET_TUNNEL_STATE \
        -e com.wireguard.android.extra.TUNNEL_NAME "$TUNNEL_NAME" \
        -e com.wireguard.android.extra.TUNNEL_STATE false >/dev/null 2>&1
    sleep 3

    # 如果 broadcast 关闭不生效（VPN always-on 阻止），强制杀进程
    if check_interface; then
        log "  broadcast 关闭无效，强制重启 WireGuard..."
        am force-stop com.wireguard.android
        sleep 2
    fi

    # Step 2: 重新启动隧道
    log "  启动隧道..."
    am broadcast --user 0 \
        -a com.wireguard.android.action.SET_TUNNEL_STATE \
        -e com.wireguard.android.extra.TUNNEL_NAME "$TUNNEL_NAME" \
        -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1

    # 等待隧道建立并检查连通性（最多 20 秒）
    for j in $(seq 1 10); do
        sleep 2
        if check_tunnel; then
            log "✓ 隧道重启成功，ping 正常"
            return 0
        fi
        log "  等待中... ($((j * 2))/20 秒)"
    done
    return 1
}

# 通过 AutoJS6 脚本恢复连接（兜底方案）
autoJS_recover() {
    log "  尝试 AutoJS6 脚本..."
    am start -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
        -a android.intent.action.VIEW \
        -d "file:///sdcard/脚本/wireguard-connect.js" \
        -t "application/x-javascript" >/dev/null 2>&1

    # 等待脚本执行（最多 50 秒）
    for j in $(seq 1 10); do
        sleep 5
        if check_tunnel; then
            log "✓ AutoJS6 恢复成功"
            return 0
        fi
        log "  等待 AutoJS6... ($((j * 5))/50 秒)"
    done
    return 1
}

log "看门狗启动 - 监控隧道：$TUNNEL_NAME"
log "检查间隔：${CHECK_INTERVAL}秒，网关：${GATEWAY_IP}"

# 等待系统完全启动
sleep 60

while true; do
    if check_tunnel; then
        # 隧道正常（接口存在 + ping 通），等待下次检查
        sleep "$CHECK_INTERVAL"
    else
        if ! check_interface; then
            log "⚠ tun0 不存在，准备重连..."
        else
            log "⚠ tun0 存在但 ping 不通（假死状态），准备重启..."
        fi

        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "重试 $i/$MAX_RETRY"
            if restart_tunnel; then
                success=1
                break
            fi
            log "等待 ${RETRY_DELAY}秒后重试..."
            sleep "$RETRY_DELAY"
        done

        # 广播方式失败，尝试 AutoJS6
        if [ $success -eq 0 ]; then
            log "广播方式失败，尝试 AutoJS6 兜底"
            if autoJS_recover; then
                success=1
            fi
        fi

        if [ $success -eq 0 ]; then
            log "✗ 所有方式重连失败，将在下次循环继续尝试"
        fi
    fi
done
