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
| VLESS | 16825 | 16825 | 192.168.50.2 | BOTH |
| Drive | 6690 | 6690 | 192.168.50.50 | BOTH |

> 注：SSH 端口 120 已删除（不再暴露到公网）

## NPM 反向代理规则 (X5_Server)

NPM 管理面板：http://192.168.50.10:81

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

### NPM 自定义配置说明

NPM 默认的 proxy.conf 不适合非标准端口反代场景，已通过 volume 挂载覆盖：

- `/opt/docker/npm/proxy.conf` → 修改 Host 头为 `$http_host`（含端口），HTTP 版本改为 1.1
- `/opt/docker/npm/force-ssl.conf` → 修改强制 SSL 跳转目标为 `https://$host:8088`

### Docker Compose 端口映射逻辑

```
外网 8081 → Docker 8081:80 → NPM 容器内 80 端口 (HTTP)
外网 8088 → Docker 8088:443 → NPM 容器内 443 端口 (HTTPS)
```

NPM 面板只监听 80/443，通过 Docker 端口映射实现外部非标准端口访问。

## 外部访问 URL 映射表

| 外部访问 URL | 内网目标 | 服务 |
|-------------|---------|------|
| https://hxfssc.com:8088 | 192.168.50.50:8088 | 群晖 DSM |
| https://router.hxfssc.com:8088 | 192.168.50.1:8443 | 路由器管理 |
| https://ha.hxfssc.com:8088 | 192.168.50.10:8123 | Home Assistant |
| https://bt.hxfssc.com:8088 | 192.168.50.50:9085 | qBittorrent |
| https://yqad.hxfssc.com:8088 | 192.168.50.50:3000 | 一汽奥迪 |
| vless://公网IP:16825 | 192.168.50.2:16825 | VLESS 代理 |

## 旁路由 Xray 直连规则

旁路由 Xray 路由配置中，以下域名设为直连（不经代理），避免 Docker 容器内 TLS 握手被透明代理干扰：

- `domain:letsencrypt.org` — Let's Encrypt 证书申请
- `domain:cloudflare.com` — Cloudflare IP 列表获取

## 相关文档

- 旁路由详细部署：./doc/倍控G31-N305旁路由部署方案.md
- X5_Server 详细部署：./doc/联想X5-14 Docker服务器部署方案.md
