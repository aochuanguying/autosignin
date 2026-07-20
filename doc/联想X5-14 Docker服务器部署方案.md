# 联想 X5-14 IAL Docker 服务器完整部署方案

## 概述

- **设备**: 联想 X5-14 IAL 迷你电脑，Intel x86_64，16G RAM，1T HDD，1G 网口，内置电池（UPS 功能）
- **目标系统**: Debian 13 (Trixie) minimal
- **角色**: 家庭轻量 Docker 服务器 — 智能家居 + 反向代理 + 服务监控 + 容器管理
- **IP**: 192.168.50.10（固定 IP，网关/DNS 通过 DHCP 自动获取）
- **网段**: 192.168.50.0/24，主路由 192.168.50.1（华硕 BE86U）

**选择 Debian 13 minimal 的理由**:
- 与旁路由（倍控 G31）系统一致，统一运维
- 轻量稳定，最小化安装后仅占用约 1GB 磁盘
- Docker 官方一等支持
- 长期维护，安全更新及时

**硬件规格**:

| 项目 | 规格 |
|------|------|
| CPU | Intel x86_64 (低功耗) |
| 内存 | 16 GB DDR |
| 存储 | 1 TB HDD |
| 网口 | 1G 以太网 ×1 |
| 电池 | 内置锂电池（断电可续航，相当于 UPS）|

## 网络拓扑

```
光猫(桥接) → BE86U WAN(2.5G)
                │
                ▼
        BE86U (192.168.50.1) — 主路由
        拨号/NAT/DHCP/WiFi
        DHCP: gateway=.50.2, DNS=.50.2
                │
                ▼ LAN(2.5G)
        兮克 SKS3200-8E2X 交换机 (8×2.5G + 2×10G)
                │
    ┌───────────┼───────────────────┬──────────────┐
    │           │                   │              │
    ▼           ▼                   ▼              ▼
 倍控 G31    联想 X5-14          群晖 218+      其他设备
 .50.2       .50.3               DHCP           WiFi/有线
 2.5G口      1G口                2.5G口
 Xray+MosDNS Docker服务器        NAS
 透明代理     HA/NPM/监控
```

**流量路径说明**:
1. 所有 DHCP 客户端自动获取网关 192.168.50.2（旁路由）和 DNS 192.168.50.2（MosDNS）
2. X5_Server 同样通过 DHCP 获取网关/DNS，上网流量经旁路由透明代理
3. X5_Server 上的服务（HA、NPM 等）通过局域网 IP 192.168.50.10 直接访问，不经代理

---

## 第一部分：系统选择与镜像下载

### 1.1 下载 Debian 13 ISO

**主站（清华镜像）**:
```
https://mirrors.tuna.tsinghua.edu.cn/debian-cd/current/amd64/iso-cd/
```

下载文件：`debian-13.x.x-amd64-netinst.iso`（约 600-800MB）

**备选镜像站**:
```
https://mirrors.ustc.edu.cn/debian-cd/current/amd64/iso-cd/
https://mirrors.aliyun.com/debian-cd/current/amd64/iso-cd/
```

### 1.2 校验镜像完整性

```bash
# 下载校验文件
wget https://mirrors.tuna.tsinghua.edu.cn/debian-cd/current/amd64/iso-cd/SHA256SUMS

# 校验 ISO 文件
sha256sum -c SHA256SUMS 2>/dev/null | grep netinst
# 预期输出：debian-13.x.x-amd64-netinst.iso: OK
```

---

## 第二部分：制作启动盘与安装系统

### 2.1 制作 USB 启动盘

#### macOS（dd 命令）

```bash
# 1. 查找 USB 设备
diskutil list
# 找到 USB 设备（如 /dev/disk2）

# 2. 卸载 USB
diskutil unmountDisk /dev/disk2

# 3. 写入 ISO（注意用 rdisk 提速）
sudo dd if=debian-13.x.x-amd64-netinst.iso of=/dev/rdisk2 bs=4m status=progress

# 4. 弹出
diskutil eject /dev/disk2
```

#### Windows（Rufus）

1. 下载 Rufus：https://rufus.ie/
2. 插入 USB，打开 Rufus
3. 设备：选择你的 USB
4. 引导类型：选择下载的 Debian ISO
5. 分区类型：**GPT**（对应 EFI 启动）
6. 点击「开始」，等待写入完成

### 2.2 BIOS 设置

1. 插入 USB 到联想 X5-14
2. 开机时连按 **F2** 进入 BIOS（联想迷你电脑通常是 F2）
3. 设置：
   - **Boot Mode**: UEFI
   - **Secure Boot**: Disabled
   - **Boot Priority**: USB 设备第一
4. 保存退出（F10）

### 2.3 格式化磁盘（清除 Windows 及所有分区）

磁盘当前安装了 Windows 系统并存在多个分区（系统分区、恢复分区、数据分区等），需要在安装 Debian 前彻底清除。

#### 方式一：在 Debian 安装器中清除（推荐）

进入安装器后，在分区步骤选择 **Manual**（手动分区），然后：

1. 选中磁盘（通常显示为 `SCSI (0,0,0) (sda) - 1.0 TB` 或类似）
2. 选择 **"Yes"** 确认创建新的空分区表（这会删除磁盘上所有 Windows 分区）
3. 分区表类型选择 **gpt**（GPT 格式，适配 UEFI 启动）
4. 此时磁盘变为一整块未分配空间，按下面的分区方案创建新分区

#### 方式二：用 USB 启动盘的 Shell 手动清除（更彻底）

如果安装器无法正确识别分区，或你想确保磁盘绝对干净：

1. 从 USB 启动后，在安装器菜单选择 **"Advanced options" → "Rescue mode"** 或按 `Ctrl+Alt+F2` 进入 Shell
2. 执行以下命令彻底清除分区表：

```bash
# 确认目标磁盘（通常是 sda 或 nvme0n1）
lsblk

# 方法 A：用 sgdisk 清除 GPT 和 MBR（推荐）
sgdisk --zap-all /dev/sda

# 方法 B：用 dd 清除前后扇区（彻底）
dd if=/dev/zero of=/dev/sda bs=1M count=100     # 清除前 100MB（含 MBR/GPT 头）
dd if=/dev/zero of=/dev/sda bs=1M seek=$(($(blockdev --getsize64 /dev/sda)/1048576 - 100)) count=100  # 清除尾部备份 GPT

# 方法 C：用 wipefs 清除文件系统签名
wipefs --all /dev/sda

# 验证磁盘已清空
lsblk
fdisk -l /dev/sda
# 预期：没有任何分区，显示为空白磁盘
```

3. 输入 `exit` 返回安装器，继续正常安装流程

> **注意**: 以上操作会永久删除磁盘上所有数据（包括 Windows 系统和所有文件），请确认数据已备份或不再需要。

### 2.4 安装 Debian 13

启动后选择 "Graphical Install" 或 "Install"：

| 步骤 | 选择 |
|------|------|
| Language | English |
| Location | China |
| Keyboard | American English |
| Hostname | `x5server` |
| Domain | 留空 |
| Root password | 设置强密码 |
| User | **不创建普通用户**（跳过） |
| Partitioning | Manual（手动分区） |
| Mirror | `mirrors.tuna.tsinghua.edu.cn` |
| Software selection | **仅勾选 SSH server + standard system utilities** |
| GRUB | Yes，安装到主硬盘 |

#### 手动分区方案（1T HDD）

在已清除的磁盘上创建以下分区：

| 分区 | 大小 | 类型 | 文件系统 | 挂载点 |
|------|------|------|---------|--------|
| EFI | 512 MB | EFI System Partition | FAT32 | /boot/efi |
| swap | 16 GB | Linux swap | swap | — |
| root | 剩余全部 (~950 GB) | Linux filesystem | ext4 | / |

> 不需要单独分 /home 或 /var，Docker 数据统一放在 /opt/docker。
> 
> 如果磁盘上仍显示旧的 Windows 分区，请先按 2.3 节清除后再创建新分区。

---

## 第三部分：网络配置

使用 systemd-networkd 实现**固定 IP + DHCP 获取网关和 DNS** 的混合配置。

### 3.1 禁用其他网络管理器

```bash
# 禁用 ifupdown（Debian 默认）
cat > /etc/network/interfaces << 'EOF'
auto lo
iface lo inet loopback
EOF

# 禁用 NetworkManager（如果安装了）
systemctl disable --now NetworkManager 2>/dev/null
apt remove --purge network-manager 2>/dev/null
```

### 3.2 配置 systemd-networkd

```bash
# 启用 systemd-networkd
systemctl enable systemd-networkd

# 创建网络配置
cat > /etc/systemd/network/10-static-eth.network << 'EOF'
[Match]
Type=ether

[Network]
Address=192.168.50.10/24
DHCP=ipv4

[DHCPv4]
# 不使用 DHCP 分配的 IP（使用上面的静态 Address）
UseAddress=false
# 使用 DHCP 分配的路由（网关）
UseRoutes=true
# 使用 DHCP 分配的 DNS
UseDNS=true
EOF

# 重启网络
systemctl restart systemd-networkd
```

**配置说明**:
- `Address=192.168.50.10/24`: 固定 IP，不随 DHCP 变化
- `DHCP=ipv4`: 启用 DHCP 客户端获取额外信息
- `UseAddress=false`: 忽略 DHCP 分配的 IP 地址
- `UseRoutes=true`: 接受 DHCP 分配的默认网关（192.168.50.2，旁路由）
- `UseDNS=true`: 接受 DHCP 分配的 DNS（192.168.50.2，MosDNS）

### 3.3 配置 resolv.conf

```bash
# 启用 systemd-resolved 管理 DNS（可选，也可直接用 DHCP 获取的 DNS）
systemctl enable systemd-resolved
ln -sf /run/systemd/resolve/resolv.conf /etc/resolv.conf
```

### 3.4 网络连通性验证

```bash
# 查看 IP 地址
ip addr show
# 预期：看到 192.168.50.10/24

# ping 网关（旁路由）
ping -c 3 192.168.50.2
# 预期：延迟 < 1ms

# ping 主路由
ping -c 3 192.168.50.1
# 预期：延迟 < 1ms

# ping 外网
ping -c 3 baidu.com
# 预期：有回复

# DNS 解析测试
dig google.com
# 预期：返回 A 记录
```

---

## 第四部分：系统初始化

### 4.1 配置国内 APT 源

```bash
cat > /etc/apt/sources.list << 'EOF'
deb https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie main contrib non-free non-free-firmware
deb https://mirrors.tuna.tsinghua.edu.cn/debian/ trixie-updates main contrib non-free non-free-firmware
deb https://mirrors.tuna.tsinghua.edu.cn/debian-security trixie-security main contrib non-free non-free-firmware
EOF

apt update && apt upgrade -y
```

### 4.2 安装基础工具

```bash
apt install -y \
  curl wget vim htop \
  net-tools ca-certificates gnupg \
  jq tmux tree \
  lsb-release sudo
```

### 4.3 关闭不需要的服务

```bash
# ModemManager — 无调制解调器，服务器不需要拨号
systemctl disable --now ModemManager 2>/dev/null

# bluetooth — 无蓝牙需求，减少攻击面
systemctl disable --now bluetooth 2>/dev/null

# cups — 不连接打印机
systemctl disable --now cups 2>/dev/null

# avahi-daemon — 不需要 mDNS 服务发现（Docker 有自己的 DNS）
systemctl disable --now avahi-daemon 2>/dev/null
```

### 4.4 内核参数优化

```bash
cat > /etc/sysctl.d/99-x5server.conf << 'EOF'
# 减少 swap 使用（HDD swap 性能差，优先用内存）
vm.swappiness = 10

# inotify 参数（Home Assistant 需要监控大量文件）
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512

# Docker 容器网络转发
net.ipv4.ip_forward = 1
EOF

sysctl --system
```

### 4.5 SSH 安全配置

```bash
# 允许 root 登录（后续可改为仅 key 认证）
sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config

# 禁用空密码登录
sed -i 's/#PermitEmptyPasswords no/PermitEmptyPasswords no/' /etc/ssh/sshd_config

# 启用公钥认证
sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config

systemctl restart sshd

# 从开发机复制公钥（在 Mac 上执行）
# ssh-copy-id root@192.168.50.10
```

### 4.6 时区和 NTP 配置

```bash
# 设置时区
timedatectl set-timezone Asia/Shanghai

# 配置 NTP 使用国内服务器
mkdir -p /etc/systemd/timesyncd.conf.d
cat > /etc/systemd/timesyncd.conf.d/cn.conf << 'EOF'
[Time]
NTP=ntp.aliyun.com ntp.tencent.com
FallbackNTP=time.cloudflare.com
EOF

# 启用 NTP 同步
timedatectl set-ntp true
systemctl restart systemd-timesyncd

# 验证
timedatectl
# 预期：NTP synchronized: yes, Time zone: Asia/Shanghai
```

---

## 第五部分：Docker 安装与配置

### 5.1 安装 Docker CE

```bash
# 添加 Docker 官方 GPG 密钥
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# 添加 Docker 仓库
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装 Docker CE + Compose 插件
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 开机自启
systemctl enable docker

# 验证
docker version
# 预期：Client 和 Server 版本号均正常显示
docker compose version
# 预期：Docker Compose version v2.x.x
```

### 5.2 配置 Docker daemon

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json << 'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  },
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://docker.xuanyuan.me"
  ]
}
EOF

# 重启 Docker 使配置生效
systemctl restart docker

# 验证镜像加速
docker info | grep -A 5 "Registry Mirrors"
```

**配置说明**:
- `max-size: 50m`: 单个日志文件最大 50MB，防止 HDD 被日志撑满
- `max-file: 3`: 最多保留 3 个日志文件（轮转）
- `registry-mirrors`: 国内镜像加速器，加快镜像拉取速度

---

## 第六部分：Docker Compose 服务部署

### 6.1 创建目录结构

```bash
mkdir -p /opt/docker/{npm/data,npm/letsencrypt,homeassistant/config,uptime-kuma/data}
```

### 6.2 编写 docker-compose.yml

```bash
cat > /opt/docker/docker-compose.yml << 'EOF'
version: "3.8"

services:
  portainer:
    image: portainer/portainer-ce:latest
    container_name: portainer
    restart: unless-stopped
    ports:
      - "9000:9000"
      - "9443:9443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data

  npm:
    image: jc21/nginx-proxy-manager:latest
    container_name: nginx-proxy-manager
    restart: unless-stopped
    depends_on:
      - portainer
    ports:
      - "80:80"
      - "443:443"
      - "81:81"
      - "8081:80"
      - "8088:443"
    volumes:
      - /opt/docker/npm/data:/data
      - /opt/docker/npm/letsencrypt:/etc/letsencrypt
      - /opt/docker/npm/proxy.conf:/etc/nginx/conf.d/include/proxy.conf
      - /opt/docker/npm/force-ssl.conf:/etc/nginx/conf.d/include/force-ssl.conf

  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    container_name: homeassistant
    restart: unless-stopped
    depends_on:
      - portainer
    network_mode: host
    environment:
      - TZ=Asia/Shanghai
    volumes:
      - /opt/docker/homeassistant/config:/config

  uptime-kuma:
    image: louislam/uptime-kuma:latest
    container_name: uptime-kuma
    restart: unless-stopped
    depends_on:
      - portainer
    ports:
      - "3001:3001"
    volumes:
      - /opt/docker/uptime-kuma/data:/app/data

volumes:
  portainer_data:
EOF
```

**端口映射说明**:

| 宿主机端口 | 容器端口 | 用途 |
|-----------|---------|------|
| 80 | 80 | 局域网 HTTP 访问 |
| 443 | 443 | 局域网 HTTPS 访问 |
| 81 | 81 | NPM 管理面板 |
| 8081 | 80 | 外网 HTTP 入口（路由器转发） |
| 8088 | 443 | 外网 HTTPS 入口（路由器转发） |

> **注意**：NPM 只在容器内 80/443 端口监听，外网 8081/8088 通过 Docker 端口映射到容器内的 80/443。

**自定义 Nginx 配置文件**:

NPM 默认的 proxy.conf 和 force-ssl.conf 不适合非标准端口场景，通过 volume 挂载覆盖：

```bash
# proxy.conf — 修改 Host 头为 $http_host（含端口），HTTP 版本改为 1.1
cat > /opt/docker/npm/proxy.conf << 'EOF'
add_header       X-Served-By $host;
proxy_set_header Host $http_host;
    proxy_http_version 1.1;
    proxy_intercept_errors off;
proxy_set_header X-Forwarded-Scheme $x_forwarded_scheme;
proxy_set_header X-Forwarded-Proto  $x_forwarded_proto;
proxy_set_header X-Forwarded-For    $proxy_add_x_forwarded_for;
proxy_set_header X-Real-IP          $remote_addr;
proxy_pass       $forward_scheme://$server:$port$request_uri;
EOF

# force-ssl.conf — 修改强制 SSL 跳转目标端口为 8088
# 从容器中导出原始文件后修改最后一行：
# return 301 https://$host$request_uri → return 301 https://$host:8088$request_uri
```

### 6.3 一键启动所有服务

```bash
cd /opt/docker
docker compose up -d
```

等待所有镜像拉取完成（首次可能需要几分钟），然后验证：

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
# 预期：4 个容器全部 Up
```

---

## 第七部分：各服务配置说明

### 7.1 Portainer — Docker 管理面板

**访问地址**: http://192.168.50.10:9000

**首次配置**:
1. 浏览器打开 http://192.168.50.10:9000
2. 设置管理员用户名和密码（密码至少 12 个字符）
3. **注意**: 必须在容器首次启动后 5 分钟内完成设置，否则需要重建容器：
   ```bash
   cd /opt/docker
   docker compose down portainer
   docker volume rm docker_portainer_data
   docker compose up -d portainer
   ```
4. 登录后确认左侧导航栏显示 "local" 环境

### 7.2 Nginx Proxy Manager — 反向代理

**访问地址**: http://192.168.50.10:81

**默认登录凭据**:
- Email: `admin@example.com`
- Password: `changeme`

**首次配置**:
1. 浏览器打开 http://192.168.50.10:81
2. 使用默认凭据登录
3. **立即修改**默认邮箱和密码
4. 配置反向代理规则（如将域名代理到 Home Assistant 8123 端口等）

**端口说明**:
| 端口 | 用途 |
|------|------|
| 80 | HTTP 反向代理入口 |
| 443 | HTTPS 反向代理入口 |
| 81 | NPM 管理面板 |

### 7.3 Home Assistant — 智能家居

**访问地址**: http://192.168.50.10:8123

**首次配置**:
1. 浏览器打开 http://192.168.50.10:8123
2. 等待初始化向导加载（首次启动可能需要 1-2 分钟）
3. 创建管理员账户（用户名、密码、姓名）
4. 设置家庭位置（用于天气和自动化）
5. 选择要集成的设备（后续可在设置中添加）

**使用 host 网络模式的原因**: Home Assistant 需要发现局域网中的智能家居设备（如 MQTT、Zigbee 网关等），host 网络模式允许直接监听广播和多播流量。

### 7.4 Uptime Kuma — 服务监控

**访问地址**: http://192.168.50.10:3001

**首次配置**:
1. 浏览器打开 http://192.168.50.10:3001
2. 创建管理员账户

**建议监控目标**:

| 目标 | 地址 | 监控类型 | 间隔 |
|------|------|---------|------|
| 主路由 BE86U | 192.168.50.1 | Ping | 60s |
| 旁路由 倍控G31 | 192.168.50.2 | Ping | 60s |
| Xray 管理面板 | http://192.168.50.2:80 | HTTP | 120s |
| NAS 群晖 218+ | 群晖 IP | Ping | 60s |
| Android AutoJS API | Android IP:8080 | HTTP | 300s |
| Google 连通性 | https://www.google.com | HTTP | 300s |
| Baidu 直连 | https://www.baidu.com | HTTP | 300s |

### 7.5 故障排查

如果某个容器无法访问：

```bash
# 检查容器状态
docker ps -a

# 查看容器日志
docker logs <容器名> --tail 50

# 检查端口监听
ss -tlnp | grep <端口号>

# 重启单个容器
docker restart <容器名>

# 重建容器
cd /opt/docker
docker compose up -d --force-recreate <服务名>
```

---

## 第八部分：运维参考

### 8.1 服务管理面板汇总

| 服务 | 地址 | 用途 |
|------|------|------|
| Portainer | http://192.168.50.10:9000 | Docker 容器管理 |
| Nginx Proxy Manager | http://192.168.50.10:81 | 反向代理管理 |
| Home Assistant | http://192.168.50.10:8123 | 智能家居控制 |
| Uptime Kuma | http://192.168.50.10:3001 | 服务监控 |

### 8.2 Docker 常用命令

```bash
# 查看所有容器状态
docker ps -a

# 查看容器日志（最近 100 行）
docker logs <容器名> --tail 100

# 实时跟踪日志
docker logs -f <容器名>

# 重启容器
docker restart <容器名>

# 进入容器 Shell
docker exec -it <容器名> /bin/bash

# 查看 Docker 磁盘使用
docker system df

# 清理无用镜像和缓存
docker system prune -a
```

### 8.3 服务更新

```bash
cd /opt/docker

# 拉取最新镜像
docker compose pull

# 用新镜像重建容器（不影响数据）
docker compose up -d

# 确认所有容器正常
docker ps
```

**回滚**（如果更新后出问题）:
```bash
# 停止容器
docker compose down

# 修改 docker-compose.yml 中的镜像标签为指定版本
# 例如：image: portainer/portainer-ce:2.19.4

# 重新启动
docker compose up -d
```

### 8.4 系统资源监控

```bash
# CPU 和内存（交互式）
htop

# 磁盘使用
df -h

# 内存使用
free -m

# 监听端口
ss -tlnp

# 网络连接
ss -s
```

### 8.5 备份方案

将 /opt/docker 目录定期备份到群晖 NAS：

```bash
# 1. 确保群晖 NAS 已配置 SSH 或 rsync 服务

# 2. 配置 SSH 免密登录到 NAS（首次执行）
# ssh-copy-id admin@<NAS_IP>

# 3. 创建备份脚本
cat > /usr/local/bin/backup-docker.sh << 'EOF'
#!/bin/bash
# Docker 数据备份到群晖 NAS
LOG_TAG="Docker-Backup"
NAS_IP="<NAS_IP>"           # 替换为群晖实际 IP
NAS_PATH="/volume1/backup/x5server-docker"
NAS_USER="admin"            # 替换为 NAS 用户名

echo "[$(date)] 开始备份..."
rsync -avz --delete \
  /opt/docker/ \
  ${NAS_USER}@${NAS_IP}:${NAS_PATH}/ \
  2>&1 | logger -t $LOG_TAG

if [ $? -eq 0 ]; then
    echo "[$(date)] 备份成功" | logger -t $LOG_TAG
else
    echo "[$(date)] 备份失败" | logger -t $LOG_TAG
fi
EOF

chmod +x /usr/local/bin/backup-docker.sh

# 4. 配置每日凌晨 3 点自动备份
cat > /etc/cron.d/docker-backup << 'EOF'
0 3 * * * root /usr/local/bin/backup-docker.sh
EOF
```

### 8.6 故障排查层次

按照以下顺序逐层排查：

```
Level 1: 宿主机网络
  $ ping 192.168.50.2        → 网关可达?
  $ ping baidu.com           → 外网可达?
  $ dig google.com           → DNS 正常?

Level 2: Docker 服务状态
  $ systemctl status docker  → Docker daemon 正常?
  $ docker info              → Docker 信息完整?

Level 3: 容器运行状态
  $ docker ps -a             → 容器是否 running?
  $ docker inspect <容器>    → 配置是否正确?

Level 4: 应用日志
  $ docker logs <容器名>     → 应用内部报错?
  $ 浏览器访问各面板         → 服务响应正常?
```

---

## 完整部署检查清单

按顺序执行，每步确认通过再进行下一步：

| # | 类别 | 验证命令 | 预期结果 |
|---|------|---------|---------|
| 1 | 系统 | `uname -a` | Linux x5server 6.x ... |
| 2 | 系统 | `cat /etc/debian_version` | 13.x |
| 3 | 系统 | `hostname` | x5server |
| 4 | 时区 | `timedatectl` | Asia/Shanghai, NTP synced |
| 5 | 网络 | `ip addr show` | 192.168.50.10/24 |
| 6 | 网络 | `ping -c 1 192.168.50.2` | 通，<1ms |
| 7 | 网络 | `ping -c 1 192.168.50.1` | 通，<1ms |
| 8 | 网络 | `ping -c 1 baidu.com` | 通 |
| 9 | DNS | `dig google.com` | 返回 A 记录 |
| 10 | 内核 | `sysctl vm.swappiness` | = 10 |
| 11 | 内核 | `sysctl fs.inotify.max_user_watches` | = 524288 |
| 12 | Docker | `docker version` | Client + Server 版本号 |
| 13 | Docker | `docker compose version` | v2.x.x |
| 14 | Docker | `docker info \| grep "Registry Mirrors"` | 显示镜像源 |
| 15 | 容器 | `docker ps \| wc -l` | 5 (标题+4容器) |
| 16 | Portainer | `curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:9000` | 200 或 302 |
| 17 | NPM | `curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:81` | 200 |
| 18 | HA | `curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:8123` | 200 |
| 19 | Kuma | `curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:3001` | 200 或 302 |
| 20 | 备份 | `rsync --dry-run /opt/docker/ <NAS>:` | 无报错 |

---

## 文件结构总览

```
/opt/docker/                          # Docker 数据根目录
├── docker-compose.yml                # 统一服务编排文件
├── npm/
│   ├── data/                         # NPM 配置数据
│   └── letsencrypt/                  # SSL 证书存储
├── homeassistant/
│   └── config/                       # HA 配置和自动化规则
│       ├── configuration.yaml        # HA 主配置
│       ├── automations.yaml          # 自动化规则
│       └── ...
└── uptime-kuma/
    └── data/                         # 监控数据和配置
        └── kuma.db                   # SQLite 数据库

/etc/systemd/network/
└── 10-static-eth.network             # 网络配置（静态IP+DHCP网关）

/etc/sysctl.d/
└── 99-x5server.conf                  # 内核参数优化

/etc/docker/
└── daemon.json                       # Docker 日志和镜像加速配置

/etc/systemd/timesyncd.conf.d/
└── cn.conf                           # NTP 国内服务器配置

/etc/cron.d/
└── docker-backup                     # 定时备份任务

/usr/local/bin/
└── backup-docker.sh                  # 备份脚本
```

---

## 注意事项

1. **1G 网口带宽**：联想 X5-14 只有 1G 网口，但跑的都是轻量 Web 服务和 API，1G 绰绰有余。即使 Home Assistant + Uptime Kuma + NPM 同时工作，带宽消耗也不到 10Mbps。

2. **HDD 性能特性**：1T HDD 顺序读写尚可，但随机 IO 较弱。Docker 容器的数据库（如 Uptime Kuma 的 SQLite）在大量写入时可能有延迟。如后续需要提升性能，可考虑换装 SSD。

3. **内置电池 UPS 功能**：X5-14 自带锂电池，断电后可续航数分钟到十几分钟（取决于负载）。这相当于一个免费的 UPS：
   - 短时间断电（几秒到几分钟）：电池自动接管，服务不中断
   - 长时间断电：电池耗尽后正常关机，数据不丢失（ext4 日志文件系统 + Docker 的 restart 策略保证恢复）

4. **16G 内存规划**：
   - 系统基础占用：约 200-300 MB
   - Docker daemon：约 100 MB
   - Portainer：约 50 MB
   - NPM：约 100-200 MB
   - Home Assistant：约 200-500 MB（取决于集成数量）
   - Uptime Kuma：约 100-200 MB
   - **总计约 1-1.5 GB**，剩余 14+ GB 为系统缓存和未来扩展预留

5. **散热**：联想 X5-14 是被动散热或小风扇设计，运行 Docker 轻量服务负载很低，一般不会有散热问题。夏天建议放在通风处。

6. **备份重要性**：定期备份 `/opt/docker/` 到群晖 NAS 是关键。HDD 有机械故障风险，建议至少每日备份一次。

---

**文档更新时间**: 2025-07  
**适用系统**: Debian 13 (Trixie) + Docker CE  
**维护者**: AutoSignin Team
