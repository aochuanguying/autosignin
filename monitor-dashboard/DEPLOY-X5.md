# X5-Server 部署与 Kiosk 配置完整指南

本文档指导你在 X5-Server (192.168.50.10) 上部署监控大屏并配置显示器 Kiosk 模式。

**前提条件：**
- X5-Server 已运行 Docker 和 docker-compose
- X5-Server 的 SSH 免密登录已配置到旁路由 (192.168.50.2) 和主路由 (192.168.50.1)
- 显示器已通过 HDMI 连接到 X5-Server

---

## 第一阶段：部署 Docker 容器（任务 5.4）

### 步骤 1：上传代码到 X5-Server

在 Mac 上执行：

```bash
cd /Users/mac/Documents/workspace/krio/autosignin
scp -r monitor-dashboard root@192.168.50.10:/opt/docker/
```

### 步骤 2：SSH 登录 X5-Server

```bash
ssh root@192.168.50.10
```

### 步骤 3：配置环境变量

```bash
cd /opt/docker/monitor-dashboard
cp .env.example .env
```

编辑 `.env` 文件，填入实际配置：

```bash
vim .env
```

**配置内容：**

```env
# 采集间隔（秒）
POLL_INTERVAL=15

# 主路由 BE86U
ROUTER_IP=192.168.50.1
ROUTER_SSH_PORT=22
ROUTER_SSH_USER=wangfuwei
ROUTER_SSH_PASSWORD=Wfw7539148@

# 旁路由 G31
GATEWAY_IP=192.168.50.2
GATEWAY_SSH_PORT=22
GATEWAY_SSH_USER=root
GATEWAY_SSH_PASSWORD=Wfw7539148@

# NAS DS218+
NAS_IP=192.168.50.50
NAS_API_PORT=8088
NAS_API_PROTO=https
NAS_API_USER=wangfuwei
NAS_API_PASSWORD=Wfw7539148@

# 连通性探测
PROBE_GOOGLE_URL=https://www.google.com
PROBE_BAIDU_URL=https://www.baidu.com
PROBE_OFFICE_URL=http://10.19.0.1

# 内网探测 URL（可选，用于测试公司内网可达性）
OFFICE_NETWORK_URL=http://10.19.0.1
```

### 步骤 4：验证 SSH 密钥

确保可以从 X5-Server SSH 到旁路由和主路由：

```bash
# 测试旁路由
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 root@192.168.50.2 "uptime"

# 测试主路由（如果开启了 SSH）
ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 wangfuwei@192.168.50.1 "uptime"
```

如果提示需要密码，说明还未配置免密登录。使用以下命令配置：

```bash
# 配置旁路由免密
ssh-copy-id -o StrictHostKeyChecking=no root@192.168.50.2

# 配置主路由免密（如果支持 SSH）
ssh-copy-id -o StrictHostKeyChecking=no wangfuwei@192.168.50.1
```

### 步骤 5：构建并启动容器

```bash
cd /opt/docker/monitor-dashboard
docker compose up -d --build
```

### 步骤 6：验证服务

```bash
# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f

# 测试 API
curl http://localhost:3030/health
curl http://localhost:3030/api/status

# 在浏览器访问（从 Mac）
# http://192.168.50.10:3030
```

**预期结果：**
- 容器状态为 `Up`
- `/health` 返回 `{"status": "ok"}`
- `/api/status` 返回包含所有设备状态的 JSON

---

## 第二阶段：配置 Kiosk 模式（任务 6.1-6.7）

**重要：** 以下步骤按顺序执行，每步完成后验证再执行下一步。

### 步骤 6.1：安装最小 X11 + Chromium

```bash
apt update
apt install -y xorg chromium openbox xdotool scrot
```

**验证安装：**

```bash
which X
which chromium
which openbox
# 应该输出对应的路径
```

### 步骤 6.2：配置 getty 自动登录

```bash
mkdir -p /etc/systemd/system/getty@tty1.service.d

cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF

systemctl daemon-reload
```

**验证配置：**

```bash
cat /etc/systemd/system/getty@tty1.service.d/override.conf
# 确认内容正确
```

### 步骤 6.3：配置 .bash_profile 自动启动 X

```bash
cat >> ~/.bash_profile << 'EOF'
# 自动启动 X11 在 tty1
if [[ $(tty) == /dev/tty1 ]]; then
    startx
fi
EOF
```

**验证配置：**

```bash
cat ~/.bash_profile
# 确认包含自动 startx 的逻辑
```

### 步骤 6.4-6.5：编写 ~/.xinitrc（禁用屏保 + 启动 Chromium）

```bash
cat > ~/.xinitrc << 'EOF'
#!/bin/sh

# 禁用屏保和 DPMS
xset s off
xset -dpms
xset s noblank

# 设置光标自动隐藏（可选）
unclutter -idle 3 -root &

# 启动 Chromium Kiosk 模式
chromium \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-check-for-default-browser \
    --disable-background-networking \
    --disable-default-apps \
    --disable-extensions \
    --disable-sync \
    --disable-translate \
    --hide-scrollbars \
    --window-size=1920,1080 \
    http://localhost:3030 &

# 启动窗口管理器
exec openbox
EOF

chmod +x ~/.xinitrc
```

**验证配置：**

```bash
cat ~/.xinitrc
# 确认包含 xset 禁用 DPMS 和 chromium 启动命令
```

### 步骤 6.6：测试显示（不重启）

先手动测试 X11 和 Chromium 是否正常工作：

```bash
# 启动 X
startx

# 等待 10 秒，应该看到 Chromium 全屏打开 http://localhost:3030
# 按 Ctrl+Alt+F2 切换到 tty2
# 登录 root
# 测试远程操控
DISPLAY=:0 xdotool key F5  # 刷新页面
DISPLAY=:0 xset dpms force off  # 息屏
DISPLAY=:0 xset dpms force on   # 亮屏
DISPLAY=:0 scrot /tmp/test.png  # 截屏

# 退出 X（如果需要）
pkill chromium
pkill openbox
```

**SSH 远程管理测试：**

在 Mac 上执行：

```bash
# SSH 登录 X5-Server
ssh root@192.168.50.10

# 刷新页面
DISPLAY=:0 xdotool key F5

# 截屏并下载检查
DISPLAY=:0 scrot /tmp/screen.png
scp root@192.168.50.10:/tmp/screen.png ~/Desktop/

# 息屏/亮屏
DISPLAY=:0 xset dpms force off
DISPLAY=:0 xset dpms force on
```

### 步骤 6.7：重启验证自动恢复

```bash
# 重启 X5-Server
reboot

# 等待 2-3 分钟
# 显示器应该自动显示 Dashboard
# 从 Mac SSH 验证
ssh root@192.168.50.10

# 检查 Chromium 进程
ps aux | grep chromium

# 截屏确认
DISPLAY=:0 scrot /tmp/boot_test.png
scp root@192.168.50.10:/tmp/boot_test.png ~/Desktop/
```

---

## 第三阶段：验收测试（任务 7.1-7.5）

### 测试 7.1：所有设备在线时 Dashboard 正常

**操作：**
1. 确保所有设备网络连接正常
2. 访问 http://192.168.50.10:3030
3. 检查 Dashboard

**预期：**
- 所有设备卡片显示绿色指示灯
- CPU/内存/磁盘数值正确显示
- 连通性面板三个指示灯都是绿色
- 延迟数值合理（Google <300ms, 百度 <50ms, 内网 <10ms）

### 测试 7.2：单设备离线测试

**操作：**
1. 拔掉 NAS 的网线（或关闭旁路由）
2. 等待 30 秒（2 个采集周期）
3. 观察 Dashboard

**预期：**
- 对应设备卡片变红
- 其他设备卡片保持绿色
- 不影响其他设备数据采集

### 测试 7.3：翻墙中断测试

**操作：**
1. SSH 到旁路由，停止 xray 服务
   ```bash
   ssh root@192.168.50.2
   systemctl stop xray
   ```
2. 等待 30 秒
3. 观察 Dashboard 连通性面板

**预期：**
- "翻墙"指示灯变红
- 内网/直连保持绿色
- Google 探测延迟显示为超时

恢复测试：
```bash
ssh root@192.168.50.2
systemctl start xray
```

### 测试 7.4：SSE 断线重连测试

**操作：**
1. 打开浏览器开发者工具（F12）→ Network 标签
2. 找到 `/api/events` 连接
3. 右键 → "Close connection" 或重启后端容器
4. 观察 Console 日志

**预期：**
- 5 秒内自动重连
- Console 显示 "SSE reconnected"
- Dashboard 数据继续实时更新

### 测试 7.5：容器重启测试

**操作：**

```bash
# 重启容器
docker compose restart monitor-dashboard

# 等待 30 秒
# 观察 Dashboard
```

**预期：**
- Dashboard 自动恢复显示
- 数据重新开始更新
- Kiosk 模式不受影响

---

## 故障排查

### 问题：Chromium 无法启动

**检查日志：**

```bash
# 查看 X11 日志
cat /var/log/Xorg.0.log | grep -i error

# 手动测试启动
DISPLAY=:0 chromium --version
```

**解决方案：**
- 确保安装了 chromium：`apt install chromium`
- 检查 DISPLAY 环境变量：`echo $DISPLAY` 应该是 `:0`
- 检查权限：确保以 root 用户运行

### 问题：Dashboard 显示空白

**检查后端：**

```bash
docker compose logs monitor-dashboard
curl http://localhost:3030/api/status
```

**检查前端：**
- 打开浏览器开发者工具 → Console
- 查看是否有 JavaScript 错误
- 检查 Network 标签 `/api/events` 连接状态

### 问题：SSH 采集失败

**检查 SSH 连接：**

```bash
# 测试旁路由
ssh -v -o ConnectTimeout=5 root@192.168.50.2 "uptime"

# 测试主路由
ssh -v -o ConnectTimeout=5 wangfuwei@192.168.50.1 "uptime"
```

**查看后端日志：**

```bash
docker compose logs monitor-dashboard | grep -i "ssh\|error"
```

### 问题：DPMS 未禁用，屏幕自动关闭

**检查 xset 状态：**

```bash
DISPLAY=:0 xset q | grep -A 5 "DPMS"
```

**应该显示：**
```
DPMS is Disabled
Standby: 0   Suspend: 0   Off: 0
```

**如果未禁用，重新执行：**

```bash
DISPLAY=:0 xset s off
DISPLAY=:0 xset -dpms
DISPLAY=:0 xset s noblank
```

**永久生效：** 确保 `~/.xinitrc` 包含这三行。

---

## 常用维护命令

### 查看 Dashboard 状态

```bash
# 从 Mac SSH 执行
ssh root@192.168.50.10 "docker compose ps"
ssh root@192.168.50.10 "curl -s http://localhost:3030/health"
```

### 刷新页面

```bash
ssh root@192.168.50.10 "DISPLAY=:0 xdotool key F5"
```

### 息屏/亮屏（节能）

```bash
# 息屏
ssh root@192.168.50.10 "DISPLAY=:0 xset dpms force off"

# 亮屏
ssh root@192.168.50.10 "DISPLAY=:0 xset dpms force on"
```

### 截屏检查

```bash
ssh root@192.168.50.10 "DISPLAY=:0 scrot /tmp/screen.png"
scp root@192.168.50.10:/tmp/screen.png ~/Desktop/
```

### 重启服务

```bash
# 重启容器
ssh root@192.168.50.10 "cd /opt/docker/monitor-dashboard && docker compose restart"

# 重启 Chromium（不重启 X）
ssh root@192.168.50.10 "DISPLAY=:0 pkill chromium && sleep 2 && DISPLAY=:0 chromium --kiosk http://localhost:3030 &"

# 完整重启 X11
ssh root@192.168.50.10 "pkill openbox && pkill chromium"
# X 会自动重启（由于 startx 在后台）
```

### 更新代码

```bash
# 从 Mac 上传
cd /Users/mac/Documents/workspace/krio/autosignin
scp -r monitor-dashboard root@192.168.50.10:/opt/docker/

# SSH 到 X5-Server 重启
ssh root@192.168.50.10
cd /opt/docker/monitor-dashboard
docker compose up -d --build
```

---

## 完成检查清单

- [ ] 任务 26：容器已启动，http://192.168.50.10:3030 可访问
- [ ] 任务 27：X11 + Chromium 已安装
- [ ] 任务 28：getty 自动登录已配置
- [ ] 任务 29：.bash_profile 自动 startx 已配置
- [ ] 任务 30：~/.xinitrc 已配置（禁用 DPMS + Chromium kiosk）
- [ ] 任务 31：DPMS 已禁用（`xset q` 验证）
- [ ] 任务 32：SSH 远程管理可用（xdotool/xset/scrot）
- [ ] 任务 33：重启后自动恢复显示
- [ ] 任务 34：所有设备在线时 Dashboard 正常
- [ ] 任务 35：单设备离线不影响其他设备
- [ ] 任务 36：翻墙中断时连通性面板标红
- [ ] 任务 37：SSE 断线 5 秒内重连
- [ ] 任务 38：容器重启后服务恢复

---

**文档版本：** 1.0  
**最后更新：** 2026-07-21  
**维护者：** 系统管理员
