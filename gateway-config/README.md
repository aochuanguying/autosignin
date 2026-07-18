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
6. **默认网关固定 192.168.50.1**：dhcpcd hook + interfaces post-up 双重保证
7. **nftables DNS(53) return 不劫持**：让 DNS 请求直达 MosDNS

## 与 FakeDNS 方案的对比

| | FakeDNS 方案（之前） | MosDNS 独立方案（当前） |
|--|--|--|
| DNS 处理 | Xray 内置 DNS + FakeDNS | MosDNS 独立 |
| 内网域名 | FakeDNS 198.18.x.x/10.19.x.x | hosts 固定 10.19.255.253 |
| DNS 分流 | Xray dns servers 配置 | MosDNS 规则文件 |
| 职责 | Xray 管 DNS + 代理 | MosDNS 管 DNS，Xray 管代理 |
| 复杂度 | dns-in/dns-out/fakedns 耦合 | 解耦清晰 |

## 文件说明

| 文件 | 旁路由路径 | 说明 |
|------|-----------|------|
| xray-config.json | /usr/local/xray/config.json | Xray 主配置 |
| tproxy.nft | /usr/local/xray/tproxy.nft | nftables TPROXY 规则 |
| nftables.conf | /etc/nftables.conf | 系统防火墙（含 mark 1 放行） |
| mosdns-config.yaml | /etc/mosdns/config.yaml | MosDNS 配置（纯转发到 Xray 5353） |

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
| 网关保护 | 静态 IP | dhcpcd hook + post-up |
