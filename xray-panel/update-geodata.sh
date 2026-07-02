#!/bin/sh
# 定时更新 geoip.dat 和 geosite.dat
# 使用 Loyalsoldier 维护的增强规则集（推荐，更新频率高）
# 部署路径: /usr/local/xray/update-geodata.sh
# Crontab: 0 4 * * 1 /usr/local/xray/update-geodata.sh

XRAY_DIR="/usr/local/xray"
TMP_DIR="/tmp/geodata_update"
LOG="/tmp/geodata_update.log"

GEOIP_URL="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geoip.dat"
GEOSITE_URL="https://github.com/Loyalsoldier/v2ray-rules-dat/releases/latest/download/geosite.dat"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

log "开始更新 geodata..."

mkdir -p "$TMP_DIR"

# 下载 geoip.dat
curl -sL --connect-timeout 30 --max-time 120 -o "$TMP_DIR/geoip.dat" "$GEOIP_URL"
if [ $? -ne 0 ] || [ ! -s "$TMP_DIR/geoip.dat" ]; then
    log "错误: geoip.dat 下载失败"
    rm -rf "$TMP_DIR"
    exit 1
fi

# 下载 geosite.dat
curl -sL --connect-timeout 30 --max-time 120 -o "$TMP_DIR/geosite.dat" "$GEOSITE_URL"
if [ $? -ne 0 ] || [ ! -s "$TMP_DIR/geosite.dat" ]; then
    log "错误: geosite.dat 下载失败"
    rm -rf "$TMP_DIR"
    exit 1
fi

# 验证文件大小（至少 1MB，防止下载到错误页面）
GEOIP_SIZE=$(wc -c < "$TMP_DIR/geoip.dat")
GEOSITE_SIZE=$(wc -c < "$TMP_DIR/geosite.dat")

if [ "$GEOIP_SIZE" -lt 1000000 ] || [ "$GEOSITE_SIZE" -lt 1000000 ]; then
    log "错误: 文件大小异常 (geoip: ${GEOIP_SIZE}B, geosite: ${GEOSITE_SIZE}B)"
    rm -rf "$TMP_DIR"
    exit 1
fi

# 备份旧文件
cp "$XRAY_DIR/geoip.dat" "$XRAY_DIR/geoip.dat.bak" 2>/dev/null
cp "$XRAY_DIR/geosite.dat" "$XRAY_DIR/geosite.dat.bak" 2>/dev/null

# 替换文件
mv "$TMP_DIR/geoip.dat" "$XRAY_DIR/geoip.dat"
mv "$TMP_DIR/geosite.dat" "$XRAY_DIR/geosite.dat"

# 重启 xray
/etc/init.d/xray restart

log "更新完成: geoip.dat(${GEOIP_SIZE}B) geosite.dat(${GEOSITE_SIZE}B)"

# 清理
rm -rf "$TMP_DIR"
