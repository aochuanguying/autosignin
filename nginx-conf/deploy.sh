#!/bin/bash
# ============================================
# Nginx 配置部署脚本
# 用法: bash deploy.sh
# ============================================

SERVER="wangfuwei@10.30.5.33"
PORT=22
REMOTE_CONF="/usr/local/nginx/conf"
REMOTE_NGINX="/usr/local/nginx/sbin/nginx"

echo "=== Nginx 配置部署 ==="
echo ""

# 1. 备份远程当前配置
echo "[1/5] 备份远程现有配置..."
ssh -p $PORT $SERVER "cp $REMOTE_CONF/nginx.conf $REMOTE_CONF/nginx.conf_bak_$(date +%Y%m%d_%H%M%S)"
ssh -p $PORT $SERVER "cp $REMOTE_CONF/conf.d/higpt-gateway.conf $REMOTE_CONF/conf.d/higpt-gateway.conf_bak_$(date +%Y%m%d_%H%M%S)"
echo "  备份完成"

# 2. 上传新配置
echo "[2/5] 上传新配置..."
scp -P $PORT nginx.conf $SERVER:$REMOTE_CONF/nginx.conf
scp -P $PORT conf.d/higpt-gateway.conf $SERVER:$REMOTE_CONF/conf.d/higpt-gateway.conf
echo "  上传完成"

# 3. 测试配置
echo "[3/5] 测试配置语法..."
ssh -p $PORT $SERVER "$REMOTE_NGINX -t"
if [ $? -ne 0 ]; then
    echo "  ❌ 配置语法错误! 回滚..."
    ssh -p $PORT $SERVER "cp $REMOTE_CONF/nginx.conf_bak $REMOTE_CONF/nginx.conf"
    ssh -p $PORT $SERVER "cp $REMOTE_CONF/conf.d/higpt-gateway.conf_bak $REMOTE_CONF/conf.d/higpt-gateway.conf"
    echo "  已回滚到上一版本"
    exit 1
fi
echo "  ✅ 配置语法正确"

# 4. 重载配置
echo "[4/5] 重载 nginx..."
ssh -p $PORT $SERVER "$REMOTE_NGINX -s reload"
echo "  ✅ 重载完成"

# 5. 验证
echo "[5/5] 验证服务状态..."
ssh -p $PORT $SERVER "ps aux | grep nginx | grep -v grep | head -5"
echo ""
echo "=== 部署完成 ==="
echo ""
echo "优化内容:"
echo "  - 添加默认 server 拦截公网扫描 (return 444)"
echo "  - 内网服务增加 IP 白名单限制"
echo "  - worker_processes 改为 auto"
echo "  - worker_connections 提升至 65535"
echo "  - 启用 epoll + multi_accept"
echo "  - 启用 gzip 压缩"
echo "  - 添加 HTTP->HTTPS 重定向"
echo "  - SSL 加固 (现代密码套件)"
echo "  - 移除 idea.lanyus.com 代理"
