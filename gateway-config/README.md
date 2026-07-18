# 倍控 G31 旁路由运行配置

当前在旁路由(192.168.50.2)上实际运行的配置文件备份。

## 架构

```
客户端 DNS(53) → MosDNS(53) → Xray dns-in(5353) → Xray 内置 DNS(FakeDNS/DoH/223.5.5.5)
客户端 流量   → nftables TPROXY → Xray tproxy-in(12345) → proxy/office/direct/block
```

## 关键设计

1. **DNS 由 Xray 全权处理**：MosDNS 仅作为 53 端口的转发层，所有 DNS 逻辑在 Xray 内置 DNS 中完成
2. **FakeDNS 解决内网域名**：hisense.com 返回 10.19.252.0/22 段假 IP，经 sniffing 还原域名后走 office 出口
3. **freedom direct 用 UseIP**：避免 TPROXY 模式下 IP_TRANSPARENT socket 导致回包不经过旁路由
4. **防火墙放行 TPROXY 流量**：inet filter input 首条规则 `meta mark 1 accept`
5. **默认网关固定 192.168.50.1**：通过 dhcpcd hook + interfaces post-up 双重保证，防止 DHCP 网关切换影响旁路由出站

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
| DNS 53 端口 | dnsmasq 转发到 Xray 5353 | MosDNS 转发到 Xray 5353 |
| office 协议 | VMess+WS | VLESS+xhttp |
| office 地址 | ws.fssc.top (域名) | 103.94.200.246 (IP直连，避免DNS循环) |
| 防火墙 | 无 inet filter | 有 inet filter (需 mark 1 accept) |
| 网关保护 | 静态 IP，无需保护 | dhcpcd hook 强制网关为 50.1 |
