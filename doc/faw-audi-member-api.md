# 一汽奥迪 API 文档

## 概览

本文档包含两部分：
1. **Token 提取接口** — 从手机 APP 中提取有效的一汽奥迪 Access Token
2. **会员信息接口** — 使用 Token 调用一汽奥迪服务端获取会员信息

---

## 1. Token 提取接口（Android Telecom API 服务）

### GET `/api/v1/audi/token`

从已 root 手机上的一汽奥迪 APP WebView Cookies 数据库中提取当前有效的 Access Token。

**服务地址**: `http://10.6.0.2:5000`

**鉴权**: Bearer Token

#### 请求

```bash
curl -X GET "http://10.6.0.2:5000/api/v1/audi/token" \
  -H "Authorization: Bearer <TELECOM_API_TOKEN>"
```

#### 成功响应 (200)

```json
{
  "success": true,
  "data": {
    "token": "eyJraWQiOi...<JWT Access Token>",
    "source": "app_webview/Cookies (faw-vw.com)",
    "token_length": 1030
  }
}
```

#### 错误响应

| HTTP 状态码 | 场景 | 响应体 |
|------------|------|--------|
| 401 | Token 鉴权失败 | `{"success": false, "error": "Unauthorized", "message": "Invalid or missing API token"}` |
| 502 | APP Cookie 中未找到 Token | `{"success": false, "error": "Failed to extract token from APP cookies"}` |
| 502 | 提取内容非 JWT 格式 | `{"success": false, "error": "Extracted value is not a valid JWT token"}` |
| 500 | 服务异常 | `{"success": false, "error": "..."}` |

#### Token 特征

| 属性 | 值 |
|------|-----|
| 签发方 | `https://audiidp.faw-vw.com` |
| 类型 | Access Token (`type: "AT"`) |
| 有效期 | ~83 小时（约 3.5 天） |
| 续期方式 | APP 打开时自动续期（更新 WebView Cookie） |
| 存储位置 | `/data/data/com.timanetworks.android.frame.audisuper.release/app_webview/Default/Cookies` |

#### Token JWT Payload 示例

```json
{
  "sub": "33946831",
  "scp": "openid profile audi",
  "iss": "https://audiidp.faw-vw.com",
  "type": "AT",
  "tnt": "AUDI_APP_MI6_71b9145c3894701e_Android13_6.2.0",
  "exp": 1784993708,
  "aid": "33946831",
  "iat": 1784693708,
  "jti": "497cbd4d-8627-4cd6-b690-d9334aaca79a",
  "rt-id": "ebbc160b-23d3-4e2d-acd9-10f838edace7"
}
```

---

## 2. 会员信息接口（一汽奥迪服务端）

### GET `/mapi/member/v1/member/info`

**Base URL**: `https://audi2c.faw-vw.com`

**完整地址**: `https://audi2c.faw-vw.com/mapi/member/v1/member/info`

**超时**: 10000ms

#### 请求头

| Header | 值 | 说明 |
|--------|------|------|
| `content-type` | `application/json` | - |
| `x-access-token` | `{accessToken}` | 从 Token 提取接口获取 |
| `x-channel` | `MINI_PROGRAM` | 渠道标识 |
| `x-microservice-name` | `audi-app-gateway-c` | 微服务名 |
| `x-namespace-code` | `faw-audi-dev` | 命名空间 |
| `x-timestamp` | `{timestamp}` | 当前时间戳（毫秒） |

#### 请求示例

```bash
TOKEN=$(curl -s -H "Authorization: Bearer <TELECOM_API_TOKEN>" \
  http://10.6.0.2:5000/api/v1/audi/token | jq -r '.data.token')

curl -X GET "https://audi2c.faw-vw.com/mapi/member/v1/member/info" \
  -H "content-type: application/json" \
  -H "x-access-token: $TOKEN" \
  -H "x-channel: MINI_PROGRAM" \
  -H "x-microservice-name: audi-app-gateway-c" \
  -H "x-namespace-code: faw-audi-dev" \
  -H "x-timestamp: $(date +%s000)"
```

#### 成功响应

```json
{
  "code": 0,
  "data": {
    "memberLevel": "金卡会员",
    "memberScore": 536,
    "memberGrowthInfoRespDto": {
      "memberId": 1320721310,
      "aid": 33946831,
      "growthValue": 9213,
      "currentLevel": "金卡",
      "upNeedGrowth": 787,
      "lastChangeLevelTime": "2024-10-08 06:04:36",
      "createTime": "2024-06-17 10:14:22",
      "updateTime": "2026-06-22 02:03:46"
    }
  }
}
```

#### 错误响应

| code | message | 说明 |
|------|---------|------|
| 10009 | 请您重新登录系统 | Token 已过期或无效 |

---

## 3. Token 续期机制

- 调用会员信息接口会触发 Token 滑动续期（服务端通过响应头 `x-access-token` 返回新 Token）
- APP 每次打开时也会自动续期 Cookie 中的 Token
- 续期成功后，Token 过期时间重置为 ~83 小时
- **建议**：每天至少提取一次 Token，确保不过期

---

## 4. 完整调用流程

```
┌──────────┐     GET /api/v1/audi/token     ┌──────────────┐
│  调用方   │ ─────────────────────────────► │ Android 手机  │
│          │ ◄───────────────────────────── │ (Telecom API) │
│          │      { token: "eyJ..." }        │  port: 5000   │
│          │                                 └──────────────┘
│          │                                        │
│          │     GET /mapi/member/v1/member/info     │ 读取 WebView
│          │ ─────────────────────────────────────► │ Cookies DB
│          │       x-access-token: eyJ...           │
│          │                                 ┌──────▼──────┐
│          │ ◄─────────────────────────────  │ 一汽奥迪服务端 │
│          │    { memberLevel, score, ... }   │audi2c.faw-vw│
└──────────┘                                 └─────────────┘
```

---

## 5. 相关文件

| 文件 | 说明 |
|------|------|
| `android-telecom-api/server.py` | Token 提取 API 实现（`/api/v1/audi/token`） |
| `doc/Android Telecom API 服务文档.md` | Telecom API 完整服务文档 |

---

**文档更新**: 2026-07-23
