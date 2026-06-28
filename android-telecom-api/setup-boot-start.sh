#!/data/data/com.termux/files/usr/bin/sh
# 设置开机自启动脚本
# 此脚本需要在 Termux 环境中运行一次，用于配置开机自启动

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOT_DIR="$HOME/.termux/boot"

echo "======================================"
echo "Telecom API 开机自启动配置"
echo "======================================"
echo ""

# 检查是否在 Termux 中运行
if [ ! -d "/data/data/com.termux" ]; then
    echo "错误：此脚本必须在 Termux 环境中运行"
    exit 1
fi

# 1. 安装 termux-boot 包
echo "1. 安装 termux-boot 包..."
pkg install termux-boot -y
if [ $? -eq 0 ]; then
    echo "   ✓ termux-boot 安装成功"
else
    echo "   ✗ termux-boot 安装失败"
    exit 1
fi

# 2. 创建 boot 目录
echo ""
echo "2. 创建 boot 目录..."
mkdir -p "$BOOT_DIR"
if [ $? -eq 0 ]; then
    echo "   ✓ 目录创建成功：$BOOT_DIR"
else
    echo "   ✗ 目录创建失败"
    exit 1
fi

# 3. 复制启动脚本
echo ""
echo "3. 复制启动脚本到 boot 目录..."
cp "$SCRIPT_DIR/boot-start.sh" "$BOOT_DIR/"
if [ $? -eq 0 ]; then
    echo "   ✓ 脚本复制成功"
else
    echo "   ✗ 脚本复制失败"
    exit 1
fi

# 4. 设置执行权限
echo ""
echo "4. 设置执行权限..."
chmod +x "$BOOT_DIR/boot-start.sh"
chmod +x "$SCRIPT_DIR/boot-start.sh"
chmod +x "$SCRIPT_DIR/start-service.sh"
echo "   ✓ 权限设置完成"

# 5. 验证配置
echo ""
echo "5. 验证配置..."
if [ -f "$BOOT_DIR/boot-start.sh" ]; then
    echo "   ✓ 启动脚本已就位：$BOOT_DIR/boot-start.sh"
    echo "   ✓ 主启动脚本：$SCRIPT_DIR/boot-start.sh"
else
    echo "   ✗ 配置验证失败"
    exit 1
fi

echo ""
echo "======================================"
echo "✓ 开机自启动配置完成！"
echo "======================================"
echo ""
echo "下次设备重启后，Telecom API 服务将自动启动。"
echo ""
echo "您可以测试启动脚本："
echo "  $SCRIPT_DIR/boot-start.sh"
echo ""
echo "或者手动启动服务："
echo "  $SCRIPT_DIR/start-service.sh start"
echo ""
