# 监控大屏项目进度

**分支**：`feature/monitor-dashboard`
**代码位置**：`monitor-dashboard/`
**本地调试**：`http://localhost:3030`（需先 `cd monitor-dashboard && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 3030`）

## 架构

- **后端**：Python FastAPI，15 秒定时采集，SSE 推送
- **前端**：纯 HTML/JS/CSS，深色全屏主题，5 列布局，无框架无构建步骤
- **部署**：Docker 单容器，端口 3030，挂载 docker.sock + SSH 密钥
- **监控设备**：主路由、旁路由、NAS、X5-Server、光猫、连通性探测

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
- **采集方式**：SSH 远程登录（端口 22，用户 root）+ 本地 psutil + Docker API
- **系统**：Debian 13, Intel N305 5 核，4GB RAM
- **展示指标**：
  - CPU、内存、磁盘使用率
  - CPU 温度（读取 `/sys/class/thermal/thermal_zone0/temp`）
  - 网络流量（下行/上行速率，自动识别主网卡 eth0/enp2s0）
  - Docker 容器运行数/总数
  - 系统运行时间（/proc/uptime）
- **实测数据**：CPU 2.6%、内存 12.7%、温度 41°C、Docker 6/6
- **状态**：✅ 已完成 - 从本地 psutil 改为 SSH 远程采集，修复数据显示错误问题

### 连通性探测
- **翻墙**：GET https://www.google.com（超时 10s）
- **直连**：GET https://www.baidu.com（超时 5s）
- **公司内网**：GET http://10.19.0.1（超时 10s）
- **展示**：绿/红指示灯 + 延迟毫秒数
- **状态**：✅ 已完成

### 光猫 VSOL V2802RH (192.168.1.1) 🚧 调试中
- **采集方式**：Telnet 密码登录（端口 23，用户 admin）
- **前端展示**：5 列布局，光猫卡片
- **状态**：🚧 调试中 - Telnet 连接成功但命令执行问题待解决

### 前端 Dashboard
- 深色全屏布局（CSS Grid），5 列设备卡片（原 4 列）
- 实时时钟（顶部）
- 设备在线/离线指示灯（绿/红）
- 资源进度条（低<50% 绿、中 50-80% 黄、高>80% 红）
- 服务状态标签（active 绿、inactive 红）
- SSE 实时更新 + 断线 5 秒自动重连
- 底部状态栏（连接状态 + 最后更新时间）
- **新增**：光猫卡片（RX/TX 光功率、电压、温度、流量、设备数）

## 下一步待做

### 1. X5-Server 卡片完善 ✅ 已完成
- ✅ 添加 CPU 温度采集（thermal_zone0）
- ✅ 添加网络流量统计（自动识别主网卡 eth0/enp2s0）
- ✅ 添加系统运行时间显示（/proc/uptime）
- ✅ 前端展示优化（温度、流量、运行时间）
- ✅ 修复数据显示错误（从本地 psutil 改为 SSH 远程采集）

### 1.5 光猫 VSOL V2802RH (192.168.1.1) 🚧 调试中
- **采集方式**：Telnet 密码登录（端口 23，用户 admin）
- **设备型号**：VSOL V2802RH (GPON ONU)
- **展示指标**：
  - 光功率（RX/TX dBm）
  - 光模块电压（V）
  - 温度（°C）
  - 偏置电流（mA）
  - WAN 状态/IP 地址
  - 网络流量（下行/上行速率）
  - 连接设备数
  - 系统运行时间
- **当前状态**：🚧 调试中
  - ✅ Telnet 连接成功（admin / Wfw7539148@）
  - ✅ 登录成功，看到 `AP#` 提示符
  - ❌ 标准 Linux 命令不响应（uptime, ifconfig, cat 等都返回空）
  - ❌ diag 模式专用命令返回 "Parse error"
  - ❌ 需要确定 VSOL V2802RH 的专用命令格式
- **下一步**：
  - 尝试 SNMP v2c 采集（community: public）
  - 尝试 Web API 接口
  - 或简化为只监控在线状态和连通性

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
| X5-Server | 192.168.50.10 | 22 | root | Wfw7539148@ |

### NAS API
| 地址 | 端口 | 协议 | 用户 | 密码 |
|------|------|------|------|------|
| 192.168.50.50 | 8088 | HTTPS | wangfuwei | Wfw7539148@ |

### Telnet 凭证
| 设备 | 地址 | 端口 | 用户 | 密码 |
|------|------|------|------|------|
| 光猫 VSOL V2802RH | 192.168.1.1 | 23 | admin | Wfw7539148@ |

### 关键技术细节
- 主路由 WAN 口：eth0（2500Mbps）
- 旁路由网口：enp2s0（实际使用），enp3s0-5s0 未使用
- NAS DSM API：默认 5000/5001 已关闭，实际用 8088 HTTPS
- 群晖温度接口返回 `sys_temp` 字段（系统温度），硬盘温度在 storage API 的 `disks[].temp`
- 主路由温度：`/sys/class/thermal/thermal_zone0/temp`（毫度，除以 1000）
- 旁路由温度：同上（thermal_zone0 = 27.8°C，thermal_zone1 = 37°C）
- X5-Server 温度：`/sys/class/thermal/thermal_zone0/temp`（41°C）
- Python 3.9 兼容：不能用 `int | None` 语法，需用 `Optional[int]`
- VSOL 光猫：Telnet 登录后看到 `AP#` 提示符，标准 Linux 命令不响应，需要专用命令格式

## 文件结构

```
monitor-dashboard/
├── .env.example        # 环境变量模板
├── .env                # 实际配置（不提交）
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── DEPLOY-X5.md        # X5-Server 部署指南
├── QUICKSTART.md       # 快速启动指南
├── X5-OPTIMIZATION.md  # X5 优化总结
├── X5-OPTIMIZATION-SUMMARY.md  # 优化摘要
├── PROGRESS.md         # 本文件
├── acceptance-tests.sh # 验收测试脚本
├── deploy-to-x5.sh     # 部署脚本
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
│       ├── local.py        # X5-Server SSH 远程采集
│       ├── ont.py          # VSOL 光猫 Telnet 采集 🆕
│       └── connectivity.py # 连通性 HTTP 探测
├── tests/
│   └── test_local_collector.py  # 单元测试
└── static/
    └── index.html      # 前端 Dashboard 单页面（5 列布局）
```
