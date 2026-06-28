#!/data/data/com.termux/files/usr/bin/bash
# 一键安装和启动脚本

echo "======================================"
echo "Telecom API 一键安装和启动"
echo "======================================"

# 检查是否在 Termux 中
if [ ! -d "/data/data/com.termux/files" ]; then
    echo "错误：此脚本只能在 Termux 中运行"
    exit 1
fi

cd /data/data/com.termux/files/home/android-telecom-api

# 1. 安装 Python 和 Flask
echo "正在安装 Python 和 Flask..."
pkg install python -y
pip install flask

# 2. 创建配置目录
echo "创建配置目录..."
mkdir -p ~/.telecom-api

# 3. 生成 API Token（如果没有）
if [ ! -f ~/.telecom-api/api_token ]; then
    echo "生成 API Token..."
    python3 -c "import secrets; print(secrets.token_urlsafe(32))" > ~/.telecom-api/api_token
    chmod 600 ~/.telecom-api/api_token
    echo "API Token 已生成"
else
    echo "API Token 已存在"
fi

# 4. 设置启动脚本权限
chmod +x start-service.sh
chmod +x boot-start.sh

# 5. 停止可能正在运行的服务
./start-service.sh stop 2>/dev/null || true

# 6. 启动服务
echo "正在启动服务..."
./start-service.sh start

# 7. 显示状态
echo ""
./start-service.sh status

# 8. 显示 API Token
echo ""
echo "API Token:"
./start-service.sh token

# 9. 获取 IP 地址
echo ""
echo "网络信息:"
ip addr show wlan0 | grep "inet " || echo "请检查 WiFi 连接"

echo ""
echo "======================================"
echo "安装完成！"
echo "======================================"
