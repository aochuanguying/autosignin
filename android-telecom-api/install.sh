#!/data/data/com.termux/files/usr/bin/sh
# Android Telecom API 安装脚本
# 用于在已 root 的 Termux 环境中安装和配置服务

echo "======================================"
echo "Android Telecom API 安装脚本"
echo "======================================"

# 检查是否在 Termux 中运行
if [ ! -d "/data/data/com.termux/files" ]; then
    echo "错误：此脚本只能在 Termux 环境中运行"
    exit 1
fi

# 检查 root 权限
echo "检查 root 权限..."
if ! su -c "echo root_access_granted" 2>/dev/null | grep -q "root_access_granted"; then
    echo "警告：未检测到 root 权限，部分功能可能无法正常工作"
    echo "请确保您的设备已 root 并授予 Termux root 权限"
fi

# 更新包管理器
echo "更新 Termux 包管理器..."
pkg update -y

# 安装 Python 和依赖
echo "安装 Python 和相关依赖..."
pkg install -y python sqlite

# 安装 Python 包
echo "安装 Python 依赖包..."
pip install flask

# 创建配置目录
echo "创建配置目录..."
CONFIG_DIR="$HOME/.telecom-api"
mkdir -p "$CONFIG_DIR"

# 生成或读取 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    echo "使用现有的 API Token..."
    API_TOKEN=$(cat "$CONFIG_DIR/api_token")
else
    echo "生成新的 API Token..."
    API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "$API_TOKEN" > "$CONFIG_DIR/api_token"
    chmod 600 "$CONFIG_DIR/api_token"
fi

# 授予读取短信和通话记录数据库的权限
echo "配置数据库访问权限..."
# 注意：这需要 root 权限，并且不同 ROM 可能路径不同
# 脚本会在运行时尝试访问，这里只做提示

# 创建服务启动脚本
echo "创建服务启动脚本..."
cat > "$CONFIG_DIR/start.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
# 启动 Telecom API 服务

CONFIG_DIR="$HOME/.telecom-api"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 加载 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$CONFIG_DIR/api_token")
fi

# 启动服务
echo "启动服务..."
python3 "$SCRIPT_DIR/server.py"
EOF

chmod +x "$CONFIG_DIR/start.sh"

# 创建 systemd 服务文件（如果支持）
if [ -d "/etc/systemd/system" ]; then
    echo "创建 systemd 服务..."
    cat > /etc/systemd/system/telecom-api.service << EOF
[Unit]
Description=Android Telecom API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment=TELECOM_API_TOKEN=$API_TOKEN
ExecStart=/data/data/com.termux/files/usr/bin/python3 $SCRIPT_DIR/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable telecom-api
    echo "systemd 服务已创建并启用"
fi

# 显示完成信息
echo ""
echo "======================================"
echo "安装完成！"
echo "======================================"
echo ""
echo "API Token: $API_TOKEN"
echo "（已保存到 $CONFIG_DIR/api_token）"
echo ""
echo "启动服务："
echo "  $CONFIG_DIR/start.sh"
echo ""
echo "或者手动启动："
echo "  export TELECOM_API_TOKEN=$API_TOKEN"
echo "  python3 server.py"
echo ""
echo "服务将在 http://0.0.0.0:5000 监听"
echo ""
echo "API 端点:"
echo "  GET  /health              - 健康检查"
echo "  POST /api/v1/call         - 拨打电话"
echo "  POST /api/v1/sms/send     - 发送短信"
echo "  GET  /api/v1/sms/inbox    - 获取短信收件箱"
echo "  GET  /api/v1/call/log     - 获取通话记录"
echo "  GET  /api/v1/device/info  - 获取设备信息"
echo ""
echo "使用示例:"
echo "  curl -X POST http://localhost:5000/api/v1/call \\"
echo "    -H \"Authorization: Bearer $API_TOKEN\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"phone_number\": \"1234567890\"}'"
echo ""
