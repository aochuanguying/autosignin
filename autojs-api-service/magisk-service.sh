#!/system/bin/sh
# AutoJS API Service - Magisk 开机自启动脚本（修复版）
# 放置位置：/data/adb/service.d/autojs-api-service.sh

# ==================== 配置区域 ====================
API_PORT=8899
LOG_TAG="AutoJS-API-Service"
PYTHON_PATH="/data/data/com.termux/files/usr/bin/python3"

# ==================== 日志函数 ====================
log() {
    /system/bin/log -t "${LOG_TAG}" "$1"
}

# ==================== 等待系统就绪 ====================
wait_for_system() {
    log "等待系统启动完成..."
    
    # 等待 boot_completed
    while [ "$(getprop sys.boot_completed)" != "1" ]; do
        sleep 1
    done
    
    # 等待网络就绪
    log "等待网络就绪..."
    sleep 10
    
    # 等待存储就绪
    while [ ! -d "/sdcard" ]; do
        sleep 1
    done
    
    log "系统已就绪"
}

# ==================== 启动 Python HTTP 服务 ====================
start_http_server() {
    log "启动 AutoJS API HTTP 服务器..."
    
    # 检查 Python 是否可用
    if [ ! -f "${PYTHON_PATH}" ]; then
        log "错误：Python3 未找到 (${PYTHON_PATH})"
        return 1
    fi
    
    # 启动服务（使用 Termux 的 Python）
    cd /sdcard
    nohup ${PYTHON_PATH} /sdcard/autojs-api-server.py > /sdcard/autojs-api.log 2>&1 &
    echo $! > /sdcard/autojs-api.pid
    
    sleep 3
    
    # 验证启动
    if netstat -tlnp 2>/dev/null | grep -q ":${API_PORT}"; then
        log "✓ HTTP 服务器启动成功 (PID: $(cat /sdcard/autojs-api.pid))"
        return 0
    else
        log "✗ HTTP 服务器启动失败"
        return 1
    fi
}

# ==================== 看门狗监控 ====================
watchdog() {
    local restart_count=0
    local last_restart_time=0
    local max_restart=5
    local restart_interval=60
    local check_interval=30
    
    log "看门狗启动，监控端口 ${API_PORT}"
    
    while true; do
        sleep ${check_interval}
        
        # 检查端口
        if ! netstat -tlnp 2>/dev/null | grep -q ":${API_PORT}"; then
            local current_time=$(date +%s)
            
            # 检查重启间隔
            if [ $((current_time - last_restart_time)) -lt ${restart_interval} ]; then
                log "警告：服务异常，但重启间隔过短，等待中..."
                continue
            fi
            
            log "检测到服务异常，尝试重启..."
            
            if [ ${restart_count} -ge ${max_restart} ]; then
                log "错误：达到最大重启次数 (${max_restart})，停止重启"
                continue
            fi
            
            # 重启服务
            kill $(cat /sdcard/autojs-api.pid) 2>/dev/null
            sleep 2
            
            if start_http_server; then
                restart_count=0
                last_restart_time=${current_time}
                log "✓ 服务重启成功"
            else
                restart_count=$((restart_count + 1))
                last_restart_time=${current_time}
                log "✗ 服务重启失败 (第 ${restart_count}/${max_restart} 次)"
            fi
        fi
    done
}

# ==================== 主程序 ====================
main() {
    log "========================================="
    log "AutoJS API Service 开机自启动"
    log "========================================="
    
    # 等待系统就绪
    wait_for_system
    
    # 启动 HTTP 服务
    if start_http_server; then
        log "✓ 服务启动成功"
    else
        log "✗ 服务启动失败"
        exit 1
    fi
    
    # 启动看门狗
    watchdog
}

# 启动
main
