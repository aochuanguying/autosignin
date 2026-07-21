# 家庭网络架构文档

## 网络拓扑

```
光猫(桥接) → BE86U WAN(2.5G)
                │
                ▼
        BE86U (192.168.50.1) — 主路由
        拨号/NAT/DHCP/WiFi/端口转发
        DHCP: gateway=.50.2, DNS=.50.2
                │
                ▼ LAN(2.5G)
        兮克 SKS3200-8E2X 交换机 (8×2.5G + 2×10G)
                │
    ┌───────────┼───────────────────┬──────────────┐
    │           │                   │              │
    ▼           ▼                   ▼              ▼
 倍控 G31    联想 X5-14          群晖 218+      其他设备
 .50.2       .50.10              .50.50          WiFi/有线
 2.5G口      1G口                2.5G口
 Xray+MosDNS NPM/HA/监控         NAS/应用
 透明代理+VLESS 反向代理
```

## 设备职责划分

| 设备 | IP | 核心职责 |
|------|-----|---------|
| BE86U 主路由 | 192.168.50.1 | PPPoE 拨号、NAT、DHCP、WiFi、端口转发 |
| 倍控 G31 旁路由 | 192.168.50.2 | 透明代理(Xray TPROXY)、DNS 分流(MosDNS)、VLESS 入站服务 |
| 联想 X5_Server | 192.168.50.10 | 反向代理(NPM)、Home Assistant、服务监控(Uptime Kuma)、容器管理(Portainer) |
| 群晖 NAS 218+ | 192.168.50.50 | NAS 存储、Web Station、qBittorrent、一汽奥迪服务、Synology Drive |

## 主路由器端口转发规则

| 服务名称 | 外部端口 | 内部端口 | 目标 IP | 协议 |
|---------|---------|---------|---------|------|
| HTTP Server | 8081 | 8081 | 192.168.50.10 | BOTH |
| HTTP Server | 8088 | 8088 | 192.168.50.10 | BOTH |
| VLESS | 16824 | 16824 | 192.168.50.50 | BOTH |
| VLESS | 16825 | 16825 | 192.168.50.2 | BOTH |
| Drive | 6690 | 6690 | 192.168.50.50 | BOTH |

> 注：SSH 端口 120 已删除（不再暴露到公网）
> 16824 映射到群晖 NAS（VLESS 入站，访问家庭内网文件）
> 16825 映射到旁路由（VLESS 入站，翻墙+内网访问）

## NPM 反向代理 (X5_Server)

NPM 管理面板：http://192.168.50.10:81

### NPM 网络架构

NPM 使用 `network_mode: host` 运行，直接监听宿主机 80/443/81 端口。

**端口转发回包问题**：X5_Server 默认网关是旁路由（192.168.50.2），端口转发的回包经过旁路由时会被 TPROXY 劫持导致丢包。

**解决方案**（配置在 X5_Server 本机，不污染旁路由）：
1. iptables PREROUTING：入站 8088 重定向到本机 443，8081 重定向到 80（必须，不能省）
2. 策略路由：源端口 443/80 的回包走 table 100（网关 192.168.50.1 主路由直出）

> 注：不能取消 iptables 重定向改为路由器直接转发到 443/80，因为策略路由 `sport 443` 会影响入站包的路由判断。
> 入站包目标端口必须是 8088（不被策略路由匹配），经 REDIRECT 后变成 443 进入 NPM。

已通过 systemd 服务 `npm-routing.service` 持久化：
```bash
systemctl status npm-routing   # 查看状态
```

**网关容灾**：当旁路由不可用（网关回退到 192.168.50.1）时，NPM 反向代理功能不受影响，仅 X5_Server 自身失去翻墙能力。

### 代理规则

| 域名 | 外部端口 | 协议 | 上游地址 | 说明 |
|------|---------|------|---------|------|
| hxfssc.com | 8088 | HTTPS | https://192.168.50.50:8088 | 群晖 DSM |
| router.hxfssc.com | 8088 | HTTPS | https://192.168.50.1:8443 | 路由器管理 |
| ha.hxfssc.com | 8088 | HTTPS | http://192.168.50.10:8123 | Home Assistant |
| bt.hxfssc.com | 8088 | HTTPS | http://192.168.50.50:9085 | qBittorrent |
| yqad.hxfssc.com | 8088 | HTTPS | http://192.168.50.50:3000 | 一汽奥迪 |

### SSL 证书

- 证书域名：`*.hxfssc.com`（通配符）
- 签发方式：Let's Encrypt DNS Challenge (阿里云 DNS)
- NPM 自动续期，无需额外 acme 容器

### NPM 自定义配置

通过 volume 挂载覆盖 NPM 默认配置：

- `/opt/docker/npm/proxy.conf` → Host 头改为 `$http_host`（含端口）、关闭 proxy_intercept_errors
- `/opt/docker/npm/force-ssl.conf` → 强制 SSL 跳转目标改为 `https://$host:8088`

## 外部访问 URL 映射表

| 外部访问 URL | 内网目标 | 服务 |
|-------------|---------|------|
| https://hxfssc.com:8088 | 192.168.50.50:8088 | 群晖 DSM |
| https://router.hxfssc.com:8088 | 192.168.50.1:8443 | 路由器管理 |
| https://ha.hxfssc.com:8088 | 192.168.50.10:8123 | Home Assistant |
| https://bt.hxfssc.com:8088 | 192.168.50.50:9085 | qBittorrent |
| https://yqad.hxfssc.com:8088 | 192.168.50.50:3000 | 一汽奥迪 |
| vless://公网IP:16824 | 192.168.50.50:16824 | NAS VLESS（家庭内网文件访问） |
| vless://公网IP:16825 | 192.168.50.2:16825 | 旁路由 VLESS（翻墙+内网） |

## 旁路由 Xray 直连规则

旁路由 Xray 路由配置中，以下域名设为直连（不经代理），避免 Docker 容器内 TLS 握手被透明代理干扰：

- `domain:letsencrypt.org` — Let's Encrypt 证书申请
- `domain:cloudflare.com` — Cloudflare IP 列表获取

## 相关文档

- 旁路由详细部署：./doc/倍控G31-N305旁路由部署方案.md
- X5_Server 详细部署：./doc/联想X5-14 Docker服务器部署方案.md
