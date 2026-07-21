# 部署说明

## 方式一：独立部署（推荐开发测试）

```bash
cd monitor-dashboard
cp .env.example .env
# 编辑 .env 填入实际配置
docker compose up -d --build
```

访问：http://192.168.50.10:3030

## 方式二：集成到 X5-Server 现有 docker-compose

在 `/opt/docker/docker-compose.yml` 中添加以下服务：

```yaml
  monitor-dashboard:
    build: /opt/docker/monitor-dashboard
    container_name: monitor-dashboard
    restart: unless-stopped
    depends_on:
      - portainer
    ports:
      - "3030:3030"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /root/.ssh/id_rsa:/root/.ssh/id_rsa:ro
      - /root/.ssh/known_hosts:/root/.ssh/known_hosts:ro
    env_file:
      - /opt/docker/monitor-dashboard/.env
    environment:
      - TZ=Asia/Shanghai
```

然后：

```bash
cd /opt/docker
docker compose up -d --build monitor-dashboard
```

## SSH 密钥配置

确保 X5-Server 的 `/root/.ssh/id_rsa` 已配置到旁路由和主路由的免密登录：

```bash
# 在 X5-Server 上执行
ssh-copy-id root@192.168.50.2   # 旁路由
ssh-copy-id admin@192.168.50.1  # 主路由（如果开启了 SSH）
```

## Kiosk 模式配置

参见 tasks.md 第 6 组任务，全程 SSH 远程完成。
