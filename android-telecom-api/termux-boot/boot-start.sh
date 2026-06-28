#!/data/data/com.termux/files/usr/bin/bash
# Termux Boot 自启动脚本
# 此文件会被 Termux:Boot 应用在系统启动完成后自动执行

# 等待网络和服务完全启动
sleep 10

# 执行主启动脚本
/data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/autosignin/android-telecom-api/boot-start.sh
