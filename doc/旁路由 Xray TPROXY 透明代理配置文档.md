# 旁路由 Xray TPROXY 透明代理配置文档

## 概述

- **设备**: 192.168.50.2 (iStoreOS 24.10.7, x86_64)
- **角色**: 局域网旁路由，实现透明代理
- **功能**: 翻墙（VLESS+XTLS-Vision）+ 公司内网访问（VMess+WS）
- **Xray 版本**: v26.3.27
- **代理模式**: TProxy 透明代理 + FakeDNS

## 网络架构

```
局域网设备 → 主路由(192.168.50.1) → 旁路由(192.168.50.2)
                                          ├── proxy出口 → 翻墙(VLESS) → 154.26.187.89
                                          ├── office出口 → 公司内网(VMess) → ws.fssc.top
                                          ├── direct出口 → 国内直连
                                          └── block出口 → 广告拦截
```

## 文件结构

```
/usr/local/xray/
├── xray                    # 二进制文件
├── config.json             # 主配置文件
├── tproxy.nft.save         # nftables 规则
├── geoip.dat               # GeoIP 数据库
└── geosite.dat             # GeoSite 数据库

/etc/init.d/xray            # 服务管理脚本
/etc/sysctl.conf            # 内核参数优化
```

## 核心配置文件

### 1. Xray 配置 (`/usr/local/xray/config.json`)

```json
{
  "log": { "loglevel": "warning" },
  "fakedns": [
    { "ipPool": "198.18.0.0/16", "poolSize": 65535 },
    { "ipPool": "fc00::/18", "poolSize": 65535 }
  ],
  "dns": {
    "servers": [
      {
        "address": "fakedns",
        "domains": ["domain:hisense.com"]
      },
      {
        "address": "https://dns.google/dns-query",
        "domains": ["geosite:geolocation-!cn"],
        "expectIPs": ["geoip:!cn"]
      },
      {
        "address": "223.5.5.5",
        "domains": ["geosite:cn", "domain:fssc.top"],
        "expectIPs": ["geoip:cn"]
      },
      "223.5.5.5"
    ]
  },
  "inbounds": [
    {
      "tag": "tproxy-in",
      "port": 12345,
      "listen": "0.0.0.0",
      "protocol": "dokodemo-door",
      "settings": {
        "network": "tcp,udp",
        "followRedirect": true
      },
      "streamSettings": {
        "sockopt": {
          "tproxy": "tproxy",
          "mark": 255
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["fakedns+others", "http", "tls", "quic"]
      }
    },
    {
      "tag": "dns-in",
      "port": 5353,
      "listen": "0.0.0.0",
      "protocol": "dokodemo-door",
      "settings": {
        "address": "223.5.5.5",
        "port": 53,
        "network": "tcp,udp"
      }
    }
  ],
  "outbounds": [
    {
      "tag": "proxy",
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "154.26.187.89",
          "port": 443,
          "users": [{
            "id": "879fc4cf-28d8-4bb3-8b88-6e0dd53cb940",
            "encryption": "none",
            "flow": "xtls-rprx-vision"
          }]
        }]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "tls",
        "tlsSettings": {
          "allowInsecure": false,
          "serverName": "cxl.fssc.top",
          "fingerprint": "chrome"
        },
        "sockopt": { "mark": 255 }
      }
    },
    {
      "tag": "office",
      "protocol": "vmess",
      "settings": {
        "vnext": [{
          "address": "ws.fssc.top",
          "port": 443,
          "users": [{
            "id": "0244b6a5-2b80-4ef5-bdba-ef81024e875f",
            "alterId": 0
          }]
        }]
      },
      "streamSettings": {
        "network": "ws",
        "security": "tls",
        "tlsSettings": { "serverName": "ws.fssc.top", "fingerprint": "chrome" },
        "wsSettings": { "path": "/" },
        "sockopt": { "mark": 255 }
      }
    },
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": { "domainStrategy": "UseIP" },
      "streamSettings": { "sockopt": { "mark": 255 } }
    },
    {
      "tag": "block",
      "protocol": "blackhole",
      "settings": { "response": { "type": "http" } }
    },
    {
      "tag": "dns-out",
      "protocol": "dns"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type": "field",
        "inboundTag": ["dns-in"],
        "outboundTag": "dns-out"
      },
      {
        "type": "field",
        "protocol": ["dns"],
        "outboundTag": "dns-out"
      },
      {
        "type": "field",
        "domain": ["domain:hisense.com"],
        "outboundTag": "office"
      },
      {
        "type": "field",
        "ip": ["10.19.0.0/16", "172.16.0.0/16", "10.30.0.0/16", "10.33.0.0/16", "10.16.0.0/16"],
        "outboundTag": "office"
      },
      {
        "type": "field",
        "domain": ["geosite:category-ads-all"],
        "outboundTag": "block"
      },
      {
        "type": "field",
        "domain": ["geosite:cn", "domain:apple.com", "domain:mzstatic.com", "domain:itunes.apple.com", "domain:ai.fssc.top"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "ip": ["geoip:cn", "geoip:private"],
        "outboundTag": "direct"
      },
      {
        "type": "field",
        "port": "0-65535",
        "outboundTag": "proxy"
      }
    ]
  }
}
```

### 2. nftables 规则 (`/usr/local/xray/tproxy.nft.save`)

```nft
table ip xray {
    chain prerouting {
        type filter hook prerouting priority mangle; policy accept;

        # 公司内网IP段优先走tproxy（在排除规则之前）
        ip daddr 172.16.0.0/16 meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept
        ip daddr 10.16.0.0/16 meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept
        ip daddr 10.33.0.0/16 meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept
        ip daddr 10.30.0.0/16 meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept
        ip daddr 10.19.0.0/16 meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept

        # xray 自身流量不代理（mark 0xff = 255）
        meta mark 0x000000ff return

        # 保留地址段不代理
        ip daddr 127.0.0.0/8 return
        ip daddr 192.168.0.0/16 return
        ip daddr 10.0.0.0/8 return
        ip daddr 172.16.0.0/12 return
        ip daddr 169.254.0.0/16 return
        ip daddr 224.0.0.0/4 return
        ip daddr 240.0.0.0/4 return
        ip daddr 255.255.255.255 return

        # DNS 流量走 xray DNS 端口
        meta l4proto { tcp, udp } th dport 53 tproxy to 127.0.0.1:5353 meta mark set 0x00000001 accept

        # 其他所有流量走 xray 代理端口
        meta l4proto { tcp, udp } tproxy to 127.0.0.1:12345 meta mark set 0x00000001 accept
    }

    chain output {
        type route hook output priority mangle; policy accept;

        # 公司内网IP段（路由器本机出站也走代理）
        ip daddr 172.16.0.0/16 meta l4proto { tcp, udp } meta mark set 0x00000001 accept
        ip daddr 10.16.0.0/16 meta l4proto { tcp, udp } meta mark set 0x00000001 accept
        ip daddr 10.33.0.0/16 meta l4proto { tcp, udp } meta mark set 0x00000001 accept
        ip daddr 10.30.0.0/16 meta l4proto { tcp, udp } meta mark set 0x00000001 accept
        ip daddr 10.19.0.0/16 meta l4proto { tcp, udp } meta mark set 0x00000001 accept

        # xray 自身流量排除
        meta mark 0x000000ff return

        # 保留地址段排除
        ip daddr 127.0.0.0/8 return
        ip daddr 192.168.0.0/16 return
        ip daddr 10.0.0.0/8 return
        ip daddr 172.16.0.0/12 return
        ip daddr 224.0.0.0/4 return

        # DNS 和其他流量
        meta l4proto { tcp, udp } th dport 53 meta mark set 0x00000001 accept
        meta l4proto { tcp, udp } meta mark set 0x00000001 accept
    }
}
```

**规则逻辑说明**:
- 公司内网 IP 段（10.19/172.16/10.30/10.33/10.16）在排除规则之前匹配，确保这些流量走 xray → office 出口
- `mark 0xff` 是 xray 自身出站流量的标记，避免回环
- 保留地址（局域网、回环、组播）排除代理
- 最后兜底规则将剩余流量送入 xray

### 3. 服务管理脚本 (`/etc/init.d/xray`)

```sh
#!/bin/sh /etc/rc.common
# Xray TPROXY transparent proxy service

START=99
STOP=10
USE_PROCD=1

XRAY_BIN="/usr/local/xray/xray"
XRAY_CONF="/usr/local/xray/config.json"
XRAY_LOG="/tmp/xray.log"
NFT_RULES="/usr/local/xray/tproxy.nft.save"

start_service() {
    # 先清理旧规则，防止重启时规则累积
    nft delete table ip xray 2>/dev/null
    ip rule del fwmark 1 table 100 2>/dev/null
    ip route del local default dev lo table 100 2>/dev/null

    # 设置路由策略（fwmark 1 的包走 table 100 → 本地回环）
    ip route add local default dev lo table 100
    ip rule add fwmark 1 table 100

    # 加载 nftables 规则
    nft -f "$NFT_RULES"

    # 通过 procd 启动 xray（支持自动重启）
    procd_open_instance
    procd_set_param command "$XRAY_BIN" run -c "$XRAY_CONF"
    procd_set_param stdout 1
    procd_set_param stderr 1
    procd_set_param file "$XRAY_CONF"
    procd_set_param respawn 3600 5 5
    procd_close_instance

    logger -t xray "Xray TPROXY service started"
}

stop_service() {
    nft delete table ip xray 2>/dev/null
    ip rule del fwmark 1 table 100 2>/dev/null
    ip route del local default dev lo table 100 2>/dev/null
    logger -t xray "Xray TPROXY service stopped"
}

reload_service() {
    stop
    start
}
```

### 4. 内核参数优化 (`/etc/sysctl.conf`)

```ini
# 连接跟踪
net.netfilter.nf_conntrack_max=131072
net.netfilter.nf_conntrack_tcp_timeout_established=600
net.netfilter.nf_conntrack_tcp_timeout_time_wait=30

# 网络缓冲区
net.core.rmem_max=16777216
net.core.wmem_max=16777216

# TCP orphan socket 上限（防止周期性断网）
net.ipv4.tcp_max_orphans = 16384

# 内存
vm.swappiness=10
vm.overcommit_memory=1
```

## 关键设计决策

### FakeDNS 解决公司内网域名解析

**问题**: 公司内网域名（如 `gitlab.hisense.com`）在公网 DNS 上不存在（NXDOMAIN），客户端无法解析就无法发起连接。

**方案**: 使用 FakeDNS 为这些域名返回假 IP（198.18.x.x），客户端用假 IP 发起连接后，xray 通过 sniffing 还原出真实域名，路由到 office 出口，由远端 VPN 服务器完成真实的 DNS 解析和连接。

**IPv6 支持**: 同时配置了 IPv6 假 IP 池 (`fc00::/18`)，因为 musl libc 的 `getaddrinfo()` 会同时发 A 和 AAAA 查询，如果 AAAA 无响应会导致整体超时失败。

### sniffing 配置: `fakedns+others`

- `fakedns+others`: 仅对目标 IP 在 fakedns 池范围内的连接做域名还原（将 198.18.x.x 替换回原始域名）
- 对正常 IP 的连接不做替换，避免影响 CDN 等场景
- 同时支持 `http`/`tls`/`quic` 嗅探用于路由决策

### mark 255 避免回环

所有 outbound 配置了 `"sockopt": { "mark": 255 }`，nftables 规则中 `meta mark 0x000000ff return` 确保 xray 自身的出站流量不会被再次截获，避免死循环。

### nftables 规则顺序

公司内网 IP 段的 tproxy 规则放在排除规则之前。因为 10.0.0.0/8 和 172.16.0.0/12 在排除列表中，如果不优先匹配公司网段，这些流量会被 `return` 直接放行而无法通过 VPN 到达。

## 路由规则优先级

| 优先级 | 匹配条件 | 出口 | 说明 |
|--------|----------|------|------|
| 1 | DNS 流量 (dns-in tag / dns protocol) | dns-out | DNS 请求由 xray 内置 DNS 处理 |
| 2 | domain:hisense.com | office | 公司域名走 VPN |
| 3 | 公司内网 IP 段 | office | 10.19/172.16/10.30/10.33/10.16 |
| 4 | 广告域名 | block | geosite:category-ads-all |
| 5 | 国内域名/Apple | direct | geosite:cn + 苹果服务 |
| 6 | 国内 IP + 私有 IP | direct | geoip:cn + geoip:private |
| 7 | 其他所有流量 | proxy | 兜底走翻墙代理 |

## DNS 解析策略

| 域名类型 | DNS 服务器 | 说明 |
|----------|-----------|------|
| hisense.com | FakeDNS | 返回假 IP，由远端 VPN 解析 |
| 国外域名 (geosite:geolocation-!cn) | dns.google (DoH) | 防污染 |
| 国内域名 (geosite:cn) + fssc.top | 223.5.5.5 (阿里) | 低延迟 |
| 其他 | 223.5.5.5 (兜底) | — |

## dnsmasq 配置要点

旁路由的 dnsmasq 需要将 DNS 查询转发到 xray：

```
server=127.0.0.1#5353
no-resolv
filter-AAAA
cache-size=0
```

- `server=127.0.0.1#5353`: 所有 DNS 查询发给 xray 的 dns-in 端口
- `no-resolv`: 不使用系统上游 DNS
- `filter-AAAA`: 过滤 IPv6 记录（旁路由无 IPv6 出口）
- `cache-size=0`: 不缓存，由 xray 管理 DNS 缓存

## 运维命令

```bash
# 服务管理
/etc/init.d/xray start
/etc/init.d/xray stop
/etc/init.d/xray restart
/etc/init.d/xray status

# 查看日志
logread | grep xray | tail -20
cat /tmp/xray.log

# 验证配置语法
/usr/local/xray/xray run -test -c /usr/local/xray/config.json

# 检查 nftables 规则
nft list table ip xray

# 检查路由策略
ip rule list
ip route show table 100

# 连通性测试
curl -s -o /dev/null -w '%{http_code}\n' https://www.google.com       # 翻墙
curl -s -o /dev/null -w '%{http_code}\n' http://gitlab.hisense.com    # 内网域名
curl -s -o /dev/null -w '%{http_code}\n' http://172.16.43.111         # 内网 IP
curl -s -o /dev/null -w '%{http_code}\n' https://www.baidu.com        # 国内直连

# 检查 TCP orphan socket（不应再出现 "too many orphaned sockets"）
dmesg | grep orphan
cat /proc/sys/net/ipv4/tcp_max_orphans

# DNS 解析测试
nslookup gitlab.hisense.com 127.0.0.1    # 应返回 198.18.x.x
nslookup google.com 127.0.0.1            # 应返回真实 IP
```

## 故障排查

### 周期性短暂断网

**表现**: 每隔一段时间出现几秒钟无法上网  
**原因**: `tcp_max_orphans` 过低，代理产生大量 TIME_WAIT 连接转为 orphan 触发内核 RST  
**检查**: `dmesg | grep "too many orphaned sockets"`  
**修复**: 调高 `net.ipv4.tcp_max_orphans`（当前 16384，如仍有问题可调到 32768）

### 公司内网域名无法访问

**表现**: `curl: (6) Could not resolve host`  
**原因**: 内网域名在公网 DNS 不存在，需要 FakeDNS 配合 sniffing 域名还原  
**检查**: `nslookup gitlab.hisense.com 127.0.0.1` 应返回 198.18.x.x  
**修复**: 确认 fakedns 配置包含 IPv4+IPv6 池，sniffing 使用 `fakedns+others`

### nftables 规则重复

**表现**: `nft list table ip xray` 显示规则重复出现  
**原因**: 服务重启时未先清理旧规则  
**修复**: init.d 脚本 `start_service()` 开头先执行 `nft delete table ip xray`

### xray 进程崩溃后未恢复

**检查**: `/etc/init.d/xray status` + `ps | grep xray`  
**修复**: procd 的 `respawn 3600 5 5` 参数确保自动重启（3600秒内最多重启5次，间隔5秒）

## 新增公司内网 IP 段

如需增加新的内网 IP 段，需同时修改两处：

1. **config.json** - routing.rules 中 office 出口的 IP 列表
2. **tproxy.nft.save** - prerouting 和 output chain 开头添加对应的 tproxy/mark 规则

修改后执行 `/etc/init.d/xray restart` 生效。

## 新增内网域名

如需增加新的公司内网域名（在公网 DNS 解析不到的），在 dns.servers 的 fakedns 条目中添加：

```json
{
  "address": "fakedns",
  "domains": ["domain:hisense.com", "domain:newdomain.com"]
}
```

同时在 routing.rules 中添加对应的路由规则指向 office 出口。
