# Docker 新项目部署流程（X5 Server）

## 概述

本文档描述在联想 X5-14 Docker 服务器上新增一个项目的标准流程。适用于任何需要在该服务器上部署 Docker 容器化服务的场景。

**服务器信息**:
- 主机: x5server
- IP: 192.168.50.10
- 系统: Debian 13 (Trixie)
- Docker 数据根目录: `/opt/docker/`
- 编排文件: `/opt/docker/docker-compose.yml`

---

## 前置条件

- 已通过 SSH 连接到服务器: `ssh root@192.168.50.10`
- Docker CE 和 Docker Compose 插件已安装并运行
- `/opt/docker/docker-compose.yml` 已存在且包含现有服务

---

## 部署步骤

### 第一步：创建持久化目录

在 `/opt/docker/` 下为新项目创建数据目录：

```bash
mkdir -p /opt/docker/<项目名>/data
```

如果项目需要多个持久化目录（如配置、日志、数据库分离），按需创建：

```bash
mkdir -p /opt/docker/<项目名>/{config,data,logs}
```

**命名规范**:
- 项目目录名使用小写字母和连字符，如 `uptime-kuma`、`home-assistant`
- 子目录名称应与容器内的挂载用途对应

---

### 第二步：编辑 docker-compose.yml

编辑 `/opt/docker/docker-compose.yml`，在 `services:` 段落下新增服务定义：

```bash
vim /opt/docker/docker-compose.yml
```

添加内容模板：

```yaml
  <项目名>:
    image: <镜像名>:<标签>
    container_name: <项目名>
    restart: unless-stopped
    depends_on:
      - portainer
    ports:
      - "<宿主机端口>:<容器端口>"
    environment:
      - TZ=Asia/Shanghai
    volumes:
      - /opt/docker/<项目名>/data:/容器内数据路径
```

**配置要求**:

| 字段 | 要求 | 说明 |
|------|------|------|
| image | 必填 | 优先使用官方镜像，标签用 `latest` 或固定版本 |
| container_name | 必填 | 与服务名一致，方便 `docker logs` 等命令使用 |
| restart | 必填 | 统一使用 `unless-stopped` |
| ports | 按需 | 宿主机端口不得与已占用端口冲突 |
| environment | 推荐 | 至少设置 `TZ=Asia/Shanghai` |
| volumes | 必填 | 持久化数据必须挂载到 `/opt/docker/<项目名>/` 下 |

**已占用端口**（不可使用）:

| 端口 | 服务 |
|------|------|
| 80 | Nginx Proxy Manager (HTTP) |
| 443 | Nginx Proxy Manager (HTTPS) |
| 81 | Nginx Proxy Manager 管理面板 |
| 8081 | NPM 外网 HTTP 入口 |
| 8088 | NPM 外网 HTTPS 入口 |
| 9000 | Portainer (HTTP) |
| 9443 | Portainer (HTTPS) |
| 8123 | Home Assistant |
| 3001 | Uptime Kuma |

---

### 第三步：启动服务

```bash
cd /opt/docker
docker compose up -d <项目名>
```

该命令只会创建/更新指定的服务，不会影响其他已运行的容器。

如果需要同时更新编排文件中的所有服务：

```bash
cd /opt/docker
docker compose up -d
```

---

### 第四步：验证部署

```bash
# 1. 确认容器状态为 running
docker ps | grep <项目名>

# 2. 查看启动日志，确认无报错
docker logs <项目名> --tail 50

# 3. 测试服务端口响应
curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:<端口>
# 预期: 200 或 302

# 4. 确认持久化目录已写入数据
ls -la /opt/docker/<项目名>/data/
```

---

### 第五步（可选）：配置反向代理

如果需要通过域名访问该服务，在 Nginx Proxy Manager 中添加代理规则：

1. 访问 http://192.168.50.10:81
2. 点击 "Proxy Hosts" → "Add Proxy Host"
3. 填写:
   - Domain Names: 你的域名
   - Scheme: http
   - Forward Hostname/IP: 192.168.50.10（或容器名，如果在同一 Docker 网络）
   - Forward Port: 容器对外映射的宿主机端口
4. 按需配置 SSL 证书

---

### 第六步（可选）：添加监控

在 Uptime Kuma 中添加对新服务的监控：

1. 访问 http://192.168.50.10:3001
2. 点击 "Add New Monitor"
3. 配置:
   - Monitor Type: HTTP(s) 或 TCP Port
   - URL/Host: http://192.168.50.10:<端口>
   - Heartbeat Interval: 60-300s（根据服务重要性）

---

## 完整示例：部署 Gitea

```bash
# 1. 创建持久化目录
mkdir -p /opt/docker/gitea/data

# 2. 编辑 docker-compose.yml，在 services: 下添加:
#
#   gitea:
#     image: gitea/gitea:latest
#     container_name: gitea
#     restart: unless-stopped
#     depends_on:
#       - portainer
#     ports:
#       - "3000:3000"
#       - "2222:22"
#     environment:
#       - TZ=Asia/Shanghai
#     volumes:
#       - /opt/docker/gitea/data:/data

# 3. 启动
cd /opt/docker
docker compose up -d gitea

# 4. 验证
docker ps | grep gitea
docker logs gitea --tail 20
curl -s -o /dev/null -w '%{http_code}' http://192.168.50.10:3000

# 5. 浏览器访问 http://192.168.50.10:3000 完成初始化配置
```

---

## 运维相关

### 备份

新增项目的持久化数据**自动被现有备份脚本覆盖**，无需额外配置。

备份脚本 `/usr/local/bin/backup-docker.sh` 每日凌晨 3 点 rsync 整个 `/opt/docker/` 到群晖 NAS，新增的子目录自动包含在内。

### 更新镜像

```bash
cd /opt/docker
docker compose pull <项目名>
docker compose up -d <项目名>
```

### 回滚

如果更新后服务异常：

1. 停止服务: `docker compose stop <项目名>`
2. 修改 `docker-compose.yml` 中的镜像标签为指定版本（如 `image: gitea/gitea:1.21.0`）
3. 重新启动: `docker compose up -d <项目名>`

### 删除项目

```bash
cd /opt/docker

# 停止并移除容器
docker compose down <项目名>

# 从 docker-compose.yml 中删除对应的服务定义

# 删除持久化数据（确认不再需要后）
rm -rf /opt/docker/<项目名>
```

### 查看资源占用

```bash
# 查看所有容器 CPU/内存使用
docker stats --no-stream

# 查看磁盘使用
docker system df
du -sh /opt/docker/*/
```

---

## 注意事项

1. **日志限制**: 已在 `/etc/docker/daemon.json` 全局配置（单文件 50MB，最多 3 个文件轮转），无需在每个服务中单独配置。

2. **网络模式**: 默认使用 Docker bridge 网络。如果新项目需要发现局域网设备（如智能家居协议），使用 `network_mode: host`。

3. **镜像加速**: 已配置国内 registry mirror，拉取镜像时自动加速。

4. **端口选择**: 宿主机端口选择 1024 以上未被占用的端口，建议在 3000-9999 范围内选取。

5. **数据安全**: HDD 有机械故障风险，重要数据依赖每日备份到 NAS。部署完成后建议手动执行一次 `backup-docker.sh` 验证备份正常。

6. **内存预估**: 当前已用约 1-1.5 GB，剩余 14+ GB。新增轻量服务（100-500 MB）无压力。如果部署内存密集型应用（如数据库），提前评估。

---

**文档维护时间**: 2025-07
**关联文档**: [联想X5-14 Docker服务器部署方案.md](联想X5-14%20Docker服务器部署方案.md)
