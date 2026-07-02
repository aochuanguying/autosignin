# Implementation Plan: Auto Init Panel

## Overview

为 Xray 管理面板的 `index.html` 添加自动初始化编排逻辑。在登录成功、会话恢复、点击刷新按钮三种场景下，自动并行执行连通性测试和配置加载，配置加载成功后自动解析路由规则。所有修改集中在 `xray-panel/www/xray-panel/index.html` 的 `<script>` 部分。

## Tasks

- [x] 1. 添加基础设施函数（执行守卫、超时控制、按钮状态管理）
  - [x] 1.1 在 `<script>` 中添加 `autoInitRunning` 全局变量和 `setRefreshButtonDisabled(disabled)` 函数
    - 添加 `let autoInitRunning = false;` 全局状态
    - 实现 `setRefreshButtonDisabled` 函数：通过选择器找到刷新按钮，设置 `disabled`、`opacity`、`pointerEvents` 属性
    - _Requirements: 3.3, 3.4_

  - [x] 1.2 修改现有 `api()` 函数，增加 AbortSignal 参数支持
    - 在 `api(action, data={})` 签名中添加第三个可选参数 `signal`
    - 在 `fetch` 调用的 options 中传入 `signal`
    - 保持向后兼容：不传 signal 时行为不变
    - _Requirements: 1.5, 5.3_

  - [x] 1.3 添加 `apiWithTimeout(action, data, timeout)` 带超时的 API 包装函数
    - 创建 AbortController，设置 setTimeout 在 30 秒后 abort
    - 捕获 AbortError 返回 `{ error: '请求超时' }`
    - 在 finally 中清除 timer
    - _Requirements: 1.5, 4.3_

- [x] 2. 实现安全包装函数（错误隔离层）
  - [x] 2.1 实现 `runTestsSafe()` 函数
    - 显示四个测试项的「测试中...」加载状态
    - 调用 `apiWithTimeout('test')` 执行测试
    - 检测 unauthorized 响应 → 调用 `doLogout()`
    - 成功时更新每个测试目标的 UI（复用现有 `runTests` 的结果渲染逻辑）
    - 失败时在对应项显示失败标记，不向上抛出错误
    - 返回 `{ success: boolean }`
    - _Requirements: 2.2, 5.1, 5.3_

  - [x] 2.2 实现 `loadConfigSafe()` 函数
    - 调用 `apiWithTimeout('config_get')` 加载配置
    - 检测 unauthorized 响应 → 调用 `doLogout()`
    - 成功时解码 base64 填入 `config-editor`，返回 `{ success: true }`
    - 失败时 toast 显示错误原因（至少 3 秒），返回 `{ success: false }`
    - _Requirements: 1.2, 4.3, 5.2_

  - [x] 2.3 实现 `loadRouteRulesSafe()` 函数
    - 从 `config-editor` 读取 JSON 并解析
    - 提取 `routing.rules` 中 outboundTag 为 office 和 direct 的规则
    - 填入四个路由规则编辑器 textarea
    - 解析失败时 toast 提示「路由规则解析失败」（至少 3 秒），编辑器保持空白
    - 返回 `{ success: boolean }`
    - _Requirements: 1.3, 4.2, 4.4, 5.4_

- [x] 3. 实现 `autoInit()` 编排主函数
  - [x] 3.1 实现 `autoInit()` 函数，管理并行执行和依赖链
    - 执行守卫检查：若 `autoInitRunning === true` 则直接 return
    - 设置 `autoInitRunning = true` 并禁用刷新按钮
    - 使用 `Promise` 并行启动 `runTestsSafe()` 和 `loadConfigSafe()`
    - `await configPromise`，若成功则链式调用 `loadRouteRulesSafe()`
    - `await testPromise` 等待测试完成
    - 在 `finally` 块中释放守卫、恢复按钮
    - _Requirements: 1.2, 1.3, 3.3, 3.4, 4.1, 4.2, 4.3_

- [x] 4. Checkpoint - 确保基础编排逻辑完整
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. 集成到现有触发点（Login、Session Restore、Refresh）
  - [x] 5.1 修改 `doLogin()` 函数
    - 登录成功后将 `refreshStatus()` 替换为 `autoInit()`
    - _Requirements: 1.1_

  - [x] 5.2 修改 `checkSession()` 函数
    - token 验证通过后调用 `autoInit()` 替代当前的手动加载逻辑
    - 保留 `loadGeodataStatus()` 调用
    - _Requirements: 2.1_

  - [x] 5.3 修改 `refreshStatus()` 函数
    - 改为并行执行：`api('status')` 刷新服务状态 + `autoInit()` 执行完整初始化
    - 保留 `updateStatus(res)` 调用
    - unauthorized 检测保留
    - _Requirements: 3.1, 3.2_

- [x] 6. Final checkpoint - 确保所有功能完整集成
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 所有修改集中在 `xray-panel/www/xray-panel/index.html` 的 `<script>` 标签内
- 无需修改后端 API（`xray-api` CGI 脚本）
- 无需安装依赖或设置构建工具
- 新增函数应放在现有 `api()` 函数之后、`doLogin()` 之前
- 保持与现有代码风格一致（async/await、无框架纯 JS）
- toast 函数已存在，直接复用

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 3, "tasks": ["3.1"] },
    { "id": 4, "tasks": ["5.1", "5.2", "5.3"] }
  ]
}
```
