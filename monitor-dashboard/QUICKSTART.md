# 监控大屏项目 - 快速开始指南

## 项目状态

**代码实现：✅ 100% 完成**  
**待执行：部署到 X5-Server 并配置 Kiosk 模式**

---

## 已完成的工作

### ✅ 代码实现（任务 1-22）
- **后端服务**：FastAPI + Python 3.9
  - 定时数据采集（15 秒间隔）
  - SSE 实时推送
  - REST API 端点
  - 5 个数据采集器（主路由、旁路由、NAS、X5-Server、连通性）

- **前端 Dashboard**：纯 HTML/JS/CSS
  - 深色全屏主题
  - 4 列设备卡片布局
  - 实时时钟
  - 资源使用率进度条
  - 服务状态指示灯
  - SSE 客户端 + 自动重连

- **Docker 配置**
  - Dockerfile
  - docker-compose.yml
  - 环境变量模板

### ✅ 部署文档（任务 23-25）
- [DEPLOY.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/DEPLOY.md) - 基础部署说明
- [DEPLOY-X5.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/DEPLOY-X5.md) - X5-Server 完整部署指南
- [PROGRESS.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/PROGRESS.md) - 项目进度和技术细节

### ✅ 自动化脚本
- [deploy-to-x5.sh](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/deploy-to-x5.sh) - 一键部署脚本
- [acceptance-tests.sh](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/acceptance-tests.sh) - 验收测试脚本

---

## 下一步操作

### 方式一：自动化部署（推荐）

在 Mac 上执行：

```bash
cd /Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard
./deploy-to-x5.sh
```

**脚本会自动完成：**
1. 上传代码到 X5-Server
2. 配置环境变量
3. 配置 SSH 免密登录
4. 构建并启动 Docker 容器
5. 安装 Kiosk 依赖（X11 + Chromium）
6. 配置自动登录和 Kiosk 模式
7. 可选：测试显示和重启验证

### 方式二：手动部署

按照 [DEPLOY-X5.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/DEPLOY-X5.md) 逐步执行：

**阶段 1：部署 Docker 容器**（任务 5.4）
```bash
# 1. 上传代码
scp -r monitor-dashboard root@192.168.50.10:/opt/docker/

# 2. SSH 登录
ssh root@192.168.50.10

# 3. 配置环境变量
cd /opt/docker/monitor-dashboard
cp .env.example .env
vim .env  # 填入密码

# 4. 构建启动
docker compose up -d --build

# 5. 验证
curl http://localhost:3030/health
```

**阶段 2：配置 Kiosk 模式**（任务 6.1-6.7）
```bash
# 1. 安装依赖
apt install -y xorg chromium openbox xdotool scrot unclutter

# 2. 配置 getty 自动登录
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF
systemctl daemon-reload

# 3. 配置 .bash_profile
echo '[[ $(tty) == /dev/tty1 ]] && startx' >> ~/.bash_profile

# 4. 编写 ~/.xinitrc
cat > ~/.xinitrc << 'EOF'
#!/bin/sh
xset s off
xset -dpms
xset s noblank
unclutter -idle 3 -root &
chromium --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:3030 &
exec openbox
EOF
chmod +x ~/.xinitrc

# 5. 重启验证
reboot
```

**阶段 3：验收测试**（任务 7.1-7.5）
```bash
# SSH 到 X5-Server 执行测试
ssh root@192.168.50.10
cd /opt/docker/monitor-dashboard
bash acceptance-tests.sh
```

---

## 验证清单

部署完成后，按以下顺序验证：

### ✅ 基础验证
- [ ] 容器运行正常：`docker compose ps`
- [ ] API 健康检查：`curl http://localhost:3030/health`
- [ ] API 返回数据：`curl http://localhost:3030/api/status`
- [ ] 浏览器访问：http://192.168.50.10:3030

### ✅ Kiosk 验证
- [ ] 显示器自动显示 Dashboard
- [ ] 全屏无浏览器边框
- [ ] 时钟实时更新
- [ ] 设备数据每 15 秒刷新
- [ ] 屏幕不会自动关闭（DPMS 已禁用）

### ✅ 功能验证
- [ ] 所有设备在线时显示绿色指示灯
- [ ] 拔掉某设备网线 → 对应卡片变红
- [ ] 停止 xray 服务 → 翻墙指示灯变红
- [ ] SSE 断线后 5 秒内重连
- [ ] 容器重启后自动恢复

### ✅ 远程管理验证
- [ ] SSH 刷新页面：`DISPLAY=:0 xdotool key F5`
- [ ] SSH 息屏：`DISPLAY=:0 xset dpms force off`
- [ ] SSH 亮屏：`DISPLAY=:0 xset dpms force on`
- [ ] SSH 截屏：`DISPLAY=:0 scrot /tmp/screen.png`

---

## 常用命令

### 查看服务状态
```bash
# SSH 到 X5-Server
ssh root@192.168.50.10

# 查看容器状态
docker compose ps

# 查看日志
docker compose logs -f monitor-dashboard

# 查看实时数据
watch -n 2 'curl -s http://localhost:3030/api/status | jq .'
```

### 重启服务
```bash
# 重启容器
docker compose restart monitor-dashboard

# 重启 Chromium
DISPLAY=:0 pkill chromium
sleep 2
DISPLAY=:0 chromium --kiosk http://localhost:3030 &

# 重启 X11（会重新触发自动登录）
pkill openbox
```

### 远程管理
```bash
# 从 Mac SSH 执行
ssh root@192.168.50.10 "DISPLAY=:0 xdotool key F5"  # 刷新
ssh root@192.168.50.10 "DISPLAY=:0 xset dpms force off"  # 息屏
ssh root@192.168.50.10 "DISPLAY=:0 xset dpms force on"  # 亮屏
ssh root@192.168.50.10 "DISPLAY=:0 scrot /tmp/screen.png"  # 截屏
scp root@192.168.50.10:/tmp/screen.png ~/Desktop/  # 下载截屏
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

## 故障排查

### 问题 1：容器无法启动
```bash
# 查看日志
docker compose logs monitor-dashboard

# 检查端口占用
netstat -tlnp | grep 3030

# 检查 .env 文件
cat /opt/docker/monitor-dashboard/.env
```

### 问题 2：Dashboard 显示空白
```bash
# 检查后端 API
curl http://localhost:3030/api/status

# 浏览器开发者工具
# F12 → Console 查看错误
# F12 → Network 查看 /api/events 连接
```

### 问题 3：Chromium 无法启动
```bash
# 查看 X11 日志
cat /var/log/Xorg.0.log | grep -i error

# 手动测试
DISPLAY=:0 chromium --version

# 检查 DISPLAY 变量
echo $DISPLAY  # 应该是 :0
```

### 问题 4：屏幕自动关闭
```bash
# 检查 DPMS 状态
DISPLAY=:0 xset q | grep -A 5 "DPMS"

# 重新禁用 DPMS
DISPLAY=:0 xset s off
DISPLAY=:0 xset -dpms
DISPLAY=:0 xset s noblank

# 永久生效：编辑 ~/.xinitrc
```

### 问题 5：SSH 采集失败
```bash
# 测试 SSH 连接
ssh -v root@192.168.50.2 "uptime"
ssh -v wangfuwei@192.168.50.1 "uptime"

# 查看后端日志
docker compose logs monitor-dashboard | grep -i ssh
```

---

## 项目文件结构

```
monitor-dashboard/
├── app/                        # 后端 Python 代码
│   ├── collectors/             # 数据采集器
│   │   ├── router.py           # 主路由采集器
│   │   ├── gateway.py          # 旁路由采集器
│   │   ├── nas.py              # NAS 采集器
│   │   ├── local.py            # X5-Server 本地采集器
│   │   └── connectivity.py     # 连通性探测器
│   ├── collector.py            # 采集调度器
│   ├── config.py               # 配置管理
│   ├── main.py                 # FastAPI 入口
│   └── routes.py               # API 路由
├── static/
│   └── index.html              # 前端 Dashboard 单页面
├── .env.example                # 环境变量模板
├── .env                        # 实际配置（不提交）
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── DEPLOY.md                   # 基础部署说明
├── DEPLOY-X5.md               # X5-Server 完整部署指南
├── PROGRESS.md                 # 项目进度和技术细节
├── QUICKSTART.md               # 本文件
├── deploy-to-x5.sh             # 一键部署脚本
└── acceptance-tests.sh         # 验收测试脚本
```

---

## 技术栈

- **后端**：Python 3.9 + FastAPI + uvicorn
- **前端**：HTML5 + Vanilla JS + CSS Grid（无框架）
- **部署**：Docker + docker-compose
- **实时通信**：Server-Sent Events (SSE)
- **数据采集**：
  - SSH：asyncssh（主路由、旁路由）
  - HTTP：httpx（NAS DSM API、连通性探测）
  - 本地：psutil + Docker API（X5-Server）

---

## 联系与支持

如有问题，请查阅：
1. [DEPLOY-X5.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/DEPLOY-X5.md) - 详细部署步骤
2. [PROGRESS.md](file:///Users/mac/Documents/workspace/krio/autosignin/monitor-dashboard/PROGRESS.md) - 技术细节和配置信息
3. [tasks.md](file:///Users/mac/Documents/workspace/krio/autosignin/openspec/changes/server-monitor-dashboard/tasks.md) - 任务清单

---

**文档版本**：1.0  
**最后更新**：2026-07-21  
**项目状态**：代码完成，待部署
