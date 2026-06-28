#!/data/data/com.termux/files/usr/bin/sh
# Telecom API 服务管理脚本
# 支持启动、停止、重启和查看状态

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$HOME/.telecom-api/server.pid"
LOG_FILE="$HOME/.telecom-api/server.log"
CONFIG_DIR="$HOME/.telecom-api"

# 确保配置目录存在
mkdir -p "$CONFIG_DIR"

# 加载 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$CONFIG_DIR/api_token")
fi

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务已在运行 (PID: $(cat "$PID_FILE"))"
        exit 1
    fi
    
    echo "启动 Telecom API 服务..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务启动成功 (PID: $(cat "$PID_FILE"))"
        echo "日志文件：$LOG_FILE"
    else
        echo "服务启动失败，请查看日志：$LOG_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "服务未运行 (无 PID 文件)"
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "服务未运行 (进程不存在)"
        rm -f "$PID_FILE"
        exit 1
    fi
    
    echo "停止服务 (PID: $PID)..."
    kill "$PID"
    
    # 等待进程结束
    i=1
    while [ $i -le 10 ]; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "服务已停止"
            rm -f "$PID_FILE"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    
    # 强制停止
    echo "强制停止服务..."
    kill -9 "$PID"
    rm -f "$PID_FILE"
    echo "服务已强制停止"
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务运行中"
        echo "  PID: $(cat "$PID_FILE")"
        echo "  端口：5000"
        echo "  日志：$LOG_FILE"
        
        # 显示最近 10 行日志
        echo ""
        echo "最近日志:"
        tail -n 10 "$LOG_FILE"
    else
        echo "服务未运行"
        rm -f "$PID_FILE"
        exit 1
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -n 50 "$LOG_FILE"
    else
        echo "日志文件不存在"
    fi
}

show_token() {
    if [ -f "$CONFIG_DIR/api_token" ]; then
        TOKEN=$(cat "$CONFIG_DIR/api_token")
        echo "API Token: $TOKEN"
    else
        echo "API Token 未设置"
    fi
}

# 主程序
case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    token)
        show_token
        ;;
    *)
        echo "用法：$0 {start|stop|restart|status|logs|token}"
        echo ""
        echo "命令:"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看最近日志"
        echo "  token   - 显示 API Token"
        exit 1
        ;;
esac
