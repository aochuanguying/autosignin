# AutoJS API 服务文档

## 📋 目录

1. [服务简介](#服务简介)
2. [系统架构](#系统架构)
3. [核心配置](#核心配置)
4. [API 接口文档](#api-接口文档)
5. [使用示例](#使用示例)
6. [部署指南](#部署指南)
7. [服务管理](#服务管理)
8. [开机自启动](#开机自启动)
9. [故障排查](#故障排查)

---

## 🎯 服务简介

AutoJS API Service 是一个基于 Python HTTP 服务器的远程脚本执行服务，允许通过 RESTful API 远程调用 AutoJS6 脚本。

**核心功能**:
- ✅ RESTful API 接口
- ✅ Bearer Token 认证
- ✅ 脚本列表查询
- ✅ 远程脚本执行（同步/异步）
- ✅ 开机自启动（Magisk）
- ✅ 看门狗监控（30 秒检查，异常自动重启）
- ✅ 完整的日志系统

**项目位置**: `/Users/mac/Documents/workspace/krio/autosignin/autojs-api-service/`

---

## 🏗️ 系统架构

```
┌──────────────┐      HTTP API       ┌─────────────┐
│   客户端      │ ◄─────────────────► │  Python     │
│  (curl/SDK)  │   Port: 8899        │  HTTP Server│
└──────────────┘                     └──────┬──────┘
                                            │
                                     调用 AutoJS6
                                            │
                                     ┌──────▼──────┐
                                     │  AutoJS6    │
                                     │  脚本引擎   │
                                     └─────────────┘
```

**与 android-telecom-api 的对比**:

| 特性 | android-telecom-api | autojs-api-service |
|------|---------------------|-------------------|
| 服务类型 | Python Flask | Shell (nc/socat) |
| 端口 | 5000 | 8899 |
| 认证方式 | Bearer Token | Bearer Token |
| 开机自启 | ✓ | ✓ |
| 看门狗 | ✗ | ✓ |
| 服务管理 | ✓ | ✓ |
| 配置目录 | ~/.telecom-api | ~/.autojs-api |

---

## ⚙️ 核心配置

| 配置项 | 值 |
|--------|-----|
| **服务端口** | 8899 |
| **脚本目录** | `/sdcard/脚本` |
| **AutoJS 包名** | `org.autojs.autojs6` |
| **认证 Token** | `api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2` |

---

## 🌐 API 接口文档

### 1. 健康检查

**接口**: `GET /api/health`

**响应**:
```json
{
  "success": true,
  "message": "Service is running"
}
```

**示例**:
```bash
curl http://192.168.50.149:8899/api/health
```

---

### 2. 获取脚本列表

**接口**: `GET /api/scripts`

**请求头**:
```
Authorization: Bearer api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2
```

**响应**:
```json
{
  "success": true,
  "data": {
    "scripts": [
      "audi_signin.js",
      "audi_post.js",
      "common_utils.js"
    ]
  }
}
```

**示例**:
```bash
curl -H "Authorization: Bearer api_token_..." \
  http://192.168.50.149:8899/api/scripts
```

---

### 3. 执行脚本

**接口**: `POST /api/execute`

**请求头**:
```
Authorization: Bearer api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2
Content-Type: application/json
```

**请求体**:
```json
{
  "script": "audi_signin.js",
  "sync": false
}
```

**参数说明**:
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `script` | string | ✓ | 脚本文件名（相对于 `/sdcard/脚本` 目录） |
| `sync` | boolean | ✗ | 是否同步等待执行完成（默认：false） |

**成功响应**:
```json
{
  "success": true,
  "message": "脚本执行成功",
  "data": {
    "script": "audi_signin.js",
    "sync": false
  }
}
```

**失败响应**:
```json
{
  "success": false,
  "message": "错误信息"
}
```

**示例**:
```bash
# 异步执行
curl -X POST \
  -H "Authorization: Bearer api_token_..." \
  -H "Content-Type: application/json" \
  -d '{"script":"audi_signin.js","sync":false}' \
  http://192.168.50.149:8899/api/execute

# 同步执行（等待完成）
curl -X POST \
  -H "Authorization: Bearer api_token_..." \
  -H "Content-Type: application/json" \
  -d '{"script":"audi_signin.js","sync":true}' \
  http://192.168.50.149:8899/api/execute
```

---

## 💡 使用示例

### cURL 调用

```bash
# 定义变量
API_TOKEN="api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2"
BASE_URL="http://192.168.50.149:8899"

# 健康检查
curl $BASE_URL/api/health

# 获取脚本列表
curl -H "Authorization: Bearer $API_TOKEN" \
  $BASE_URL/api/scripts

# 执行发帖脚本
curl -X POST \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"script":"audi_post.js"}' \
  $BASE_URL/api/execute
```

---

### Python 调用

```python
import requests

BASE_URL = "http://192.168.50.149:8899"
API_TOKEN = "api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# 健康检查
response = requests.get(f"{BASE_URL}/api/health")
print(response.json())

# 获取脚本列表
response = requests.get(f"{BASE_URL}/api/scripts", headers=headers)
print(response.json())

# 执行脚本
response = requests.post(
    f"{BASE_URL}/api/execute",
    headers=headers,
    json={"script": "audi_signin.js", "sync": False}
)
print(response.json())
```

---

### Shell 脚本封装

```bash
#!/bin/bash

API_TOKEN="api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2"
API_SERVER="http://192.168.50.149:8899"

execute_script() {
    local script=$1
    curl -X POST \
        -H "Authorization: Bearer $API_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"script\":\"$script\",\"sync\":false}" \
        "$API_SERVER/api/execute"
}

# 执行签到
execute_script "audi_signin.js"
```

---

## 📦 部署指南

### 系统要求

- ✅ Android 设备已 Root
- ✅ Magisk
- ✅ Termux（提供 Python3）
- ✅ AutoJS6 已安装并授予 root 和无障碍权限

---

### 方法一：使用部署脚本（推荐）

```bash
cd autojs-api-service
./deploy.sh
```

---

### 方法二：手动部署

```bash
# 1. 上传脚本
adb push autojs-api-service.sh /data/adb/service.d/
adb push autojs-api-watchdog.sh /data/adb/service.d/

# 2. 设置权限
adb shell "chmod 755 /data/adb/service.d/*.sh"

# 3. 重启设备
adb reboot
```

---

### 方法三：Termux 部署

```bash
# 在 Termux 中
cd ~/autosignin/autojs-api-service

# 配置开机自启
./setup-boot-start.sh

# 启动服务
./start-service.sh start
```

---

## 🔧 服务管理

### 基本命令

```bash
# 启动服务
./start-service.sh start

# 停止服务
./start-service.sh stop

# 重启服务
./start-service.sh restart

# 查看状态
./start-service.sh status

# 查看日志
./start-service.sh logs

# 显示 Token
./start-service.sh token
```

---

### 手动管理

```bash
# 查看进程
adb shell ps -A | grep autojs-api

# 查看端口
adb shell netstat -tlnp | grep 8899

# 查看日志
adb shell cat /sdcard/autojs-api.log

# 重启服务
adb shell "su -c 'pkill -f autojs-api-server.py; python3 /sdcard/autojs-api-server.py &'"
```

---

## 🔄 开机自启动

### 配置方式

服务已配置开机自启动，通过 Magisk 服务脚本实现：
- 脚本位置：`/data/adb/service.d/autojs-api-service.sh`
- 看门狗监控：每 30 秒检查服务状态，异常时自动重启

### Termux:Boot 配置

```bash
# 在 Termux 中配置
mkdir -p ~/.termux/boot
cp ~/autosignin/autojs-api-service/boot-start.sh ~/.termux/boot/
chmod +x ~/.termux/boot/boot-start.sh
```

### 测试自启动

```bash
# 手动测试启动脚本
./boot-start.sh

# 查看启动日志
cat ~/.telecom-api/boot-start.log
```

---

## 🔍 故障排查

### 服务无法访问

```bash
# 检查端口监听
adb shell "su -c 'netstat -tlnp | grep 8899'"

# 检查进程
adb shell "ps -A | grep python"

# 检查防火墙
adb shell "su -c 'iptables -L'"
```

---

### 脚本执行失败

```bash
# 查看 API 日志
adb shell cat /sdcard/autojs-api.log

# 查看 AutoJS 日志
adb shell logcat | grep AutoJS

# 检查脚本文件
adb shell ls -la /sdcard/脚本/
```

---

### 解锁失败

如果脚本执行时卡在锁屏界面，检查 `common_utils.js` 中的 `prepareDevice` 方法是否适配当前设备。

经测试验证，在 LineageOS 上使用 `input keyevent 82`（菜单键）可以成功解锁无密码设备。

---

### 看门狗不工作

```bash
# 查看看门狗日志
adb shell logcat -s AutoJS-API-Watchdog

# 检查看门狗进程
adb shell ps -A | grep watchdog
```

---

## 📊 监控与日志

### 日志位置

- **API 服务日志**: `/sdcard/autojs-api.log`
- **看门狗日志**: `/sdcard/autojs-api-watchdog.log`
- **logcat 日志**: `adb logcat -s AutoJS-API`

### 实时监控

```bash
# 实时查看 API 日志
adb shell tail -f /sdcard/autojs-api.log

# 实时查看 logcat
adb logcat -s AutoJS-API AutoJS-API-Watchdog
```

---

## 🔒 安全建议

1. **修改默认 API Token**
   ```bash
   # 生成新 Token
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   
   # 保存到配置文件
   echo "your-new-token" > ~/.autojs-api/api_token
   
   # 重启服务
   ./start-service.sh restart
   ```

2. **限制访问 IP**
   - 在路由器或防火墙层面限制
   - 只允许信任的 IP 访问

3. **定期查看日志**
   ```bash
   ./start-service.sh logs
   ```

4. **不要将 API Token 泄露给他人**

---

## 📁 项目结构

```
autojs-api-service/
├── autojs-api-server.py      # Python HTTP 服务器
├── autojs-api-watchdog.py    # Python 看门狗监控
├── magisk-service.sh         # Magisk 开机自启动脚本
├── test-autojs-api.py        # API 测试脚本
└── doc/
    ├── API 文档.md           # 详细 API 文档
    └── README.md             # 说明文档
```

---

## 🎯 技术细节

### 开机自启动原理

Magisk 在 `/data/adb/service.d/` 目录下的脚本会在系统启动完成后自动执行。`magisk-service.sh` 脚本：
1. 等待系统启动完成
2. 等待网络就绪
3. 启动 Python HTTP 服务器
4. 启动看门狗监控进程

### 看门狗监控

- **检查间隔**: 30 秒
- **检查方式**: 检测端口 8899 是否监听
- **重启策略**: 异常时自动重启，最大重启次数 5 次，重启间隔 60 秒

---

## 📚 相关文档

- [Autojs 远程执行.md](./Autojs 远程执行.md) - AutoJS 远程执行方案
- [AUTOJS_API_SERVICE_整合说明.md](./AUTOJS_API_SERVICE_整合说明.md) - 整合说明（历史文档）

---

**文档更新时间**: 2026-06-28  
**服务版本**: 1.0.0
