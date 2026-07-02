# Requirements Document

## Introduction

Xray 管理面板的自动初始化功能。当用户成功登录或通过 token 恢复会话进入面板后，系统自动执行连通性测试、加载配置文件、加载路由规则，无需用户手动逐步点击。刷新按钮也触发同样的完整初始化流程。

## Glossary

- **Panel**: Xray 管理面板，运行在 OpenWrt 路由器上的单页 HTML 应用
- **Session_Restore**: 页面加载时通过 localStorage 中已有的 token 验证并恢复会话的过程
- **Login**: 用户输入密码后通过 API 获取新 token 的过程
- **Connectivity_Test**: 通过 API 的 `test` 操作对 Google、内网域名、内网 IP、百度四个目标执行网络连通性测试
- **Config_Load**: 通过 API 的 `config_get` 操作从路由器加载 Xray 配置文件到编辑器
- **Route_Rules_Load**: 从已加载的配置 JSON 中解析 routing.rules，提取 office 和 direct 规则填入路由规则编辑器
- **Auto_Init**: 自动依次执行 Connectivity_Test、Config_Load、Route_Rules_Load 的完整流程
- **Refresh_Button**: 面板顶部的「刷新」按钮

## Requirements

### 需求 1：登录后自动初始化

**用户故事：** 作为面板用户，我想在登录成功后自动看到连通性测试结果、配置文件内容和路由规则，这样我无需手动逐个点击加载按钮。

#### 验收标准

1. WHEN 用户输入正确密码并完成 Login，THE Panel SHALL 在 Login API 返回成功响应后 1 秒内自动启动 Auto_Init 流程
2. WHEN Auto_Init 流程执行时，THE Panel SHALL 并行执行 Connectivity_Test 和 Config_Load，并在 Config_Load 成功完成后执行 Route_Rules_Load
3. WHEN Config_Load 成功完成后，THE Panel SHALL 无需用户干预直接执行 Route_Rules_Load 以解析已加载的配置
4. WHILE Auto_Init 流程执行中，THE Panel SHALL 在各对应区域显示加载状态指示，直到该区域数据加载完成或失败
5. IF Auto_Init 中任一操作在 30 秒内未收到 API 响应，THEN THE Panel SHALL 终止该操作并在对应区域显示超时错误提示

### 需求 2：会话恢复后自动初始化

**用户故事：** 作为面板用户，我想在通过已有 token 恢复会话后自动加载所有数据，这样刷新浏览器页面不需要手动重新加载各项内容。

#### 验收标准

1. WHEN Session_Restore 验证 token 有效并进入面板，THE Panel SHALL 自动执行 Auto_Init 流程
2. WHEN Auto_Init 中 Connectivity_Test 执行时，THE Panel SHALL 在测试结果区域显示「测试中...」状态

### 需求 3：刷新按钮触发完整初始化

**用户故事：** 作为面板用户，我想在点击刷新按钮后重新加载所有数据（状态、连通性、配置、路由规则），这样一键即可获取最新全貌。

#### 验收标准

1. WHEN 用户点击 Refresh_Button，THE Panel SHALL 通过 API 的 `status` 操作刷新 Xray 服务运行状态，并同时触发 Auto_Init 流程（服务状态刷新与 Auto_Init 并行执行）
2. WHEN Refresh_Button 触发的 Auto_Init 完成时，THE Panel SHALL 将连通性测试结果、配置编辑器内容和路由规则编辑器内容替换为最新获取的数据
3. WHILE Auto_Init 流程正在执行中，IF 用户再次点击 Refresh_Button，THEN THE Panel SHALL 忽略此次点击，不触发新的刷新操作
4. WHEN 用户点击 Refresh_Button 后刷新操作开始执行时，THE Panel SHALL 将 Refresh_Button 置为禁用状态，直到所有刷新操作（服务状态刷新及 Auto_Init）均完成后恢复为可用状态

### 需求 4：初始化流程的执行顺序与依赖

**用户故事：** 作为面板用户，我想让自动加载按正确顺序执行，这样路由规则总是基于最新的配置内容来解析。

#### 验收标准

1. WHEN Auto_Init 流程启动时，THE Panel SHALL 同时发起 Connectivity_Test 和 Config_Load，两者不互相等待
2. WHEN Config_Load 成功完成，THE Panel SHALL 在 1 秒内开始执行 Route_Rules_Load
3. IF Config_Load 失败（API 返回错误或请求超时 30 秒），THEN THE Panel SHALL 跳过 Route_Rules_Load，并通过 toast 提示用户加载配置失败，toast 显示不少于 3 秒
4. IF Route_Rules_Load 解析失败（配置 JSON 中缺少 routing.rules 或目标规则不存在），THEN THE Panel SHALL 通过 toast 提示用户路由规则解析失败，路由规则编辑器保持为空

### 需求 5：初始化过程中的错误处理

**用户故事：** 作为面板用户，我想在自动初始化过程中某一步失败时得到提示，并且其他步骤不受影响继续执行。

#### 验收标准

1. IF Connectivity_Test 中任一测试目标请求失败或超时，THEN THE Panel SHALL 在该测试目标对应的结果项显示失败标记，其余测试目标的结果独立显示，且 Config_Load 继续正常执行
2. IF Config_Load 返回错误，THEN THE Panel SHALL 通过 toast 显示包含错误原因的提示信息，toast 持续显示至少 3 秒，且配置编辑器保持空白状态不加载内容
3. IF Auto_Init 过程中任一 API 请求返回 unauthorized，THEN THE Panel SHALL 立即终止所有正在执行的 Auto_Init 请求并执行退出登录流程
4. IF Route_Rules_Load 解析失败，THEN THE Panel SHALL 通过 toast 显示解析失败的提示信息，toast 持续显示至少 3 秒，且路由规则编辑器保持空白状态
