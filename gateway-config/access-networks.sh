#!/bin/sh
# ===============================================================
# access-networks.sh - 跨子网设备管理通道（光猫 + 交换机）
# 部署位置: /jffs/scripts/access-networks.sh
# 调用方式: nat-start 调用 + cron 定时自检
# ===============================================================

# ================= 配置区域 =================
WAN_IF="eth0"

# 通道1：光猫
MODEM_TARGET_IP="192.168.1.1"
ROUTER_IP_MODEM="192.168.1.111"
MODEM_MASK="255.255.255.0"
MODEM_ALIAS="${WAN_IF}:0"

# 通道2：交换机
SWITCH_TARGET_IP="192.168.10.12"
ROUTER_IP_SWITCH="192.168.10.111"
SWITCH_MASK="255.255.255.0"
SWITCH_ALIAS="${WAN_IF}:1"

# 日志
LOG_FILE="/tmp/access-networks.log"
LOG_MAX_LINES=200
# ===========================================

# --- 日志函数 ---
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
    logger -t "AccessNet" "$1"
    # 日志轮转
    if [ -f "$LOG_FILE" ]; then
        LINES=$(wc -l < "$LOG_FILE" 2>/dev/null || echo 0)
        if [ "$LINES" -gt "$LOG_MAX_LINES" ]; then
            tail -100 "$LOG_FILE" > "${LOG_FILE}.tmp"
            mv "${LOG_FILE}.tmp" "$LOG_FILE"
        fi
    fi
}

# --- 检查并修复 IP alias ---
ensure_alias() {
    local ALIAS="$1"
    local IP="$2"
    local MASK="$3"
    local NAME="$4"

    # 检查 alias 是否存在且 IP 正确
    CURRENT_IP=$(ifconfig "$ALIAS" 2>/dev/null | grep 'inet addr' | awk -F'addr:' '{print $2}' | awk '{print $1}')

    if [ "$CURRENT_IP" = "$IP" ]; then
        return 0  # 正常
    fi

    # 需要修复
    ifconfig "$ALIAS" down 2>/dev/null
    ifconfig "$ALIAS" "$IP" netmask "$MASK" up
    if [ $? -eq 0 ]; then
        log "[修复] ${NAME} alias ${ALIAS} = ${IP} 已恢复"
        return 1  # 修复了
    else
        log "[错误] ${NAME} alias ${ALIAS} = ${IP} 设置失败!"
        return 2  # 失败
    fi
}

# --- 检查并修复 iptables 规则 ---
ensure_nat_rule() {
    local TARGET_IP="$1"
    local NAME="$2"

    # 检查规则是否已存在
    iptables -t nat -C POSTROUTING -o "$WAN_IF" -d "$TARGET_IP" -j MASQUERADE 2>/dev/null
    if [ $? -eq 0 ]; then
        return 0  # 已存在
    fi

    # 需要添加
    iptables -t nat -I POSTROUTING -o "$WAN_IF" -d "$TARGET_IP" -j MASQUERADE
    if [ $? -eq 0 ]; then
        log "[修复] ${NAME} NAT 规则已恢复 (-d ${TARGET_IP})"
        return 1
    else
        log "[错误] ${NAME} NAT 规则添加失败!"
        return 2
    fi
}

# --- 连通性验证 ---
verify_connectivity() {
    local TARGET_IP="$1"
    local NAME="$2"

    ping -c 1 -W 2 "$TARGET_IP" > /dev/null 2>&1
    if [ $? -eq 0 ]; then
        return 0
    else
        log "[警告] ${NAME} (${TARGET_IP}) ping 不通"
        return 1
    fi
}

# === 主逻辑 ===
MODE="${1:-check}"  # check(默认/cron) 或 init(nat-start首次调用)
FIXED=0

if [ "$MODE" = "init" ]; then
    log "=== nat-start 触发，初始化双向管理通道 ==="
fi

# 1. 确保光猫通道
ensure_alias "$MODEM_ALIAS" "$ROUTER_IP_MODEM" "$MODEM_MASK" "光猫"
[ $? -eq 1 ] && FIXED=$((FIXED + 1))

ensure_nat_rule "$MODEM_TARGET_IP" "光猫"
[ $? -eq 1 ] && FIXED=$((FIXED + 1))

# 2. 确保交换机通道
ensure_alias "$SWITCH_ALIAS" "$ROUTER_IP_SWITCH" "$SWITCH_MASK" "交换机"
[ $? -eq 1 ] && FIXED=$((FIXED + 1))

ensure_nat_rule "$SWITCH_TARGET_IP" "交换机"
[ $? -eq 1 ] && FIXED=$((FIXED + 1))

# 3. 连通性验证（仅在 init 模式或修复后）
if [ "$MODE" = "init" ] || [ "$FIXED" -gt 0 ]; then
    sleep 1
    verify_connectivity "$MODEM_TARGET_IP" "光猫"
    MODEM_OK=$?
    verify_connectivity "$SWITCH_TARGET_IP" "交换机"
    SWITCH_OK=$?

    if [ "$MODE" = "init" ]; then
        log "初始化完成: 光猫=$([ $MODEM_OK -eq 0 ] && echo 'OK' || echo 'FAIL') 交换机=$([ $SWITCH_OK -eq 0 ] && echo 'OK' || echo 'FAIL')"
    elif [ "$FIXED" -gt 0 ]; then
        log "自修复完成(修复${FIXED}项): 光猫=$([ $MODEM_OK -eq 0 ] && echo 'OK' || echo 'FAIL') 交换机=$([ $SWITCH_OK -eq 0 ] && echo 'OK' || echo 'FAIL')"
    fi
fi
