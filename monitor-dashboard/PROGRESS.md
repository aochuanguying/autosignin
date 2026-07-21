# 监控大屏项目进度

**分支**：`feature/monitor-dashboard`
**代码位置**：`monitor-dashboard/`
**本地调试**：`http://localhost:3030`（需先 `cd monitor-dashboard && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 3030`）

## 架构

- **后端**：Python FastAPI，15秒定时采集，SSE 推送
- **前端**：纯 HTML/JS/CSS，深色全屏主题，无框架无构建步骤
- **部署**：Docker 单容器，端口 3030，挂载 docker.sock + SSH 密钥

## 已完成

### 主路由 BE86U (192.168.50.1)
- **采集方式**：SSH 密码登录（端口 22，用户 wangfuwei）
- **固件**：ASUSWRT-Merlin-KoolShare (aarch64)
- **展示指标**：CPU、内存、CPU温度、公网IP、上下行流量、在线设备数、运行时间
- **实测数据**：CPU 2.5%、内存 62.4%、温度 62.8°C、公网IP 218.57.80.23、44台设备

### 旁路由 G31 (192.168.50.2)
- **采集方式**：SSH 密码登录（端口 22，用户 root）
- **系统**：Debian 13, Intel N305 5核, 4G RAM, enp2s0 网口
- **展示指标**：CPU、内存、CPU温度、Xray/MosDNS/Nginx 服务状态、连接跟踪、上下行流量、运行时间
- **实测数据**：CPU 1.8%、内存 18.4%、温度 27.8°C、三服务 active、conntrack 556/131072

### NAS DS218+ (192.168.50.50)
- **采集方式**：Synology DSM API（HTTPS 端口 8088，用户 wangfuwei）
- **系统**：DSM 7.3.1-86003、J3355 CPU、12GB RAM、2x ST4000VN 4TB
- **展示指标**：CPU、内存、磁盘使用率、系统温度、两块硬盘温度、上下行流量、卷状态、运行时间
- **实测数据**：CPU 7%、内存 19%、磁盘 9.4%(723G/7.66T)、系统40°C、硬盘30/31°C、卷 normal

### X5-Server (192.168.50.10)
- **采集方式**：本地 psutil + Docker API（/var/run/docker.sock）
- **展示指标**：
  - CPU、内存、磁盘使用率
  - CPU 温度（读取 `/sys/class/thermal/thermal_zone*`）
  - 网络流量（下行/上行速率，自动识别主网卡）
  - Docker 容器运行数/总数
  - 系统运行时间
- **状态**：代码完成，部署到 X5 后自动采集本机数据

### 连通性探测
- **翻墙**：GET https://www.google.com（超时 10s）
- **直连**：GET https://www.baidu.com（超时 5s）
- **公司内网**：GET http://10.19.0.1（超时 10s）
- **展示**：绿/红指示灯 + 延迟毫秒数

### 前端 Dashboard
- 深色全屏布局（CSS Grid），4 列设备卡片
- 实时时钟（顶部）
- 设备在线/离线指示灯（绿/红）
- 资源进度条（低<50%绿、中50-80%黄、高>80%红）
- 服务状态标签（active 绿、inactive 红）
- SSE 实时更新 + 断线 5 秒自动重连
- 底部状态栏（连接状态 + 最后更新时间）

## 下一步待做

### 1. X5-Server 卡片完善 ✅ 已完成
- ✅ 添加 CPU 温度采集（thermal_zone）
- ✅ 添加网络流量统计（自动识别主网卡）
- ✅ 添加系统运行时间显示
- ✅ 前端展示优化（温度、流量、运行时间）

### 2. 部署到 X5-Server
```bash
# 从 Mac 上传
scp -r monitor-dashboard root@192.168.50.10:/opt/docker/

# SSH 到 X5-Server
ssh root@192.168.50.10
cd /opt/docker/monitor-dashboard

# 编辑 .env（从 .env.example 复制，填入密码）
cp .env.example .env
vim .env

# 构建并启动
docker compose up -d --build

# 验证
curl http://localhost:3030/api/status
```

### 3. Kiosk 模式配置（全程 SSH 远程，无需键鼠）
```bash
# 1. 安装最小 X11 + Chromium
apt install -y xorg chromium openbox xdotool scrot

# 2. 配置 getty 自动登录
mkdir -p /etc/systemd/system/getty@tty1.service.d
cat > /etc/systemd/system/getty@tty1.service.d/override.conf << 'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin root --noclear %I $TERM
EOF
systemctl daemon-reload

# 3. .bash_profile 自动 startx
echo '[[ $(tty) == /dev/tty1 ]] && startx' >> ~/.bash_profile

# 4. ~/.xinitrc
cat > ~/.xinitrc << 'EOF'
xset s off
xset -dpms
xset s noblank
chromium --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:3030 &
exec openbox
EOF

# 5. 重启验证
reboot
```

### 4. SSH 远程管理显示器
```bash
# 刷新页面
DISPLAY=:0 xdotool key F5

# 息屏/亮屏
DISPLAY=:0 xset dpms force off
DISPLAY=:0 xset dpms force on

# 截屏检查
DISPLAY=:0 scrot /tmp/screen.png
scp root@192.168.50.10:/tmp/screen.png ~/Desktop/
```

### 5. 验收测试
- [ ] 所有设备在线时绿色指示灯 + 数值正确
- [ ] 拔掉某设备网线 → 对应卡片变红，其他不受影响
- [ ] 停止 xray 服务 → 旁路由 Xray 标签变红
- [ ] SSE 断线后 5 秒内自动重连
- [ ] 容器重启后自动恢复
- [ ] 断电来电后 Kiosk 自动恢复显示

## 配置信息

### SSH 凭证
| 设备 | 地址 | 端口 | 用户 | 密码 |
|------|------|------|------|------|
| 主路由 | 192.168.50.1 | 22 | wangfuwei | Wfw7539148@ |
| 旁路由 | 192.168.50.2 | 22 | root | Wfw7539148@ |

### NAS API
| 地址 | 端口 | 协议 | 用户 | 密码 |
|------|------|------|------|------|
| 192.168.50.50 | 8088 | HTTPS | wangfuwei | Wfw7539148@ |

### 关键技术细节
- 主路由 WAN 口：eth0（2500Mbps）
- 旁路由网口：enp2s0（实际使用），enp3s0-5s0 未使用
- NAS DSM API：默认 5000/5001 已关闭，实际用 8088 HTTPS
- 群晖温度接口返回 `sys_temp` 字段（系统温度），硬盘温度在 storage API 的 `disks[].temp`
- 主路由温度：`/sys/class/thermal/thermal_zone0/temp`（毫度，除以1000）
- 旁路由温度：同上（thermal_zone0 = 27.8°C，thermal_zone1 = 37°C）
- Python 3.9 兼容：不能用 `int | None` 语法，需用 `Optional[int]`

## 文件结构

```
monitor-dashboard/
├── .env.example        # 环境变量模板
├── .env                # 实际配置（不提交）
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── DEPLOY.md           # 部署说明
├── PROGRESS.md         # 本文件
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI 入口 + lifespan
│   ├── config.py       # 环境变量配置
│   ├── collector.py    # 采集调度器 + SSE 订阅管理
│   ├── routes.py       # /health, /api/status, /api/events
│   └── collectors/
│       ├── __init__.py
│       ├── router.py       # 主路由 SSH 采集
│       ├── gateway.py      # 旁路由 SSH 采集
│       ├── nas.py          # NAS DSM API 采集
│       ├── local.py        # X5-Server 本地采集
│       └── connectivity.py # 连通性 HTTP 探测
└── static/
    └── index.html      # 前端 Dashboard 单页面
```
