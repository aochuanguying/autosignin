#!/system/bin/sh
# WireGuard be86u 开机自启动脚本

LOG_TAG="WireGuard-Boot"
TARGET_IP="10.6.0.2"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "等待系统完全启动..."

# 等待系统完全启动（与 termux-ssh.sh 一致）
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 5
done

# 错开 AutoJS6 的启动时间
sleep 25

log "启动 WireGuard 应用"

# 方法 1: 先启动应用界面
am start -n com.wireguard.android/.activity.MainActivity >/dev/null 2>&1
sleep 3

# 方法 2: 发送启动隧道广播
log "启动 be86u 隧道"
am broadcast --user 0 -a com.wireguard.android.action.SET_TUNNEL_STATE \
    -e com.wireguard.android.extra.TUNNEL_NAME be86u \
    -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1
sleep 5

# 检查是否启动成功（与看门狗一致的检查方法）
if ip addr show tun0 2>/dev/null | grep -q "$TARGET_IP"; then
    log "✓ WireGuard 隧道启动成功"
else
    log "⚠ 隧道可能未启动，看门狗将自动重连"
fi
