# 倍控 G31 旁路由运行配置

当前在旁路由(192.168.50.2)上实际运行的配置文件备份。

## 架构

```
客户端 DNS(53) → MosDNS(53) — 独立 DNS 分流/防污染/去广告
                              ├── hisense.com → hosts 返回 10.19.255.253 (假IP)
                              ├── 国内域名 → 223.5.5.5 / 119.29.29.29
                              ├── 国外域名 → DoT 8.8.8.8 / 1.1.1.1
                              └── 广告域名 → NXDOMAIN

客户端 流量 → nftables TPROXY → Xray tproxy-in(12345) → proxy/office/direct/block
                                                          ↓
                                              iptables MASQUERADE (mark 255)
                                              确保回包经过旁路由
```

## 关键设计

1. **MosDNS 独立处理 DNS**：完整的 DNS 分流逻辑，Xray 不参与 DNS 处理
2. **MosDNS hosts 解决内网域名**：hisense.com → 10.19.255.253（在 office_nets 范围内，触发 TPROXY → sniffing 还原域名 → office 出口）
3. **freedom direct 用 AsIs**：不需要 Xray 重新解析，直接转发
4. **iptables MASQUERADE**：对 Xray mark 255 出站流量做 SNAT，解决 TPROXY IP_TRANSPARENT 回包不经过旁路由的问题
5. **防火墙放行 TPROXY 流量**：inet filter input 首条规则 `meta mark 1 accept`
6. **旁路由默认网关固定 192.168.50.1**：`/etc/network/interfaces` 静态配置，dhcpcd 已禁用
7. **nftables DNS(53) return 不劫持**：让 DNS 请求直达 MosDNS

## 高可用：主路由 Watchdog 自动切换

主路由 BE86U 上部署了 `/jffs/scripts/watchdog-openclash.sh`（v5），实现旁路由故障自动切换：

| 参数 | 值 | 说明 |
|------|-----|------|
| CHECK_INTERVAL | 5s | 检测间隔 |
| FAIL_THRESHOLD | 3 | 连续失败 3 次触发故障切换 (15s) |
| OK_THRESHOLD | 6 | 连续成功 6 次触发恢复 (30s) |
| RECOVER_COOLDOWN | 300s | 恢复方向冷却期（防翻转） |
| 检测方法 | ping + HTTP 代理 (10800) | 验证旁路由国内连通性 |

**切换逻辑**：
- 旁路由正常 → DHCP 网关/DNS = 192.168.50.2（翻墙 + 公司内网）
- 旁路由故障 → DHCP 网关/DNS = 192.168.50.1（直连国内，ISP DNS）
- 故障切换无冷却（15 秒即切），恢复切换有 300 秒冷却（防翻转）
- 开机自启动：`/jffs/scripts/services-start` 中调用
- 启动时等待旁路由上线最多 60 秒

**客户端感知延迟**：
- DHCP lease = 120 秒
- 故障后最长断网 ≈ 15 秒（检测）+ 60 秒（等客户端 DHCP 续约）= 75 秒

## 网络设备静态 IP 配置

| 设备 | IP | 网关 | 配置方式 | 说明 |
|------|-----|------|---------|------|
| 主路由 BE86U | 192.168.50.1 | PPPoE | 固有 | 全屋 DHCP Server |
| 旁路由 倍控 G31 | 192.168.50.2 | 192.168.50.1 | `/etc/network/interfaces` 静态 | 透明代理网关 |
| X5 Server | 192.168.50.10 | 192.168.50.1 | systemd-networkd 静态 | Docker/NPM/WireGuard |
| NAS 群晖 | 192.168.50.50 | 192.168.50.1 | DSM 静态 | xray vless-in(16824) |

**X5/NAS 网关固定为 192.168.50.1 的原因**：
- 这些设备有端口转发服务（NPM 反代、VLESS 入站），外网请求经主路由 DNAT 后到达它们
- 如果网关指向旁路由，回包会被旁路由 TPROXY 劫持（旁路由 conntrack 没有对应的入站记录）
- 网关指向主路由后，回包直接从主路由出去，不经过旁路由 TPROXY

## 主路由端口转发

| 服务 | 外部端口 | 内部端口 | 目标 IP | 说明 |
|------|---------|---------|---------|------|
| HTTP Server | 8081 | 8081 | 192.168.50.10 | NPM HTTP → 301 到 HTTPS:8088 |
| HTTP Server | 8088 | 8088 | 192.168.50.10 | NPM HTTPS 反代 |
| VLESS | 16824 | 16824 | 192.168.50.50 | NAS VLESS（远程访问家庭内网） |
| VLESS | 16825 | 16825 | 192.168.50.2 | 旁路由 VLESS（翻墙+内网） |
| Drive | 6690 | 6690 | 192.168.50.50 | Synology Drive |

## X5 Server Docker 配置

NPM 和 yqad 使用 bridge 网络模式，通过 Docker 端口映射暴露服务：

```yaml
# /opt/docker/docker-compose.yml 关键配置
npm:
  image: jc21/nginx-proxy-manager:latest
  ports:
    - "80:80"       # HTTP
    - "443:443"     # HTTPS
    - "81:81"       # 管理界面
    - "8081:80"     # 外网 HTTP 入口（主路由转发）
    - "8088:443"    # 外网 HTTPS 入口（主路由转发）

yqad:
  image: yqad-app:latest
  ports:
    - "3000:3000"
    - "3080:3080"

uptime-kuma:
  ports:
    - "3001:3001"

homeassistant:
  network_mode: host   # 需要 mDNS 发现设备
```

**NPM proxy hosts（通过域名区分后端）**：

| 域名 | 代理目标 | 说明 |
|------|---------|------|
| hxfssc.com | https://192.168.50.50:8088 | NAS 服务 |
| router.hxfssc.com | https://192.168.50.1:8443 | 主路由管理 |
| bt.hxfssc.com | http://192.168.50.50:9085 | qBittorrent |
| ha.hxfssc.com | http://192.168.50.10:8123 | HomeAssistant |

> **已清理的无效配置**：`npm-routing.service`（端口 redirect + 策略路由）已禁用。
> x5 网关固定为 192.168.50.1 后，不再需要策略路由让回包绕过旁路由；
> Docker bridge 端口映射替代了 iptables REDIRECT。

## 文件说明

| 文件 | 旁路由路径 | 说明 |
|------|-----------|------|
| xray-config.json | /usr/local/xray/config.json | Xray 主配置 |
| tproxy.nft | /usr/local/xray/tproxy.nft | nftables TPROXY 规则 |
| nftables.conf | /etc/nftables.conf | 系统防火墙（含 mark 1 放行） |
| mosdns-config.yaml | /etc/mosdns/config.yaml | MosDNS DNS 分流配置 |

| 文件 | 主路由路径 | 说明 |
|------|-----------|------|
| watchdog-openclash.sh | /jffs/scripts/watchdog-openclash.sh | 旁路由可用性监控 v5 |
| nat-start | /jffs/scripts/nat-start | NAT 规则初始化 |
| access-networks.sh | /jffs/scripts/access-networks.sh | 跨子网管理通道（光猫+交换机） |
| services-start | /jffs/scripts/services-start | 开机服务启动（含 watchdog） |

| 文件 | X5 路径 | 说明 |
|------|---------|------|
| 20-wired.network | /etc/systemd/network/20-wired.network | 静态 IP (192.168.50.10, gw 192.168.50.1) |
| docker-compose.yml | /opt/docker/docker-compose.yml | 所有 Docker 服务定义 |
| .gitconfig | /root/.gitconfig | git 代理（仅 GitHub 走旁路由代理） |
| daemon.json | /etc/docker/daemon.json | Docker 国内镜像源 |

## X5 Server 网络与代理配置

X5 网关固定为 192.168.50.1（不走旁路由），无法直接翻墙。各应用的镜像/代理方案：

| 应用 | 方案 | 配置 |
|------|------|------|
| APT | 清华镜像 | /etc/apt/sources.list |
| Docker pull | 国内镜像 | /etc/docker/daemon.json (docker.1ms.run) |
| git (GitHub) | 旁路由 HTTP 代理 | ~/.gitconfig `http.https://github.com.proxy` |
| ghcr.io | 国内直连 | 无需配置 |
| Let's Encrypt | 国内直连 | 无需配置 |
| 临时翻墙 | shell 别名 | `proxy_on` / `proxy_off`（~/.bashrc） |

## 与 FakeDNS 方案的对比

| | FakeDNS 方案（之前） | MosDNS 独立方案（当前） |
|--|--|--|
| DNS 处理 | Xray 内置 DNS + FakeDNS | MosDNS 独立 |
| 内网域名 | FakeDNS 198.18.x.x/10.19.x.x | hosts 固定 10.19.255.253 |
| DNS 分流 | Xray dns servers 配置 | MosDNS 规则文件 |
| 职责 | Xray 管 DNS + 代理 | MosDNS 管 DNS，Xray 管代理 |
| 复杂度 | dns-in/dns-out/fakedns 耦合 | 解耦清晰 |

## 与原 iStoreOS 的差异

| 项目 | 原 iStoreOS | 当前 Debian |
|------|------------|-------------|
| DNS 53 端口 | dnsmasq → Xray 5353 | MosDNS 独立处理 |
| DNS 逻辑 | Xray 内置 DNS + FakeDNS | MosDNS 分流 + hosts |
| 内网域名 | FakeDNS 198.18.x.x | MosDNS hosts 10.19.255.253 |
| office 协议 | VMess+WS | VLESS+xhttp |
| office 地址 | ws.fssc.top (域名) | 103.94.200.246 (IP直连) |
| direct 回包 | 无问题(可能有隐式NAT) | iptables MASQUERADE mark 255 |
| 防火墙 | 无 inet filter | inet filter (需 mark 1 accept) |
| 网关保护 | DHCP + hook | 静态 IP（dhcpcd 已禁用） |
| 高可用 | 无 | watchdog v5 自动切换 |
