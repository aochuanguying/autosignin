#!/system/bin/sh

# Termux SSH 开机自启动脚本

LOG_TAG="Termux-SSH"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "=== Termux SSH 启动 ==="

# 等待系统完全启动
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 5
done

# 等待存储挂载
sleep 30

log "启动 Termux 应用"

# 启动 Termux 应用（确保环境就绪）
am start --user 0 com.termux/com.termux.app.TermuxApp >/dev/null 2>&1 || true
sleep 10  # 等待 Termux 完全启动

log "启动 SSH 服务"

# 以 u0_a167 用户身份启动 SSH（关键：使用 su - 用户 -c 方式）
su u0_a167 -c '/data/data/com.termux/files/usr/bin/sshd' >/dev/null 2>&1 &

sleep 8

if pgrep -f sshd >/dev/null 2>&1; then
    log "✓ SSH 启动成功"
else
    log "✗ SSH 启动失败"
fi

log "=== Termux SSH 启动完成 ==="
