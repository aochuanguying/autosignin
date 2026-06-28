# Android 初始化配置指南

## 📋 目录

1. [Magisk & LSPosed 故障排查](#magisk--lsposed-故障排查)
2. [SSH 服务配置](#ssh-服务配置)
3. [WireGuard 服务配置](#wireguard-服务配置)
4. [开机自启动方案](#开机自启动方案)
5. [常用诊断命令](#常用诊断命令)

---

## Part 1: Magisk & LSPosed 故障排查

### 🔍 Magisk App 无法打开问题

#### 问题现象

Magisk App 打开后提示"需要下载完整版 Magisk 才能正常打开"，点击下载会卡死很久。手工安装最新版 APK 后，点击打开仍然异常（闪退/消失）。

---

#### 问题分析

**核心发现**：Magisk Daemon (v30.7) 在主动替换 App！

**完整流程**:
1. 用户打开了手动安装的 Magisk App（无论哪个版本）
2. Magisk 守护进程（daemon v30.7）检测到 App 版本与自身不匹配
3. Daemon 强制卸载当前 App（`pm_uninstall`）
4. Daemon 从 `/data/stub.apk` 重新安装 stub 版本（`pm_install: /data/stub.apk`）
5. 导致用户看到的现象就是 App 闪退/消失

**这不是 App 崩溃**（logcat 中没有 FATAL EXCEPTION 或 crash stack trace），而是 daemon 主动触发了卸载 + 重装 stub 的流程。

---

#### 日志分析

```log
06-16 21:29:49.098 I/Magisk  (15414): pm_install: /data/stub.apk
06-16 21:29:49.122 I/ActivityManager: Force stopping com.topjohnwu.magisk appid=10273 user=-1: deletePackageX
06-16 21:29:49.128 I/ActivityManager: Killing 15384:com.topjohnwu.magisk/u0a273 (adj 0): stop com.topjohnwu.magisk due to deletePackageX
06-16 21:29:49.254 I/Magisk  (15435): pm_uninstall: Success
...
06-16 21:29:51.499 I/Magisk  (15492): pm_install: Success
```

**关键日志**：
```
E/Magisk  (974): pkg: APK signature mismatch: /data/app/.../com.topjohnwu.magisk-.../base.apk 
W/Magisk  (974): su: request rejected (10275) 
I/Magisk  (16352): pm_uninstall: com.topjohnwu.magisk 
I/Magisk  (16354): pm_install: /data/stub.apk 
```

**真正的问题**：APK 签名不匹配！

Magisk daemon 中保存了一个签名指纹（可能是之前安装时的签名），而从 GitHub 下载的官方 APK 签名与之不同。Daemon 因此：
1. 拒绝授予 root 权限（`su: request rejected`）
2. 判定这是一个"假的"Magisk App
3. 立即卸载并用 `stub.apk` 替换

---

#### 解决方案

##### 方案一：安装版本匹配的 APK（推荐）

```bash
# 1. 下载与 daemon 版本匹配的 APK
# 当前 daemon 版本：v30.7
curl -L -o /tmp/Magisk-v30.7.apk "https://github.com/topjohnwu/Magisk/releases/download/v30.7/Magisk-v30.7.apk"

# 2. 卸载当前 App
adb shell "pm uninstall com.topjohnwu.magisk"

# 3. 安装匹配的 APK
adb install /tmp/Magisk-v30.7.apk

# 4. 验证版本
adb shell "dumpsys package com.topjohnwu.magisk | grep -E 'versionCode|versionName'"
# 应该返回：versionCode=30700 versionName=30.7
```

---

##### 方案二：清除 Magisk 配置数据库

```bash
# 在 Termux 中执行（需要 root）
su

# 删除 magisk.db（Magisk 配置数据库）
rm -f /data/adb/magisk.db

# 删除 stub.apk（如果存在）
rm -f /data/stub.apk

# 重启设备
reboot
```

**重启后重新安装官方 APK**:
```bash
adb install /tmp/Magisk-v30.7.apk
```

---

##### 方案三：降级 Magisk（如果以上都不行）

如果签名验证仍然失败，可能需要降级到更稳定的版本：

```bash
# 下载 Magisk v28.1
curl -L -o /tmp/Magisk-v28.1.apk "https://github.com/topjohnwu/Magisk/releases/download/v28.1/Magisk-v28.1.apk"

# 安装
adb install -r /tmp/Magisk-v28.1.apk
```

---

#### 验证修复

```bash
# 检查 su 权限
adb shell "su -c 'id'"
# 应该返回：uid=0(root) gid=0(root) ...

# 检查 App 版本
adb shell "dumpsys package com.topjohnwu.magisk | grep -E 'versionCode|versionName'"
# 应该返回：versionCode=30700 versionName=30.7

# 打开 App 测试
# 应该能正常打开，不再闪退
```

---

### 💥 LSPosed 崩溃问题

#### 问题描述

- 设备：小米 9 (MI 9)
- 系统：Android 14
- 已刷入：LSPosed-v1.9.2-7024-zygosis-release.zip（Zygisk 模块）
- 问题：尝试打开 LSPosed 时崩溃或提示错误

---

#### 崩溃原因分析

从日志中发现的确切崩溃原因：

```
E/LSPosed ( 6431): Failed to init lsplant
F/libc    ( 6431): Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
```

**问题**：LSPosed v1.9.2 在初始化 lsplant（hook 框架）时崩溃了。

**根本原因**：LSPosed v1.9.2 与 Magisk v30.7 或 Android 14 存在兼容性问题。

---

#### 解决方案

##### 方案一：升级到最新版 LSPosed（推荐）

LSPosed 已经发布了更新版本来修复这个问题。

**步骤**：

1. **下载最新版 LSPosed：**
   - 访问：https://github.com/LSPosed/LSPosed/releases
   - 下载最新的 `LSPosed-vx.x.x-xxxx-zygosis-release.zip`（不是 APK）

2. **在 Magisk 中刷入：**
   - 打开 Magisk 应用
   - 进入"模块"页面
   - 点击"从本地安装"
   - 选择下载的最新版 zip 文件
   - 等待刷入完成

3. **重启设备：**
   ```bash
   adb reboot
   ```

4. **使用拨号代码打开：**
   - 重启后在拨号界面输入：`*#*#5776733#*#*`

---

##### 方案二：降级到 LSPosed v1.9.1 或 v1.9.0

如果最新版还有问题，可以尝试旧版本：

**降级到 v1.9.1**:
1. 访问：https://github.com/LSPosed/LSPosed/releases/tag/v1.9.1
2. 下载：`LSPosed-v1.9.1-6992-zygosis-release.zip`
3. 在 Magisk 中卸载当前 LSPosed
4. 重启
5. 刷入 v1.9.1 版本
6. 再次重启

**降级到 v1.9.0**:
1. 访问：https://github.com/LSPosed/LSPosed/releases/tag/v1.9.0
2. 下载：`LSPosed-v1.9.0-6970-zygosis-release.zip`
3. 重复上述步骤

---

##### 方案三：检查 Zygisk 是否正确启用

确保 Zygisk 在 Magisk 中已启用：

1. 打开 Magisk 应用
2. 进入"设置"页面
3. 找到"Zygisk"选项
4. 确保它已**开启**
5. 如果之前是关闭的，开启后需要重启

---

##### 方案四：降级 Magisk 版本（如果以上都不行）

Magisk v30.7 可能与某些 LSPosed 版本存在兼容性问题。

1. 访问：https://github.com/topjohnwu/Magisk/releases
2. 下载 Magisk v28.1 或 v27.0
3. 参考 Magisk 降级指南操作

---

#### 验证修复

修复成功后，应该能看到：
- LSPosed 界面正常打开
- 显示"Zygisk：已激活"
- 框架版本显示正常
- 不再崩溃

---

### 🎯 LSPosed 无法访问问题

#### 好消息！您的 LSPosed 其实已经正常工作了！

根据诊断，LSPosed Zygisk 模块已正确安装并运行！**您不需要再安装任何东西！** LSPosed 管理器 APK 实际上已经包含在模块中了。

---

#### 访问 LSPosed 的 3 种方法

##### 方法 1：通过通知栏（最简单）

1. 下拉手机通知栏
2. 查找 "LSPosed" 通知
3. 点击通知即可打开 LSPosed

---

##### 方法 2：通过拨号代码（推荐）

在手机拨号界面输入：
```
*#*#5776733#*#*
```

（"5776733" 对应 "LSPOSED"）

输入后会自动打开 LSPosed 管理器！

---

##### 方法 3：从模块路径提取 APK（高级）

如果需要 APK 文件，可以在手机上：

1. 使用 Root 文件管理器（如 Root Explorer、MT 管理器等）
2. 访问路径：`/data/adb/lspd/manager.apk`
3. 点击安装此 APK

---

#### 验证 LSPosed 是否正常工作

##### 步骤 1：检查模块状态

1. 打开 Magisk 应用
2. 进入 "模块" 页面
3. 确认 "LSPosed" 模块显示为 **已激活**

##### 步骤 2：使用拨号代码打开

在拨号界面输入 `*#*#5776733#*#*`

应该能看到 LSPosed 界面，显示：
- Zygisk 状态：已激活
- 框架版本：1.9.2 (7024)

---

#### 如果还是无法访问

##### 1. 重启设备

有时候需要重启才能让 LSPosed 完全激活：

```bash
adb reboot
```

重启后再次尝试拨号代码。

##### 2. 检查模块是否正确安装

在 Magisk 中确认 LSPosed 模块已启用。

##### 3. 重新刷入模块

如果问题持续：

1. 在 Magisk 中卸载 LSPosed 模块
2. 重启设备
3. 重新刷入 LSPosed zip 文件
4. 再次重启

---

#### 常见问题

**Q: 为什么刷入 zip 后没有应用图标？**  
A: LSPosed 设计为不显示常规应用图标，而是通过通知栏或拨号代码访问。

**Q: 拨号代码没反应怎么办？**  
A: 确保：
- LSPosed 模块在 Magisk 中已激活
- 已重启过设备
- 尝试在不同的拨号应用中输入（如系统自带拨号器）

**Q: LSPosed 和 EdXposed 有什么区别？**  
A: LSPosed 是 EdXposed 的继任者，更稳定、更现代，支持 Android 8.1-14。

**Q: 需要安装额外的 APK 吗？**  
A: **不需要！** 管理器已经包含在模块中了，通过拨号代码访问即可。

---

## Part 2: SSH 服务配置

### 📁 SSH 脚本总览

| 序号 | 脚本名称 | 文件路径 | 类型 | 用途 |
|------|----------|----------|------|------|
| 1 | `termux-ssh.sh` | `/shell/termux-ssh.sh` | Shell | Magisk 开机自启动 |
| 2 | `sshd-watchdog.sh` | `/shell/sshd-watchdog.sh` | Shell | SSH 看门狗监控 |
| 3 | `start-sshd` | `/shell/termux-boot/start-sshd` | Shell | Termux Boot 直接启动 |
| 4 | `watchdog` | `/shell/termux-boot/watchdog` | Shell | Termux Boot 启动多个看门狗 |

---

### 1️⃣ SSH 开机自启动脚本

**文件名称**: `termux-ssh.sh`  
**文件路径**: `/shell/termux-ssh.sh`

**用途**: Magisk/Android 开机自启动脚本，系统启动后自动启动 Termux SSH 服务

**特点**: 
- 等待系统完全启动
- 等待存储挂载
- 启动 Termux 应用确保环境就绪
- 以正确的用户身份 (u0_a167) 启动 SSH 服务

**完整源码**:

```bash
#!/system/bin/sh

# Termux SSH 开机自启动脚本

LOG_TAG="Termux-SSH"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "=== Termux SSH 启动 ==="

# 等待系统完全启动
while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 5
done

# 等待存储挂载
sleep 30

log "启动 Termux 应用"

# 启动 Termux 应用（确保环境就绪）
am start --user 0 com.termux/com.termux.app.TermuxApp >/dev/null 2>&1 || true
sleep 10  # 等待 Termux 完全启动

log "启动 SSH 服务"

# 以 u0_a167 用户身份启动 SSH（关键：使用 su - 用户 -c 方式）
su u0_a167 -c '/data/data/com.termux/files/usr/bin/sshd' >/dev/null 2>&1 &

sleep 8

if pgrep -f sshd >/dev/null 2>&1; then
    log "✓ SSH 启动成功"
else
    log "✗ SSH 启动失败"
fi

log "=== Termux SSH 启动完成 ==="
```

---

### 2️⃣ SSH 看门狗监控脚本

**文件名称**: `sshd-watchdog.sh`  
**文件路径**: `/shell/sshd-watchdog.sh`

**用途**: 持续监控 SSH 服务状态，检测到 SSH 服务停止时自动重启

**特点**: 
- 每 30 秒检查一次 SSH 进程
- 启动失败时自动重试（最多 3 次）
- 重试间隔 2 秒
- 使用 logcat 记录日志

**完整源码**:

```bash
#!/system/bin/sh
# SSH 看门狗脚本
# 用途：持续监控 SSH 服务，挂掉自动重启

LOG_TAG="SSHD-Watchdog"
SSHD_PATH="/data/data/com.termux/files/usr/bin/sshd"
CHECK_INTERVAL=30  # 每 30 秒检查一次
MAX_RETRY=3        # 最大重试次数
RETRY_DELAY=2      # 重试间隔（秒）

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "启动 SSH 看门狗"
log "检查间隔：${CHECK_INTERVAL}秒"

# 等待系统完全启动
sleep 60

while true; do
    if ! pgrep -f sshd >/dev/null 2>&1; then
        log "⚠ 检测到 SSH 未运行，准备启动..."
        
        # 尝试启动 SSH，最多重试 MAX_RETRY 次
        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "  启动尝试 $i/$MAX_RETRY"
            $SSHD_PATH
            sleep 8
            
            if pgrep -f sshd >/dev/null 2>&1; then
                log "✓ SSH 启动成功"
                success=1
                break
            else
                log "  启动失败，${RETRY_DELAY}秒后重试..."
                sleep "$RETRY_DELAY"
            fi
        done
        
        if [ $success -eq 0 ]; then
            log "✗ SSH 启动失败，将在下次循环继续尝试"
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
```

---

### 3️⃣ Termux Boot 启动脚本

#### 3.1 SSH 直接启动脚本

**文件名称**: `start-sshd`  
**文件路径**: `/shell/termux-boot/start-sshd`

**用途**: 被 Termux:Boot 应用在系统启动后执行，直接启动 SSH 服务

**特点**: 
- 简单直接
- 使用 termux-wake-lock 保持唤醒
- 适合不需要复杂逻辑的场景

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/sh
# Termux SSH 启动脚本

LOG_TAG="Termux-SSH"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "启动 SSH 服务"
termux-wake-lock
/data/data/com.termux/files/usr/bin/sshd

if pgrep -f sshd >/dev/null 2>&1; then
    log "✓ SSH 启动成功"
else
    log "✗ SSH 启动失败"
fi
```

#### 3.2 综合看门狗启动脚本

**文件名称**: `watchdog`  
**文件路径**: `/shell/termux-boot/watchdog`

**用途**: 被 Termux:Boot 应用在系统启动后执行，同时启动 WireGuard 和 SSH 看门狗服务

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/bash
# 看门狗服务启动脚本（Termux:Boot）
# 用途：开机启动 AutoJS6、WireGuard 和 SSH 看门狗服务

LOG_TAG="Watchdog-Boot"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "=== 看门狗服务启动 ==="

# 等待系统完全启动
sleep 60

log "启动 WireGuard 看门狗..."

# 启动 WireGuard 看门狗（从 service.d 目录）
nohup /system/bin/sh /data/adb/service.d/wireguard-watchdog.sh >/dev/null 2>&1 &
WG_PID=$!

sleep 2

log "启动 SSH 看门狗..."

# 启动 SSH 看门狗（从 service.d 目录）
nohup /system/bin/sh /data/adb/service.d/sshd-watchdog.sh >/dev/null 2>&1 &
SSH_PID=$!

sleep 2

log "✓ 所有看门狗服务已启动"
log "WireGuard PID: $WG_PID"
log "SSHD PID: $SSH_PID"
log "=== 看门狗服务启动完成 ==="
```

---

### 4️⃣ SSH 部署说明

#### 方案一：使用 Magisk service.d（推荐）

适用于已 root 的设备，使用 Magisk 管理开机自启动。

**部署步骤**:

```bash
# 1. 推送 SSH 启动脚本
adb push shell/termux-ssh.sh /data/adb/service.d/termux-ssh.sh
adb shell chmod +x /data/adb/service.d/termux-ssh.sh

# 2. 推送 SSH 看门狗脚本
adb push shell/sshd-watchdog.sh /data/adb/service.d/sshd-watchdog.sh
adb shell chmod +x /data/adb/service.d/sshd-watchdog.sh

# 3. 重启设备验证
adb reboot
```

---

#### 方案二：使用 Termux:Boot

适用于安装了 Termux:Boot 插件的设备。

**部署步骤**:

```bash
# 1. 在 Termux 中创建 boot 目录
mkdir -p ~/.termux/boot

# 2. 复制 SSH 启动脚本
cp ~/autosignin/shell/termux-boot/start-sshd ~/.termux/boot/

# 3. 设置执行权限
chmod +x ~/.termux/boot/start-sshd

# 4. 重启设备验证
```

---

#### 方案三：组合部署（最完整）

结合 Magisk 和 Termux:Boot 的优势，实现多层保障。

**部署架构**:
- **Magisk service.d**: 部署 SSH 启动脚本和看门狗
- **Termux:Boot**: 部署备用启动脚本和综合看门狗

**部署步骤**:

```bash
# 1. 部署 Magisk 服务
adb push shell/termux-ssh.sh /data/adb/service.d/termux-ssh.sh
adb shell chmod +x /data/adb/service.d/termux-ssh.sh

adb push shell/sshd-watchdog.sh /data/adb/service.d/sshd-watchdog.sh
adb shell chmod +x /data/adb/service.d/sshd-watchdog.sh

# 2. 部署 Termux Boot 脚本
mkdir -p ~/.termux/boot
cp ~/autosignin/shell/termux-boot/watchdog ~/.termux/boot/
chmod +x ~/.termux/boot/watchdog
```

---

### 5️⃣ SSH 日志查看

```bash
# 查看 SSH 启动日志
adb logcat -s Termux-SSH

# 查看 SSH 看门狗日志
adb logcat -s SSHD-Watchdog

# 查看 SSH 进程状态
adb shell ps | grep sshd

# 检查 SSH 端口（默认 8022）
adb shell netstat -tlnp | grep 8022
```

---

## Part 3: WireGuard 服务配置

### 📁 WireGuard 脚本总览

| 序号 | 脚本名称 | 文件路径 | 类型 | 用�� |
|------|----------|----------|------|------|
| 1 | `wireguard-connect.js` | `/scripts/wireguard-connect.js` | AutoJS6 | UI 自动化连接隧道 |
| 2 | `wireguard-boot.sh` | `/shell/wireguard-boot.sh` | Shell | 开机自启动 |
| 3 | `wireguard-watchdog.sh` | `/shell/wireguard-watchdog.sh` | Shell | 完整看门狗监控 |
| 4 | `wireguard-simple-watchdog.sh` | 根目录 | Shell | 简单看门狗 |
| 5 | `wireguard-watchdog-new.sh` | 根目录 | Shell | 新版看门狗（Magisk 服务） |

---

### 🌐 WireGuard 网络配置

| 配置项 | 值 |
|--------|-----|
| 隧道名称 | `be86u` |
| 本地 IP | `10.6.0.2` |
| 网关 IP | `10.6.0.1` |
| 接口名称 | `tun0` |

---

### 1️⃣ AutoJS6 连接脚本

**文件名称**: `wireguard-connect.js`  
**文件路径**: `/scripts/wireguard-connect.js`

**用途**: 通过 UI 自动化点击 WireGuard 应用的隧道开关来建立连接

**被调用方式**: 被 Shell 看门狗脚本调用执行

**完整源码**:

```javascript
// AutoJS6 脚本 - WireGuard be86u 一次性连接脚本
// 用途：被 Shell 脚本调用，执行一次连接操作
"auto";

var CONFIG = {
  tunnelName: "be86u",
  targetIP: "10.6.0.2",
  gatewayIP: "10.6.0.1",
  wgPackage: "com.wireguard.android",
  wgAppName: "WireGuard",
  tunnelSwitchId: "tunnel_switch",
  maxAttempts: 3,
  retryDelayMs: 3000,
  connectionWaitMs: 15000
};

auto.waitFor();

console.log("=== WireGuard 连接脚本（被调用）===");

function execShell(cmd) {
  var result = {code: 1, result: ""};
  try {
    var process = shell(cmd, true);
    result.code = process.code;
    result.result = String(process.result);
  } catch (e) {
    result.result = e.toString();
  }
  return result;
}

function checkConnection() {
  try {
    var ipResult = execShell("ip addr show tun0");
    if (ipResult.code !== 0 || ipResult.result.indexOf("tun0") === -1) {
      return false;
    }
    if (ipResult.result.indexOf(CONFIG.targetIP) === -1) {
      return false;
    }
    var pingResult = execShell("ping -c 1 -W 5 " + CONFIG.gatewayIP);
    if (pingResult.code !== 0) {
      return false;
    }
    return true;
  } catch (e) {
    return false;
  }
}

function connect() {
  console.log("1. 打开 WireGuard 应用");
  launchApp(CONFIG.wgAppName);
  sleep(3000);
  
  console.log("2. 查找开关控件");
  var switchWidget = id(CONFIG.tunnelSwitchId).findOne(5000);
  
  if (!switchWidget) {
    console.log("   尝试通过隧道名称查找...");
    var tunnelItem = text(CONFIG.tunnelName).findOne(5000);
    if (tunnelItem) {
      var parent = tunnelItem.parent();
      if (parent) {
        switchWidget = parent.findOne(id(CONFIG.tunnelSwitchId));
      }
    }
  }
  
  if (!switchWidget) {
    console.log("✗ 未找到开关控件");
    return false;
  }
  
  console.log("✓ 找到开关");
  
  var isChecked = switchWidget.checked();
  console.log("当前状态：" + (isChecked ? "已连接" : "已断开"));
  
  if (isChecked) {
    console.log("已经是连接状态");
    return true;
  }
  
  console.log("3. 点击连接开关");
  try {
    switchWidget.click();
    console.log("✓ 点击成功");
  } catch (e) {
    console.log("✗ 点击失败：" + e.message);
    return false;
  }
  
  console.log("4. 等待连接 (" + (CONFIG.connectionWaitMs / 1000) + "秒)");
  var checkCount = Math.floor(CONFIG.connectionWaitMs / 1000);
  for (var i = 0; i < checkCount; i++) {
    sleep(1000);
    if (checkConnection()) {
      console.log("✓ 连接成功");
      return true;
    }
    if ((i + 1) % 5 === 0) {
      console.log("   等待中... " + (i + 1) + "s");
    }
  }
  
  console.log("✗ 连接���时");
  return false;
}

function main() {
  console.log("检查当前连接状态...");
  if (checkConnection()) {
    console.log("✓ 已经连接，无需操作");
    exit();
  }
  
  console.log("✗ 检测到断联，准备连接");
  
  var success = false;
  for (var i = 0; i < CONFIG.maxAttempts; i++) {
    console.log("\n尝试 " + (i + 1) + "/" + CONFIG.maxAttempts);
    if (connect()) {
      success = true;
      break;
    }
    if (i < CONFIG.maxAttempts - 1) {
      console.log("等待 " + (CONFIG.retryDelayMs / 1000) + "秒后重试...");
      sleep(CONFIG.retryDelayMs);
    }
  }
  
  console.log("\n=== 执行完成 ===");
  if (success) {
    console.log("✓ 连接成功");
  } else {
    console.log("✗ 连接失败");
  }
  
  home();
}

main();
```

---

### 2️⃣ WireGuard 开机自启动脚本

**文件名称**: `wireguard-boot.sh`  
**文件路径**: `/shell/wireguard-boot.sh`

**用途**: Magisk/Android 开机自启动脚本，系统启动后自动连接 WireGuard

**完整源码**:

```bash
#!/system/bin/sh
# WireGuard be86u 开机自启动脚本

LOG_TAG="WireGuard-Boot"
TARGET_IP="10.6.0.2"

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

log "等待系统完全启动..."

while [ "$(getprop sys.boot_completed)" != "1" ]; do
    sleep 5
done

sleep 25

log "启动 WireGuard 应用"

am start -n com.wireguard.android/.activity.MainActivity >/dev/null 2>&1
sleep 3

log "启动 be86u 隧道"
am broadcast --user 0 -a com.wireguard.android.action.SET_TUNNEL_STATE \
    -e com.wireguard.android.extra.TUNNEL_NAME be86u \
    -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1
sleep 5

if ip addr show tun0 2>/dev/null | grep -q "$TARGET_IP"; then
    log "✓ WireGuard 隧道启动成功"
else
    log "⚠ 隧道可能未启动，看门狗将自动重连"
fi
```

---

### 3️⃣ WireGuard 看门狗监控脚本

#### 3.1 完整版看门狗

**文件名称**: `wireguard-watchdog.sh`  
**文件路径**: `/shell/wireguard-watchdog.sh`

**用途**: 持续监控 WireGuard 隧道状态，断开时自动重连

**特点**: 
- 两阶段重连策略（广播快速尝试 → AutoJS 可靠方式）
- 最大重试 3 次，重试间隔 50 秒
- 每 30 秒检查一次

**完整源码**:

```bash
#!/system/bin/sh
# WireGuard be86u 看门狗脚本（真正版本）
# 用途：持续监控 WireGuard 隧道状态，断开自动重连

LOG_TAG="WireGuard-Watchdog"
TUNNEL_NAME="be86u"
TARGET_IP="10.6.0.2"
CHECK_INTERVAL=30
MAX_RETRY=3
RETRY_DELAY=50

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

check_tunnel() {
    if ip addr show tun0 2>/dev/null | grep -q "$TARGET_IP"; then
        return 0
    fi
    return 1
}

start_tunnel() {
    log "  方法 1: 发送广播..."
    am broadcast --user 0 \
        -a com.wireguard.android.action.SET_TUNNEL_STATE \
        -e com.wireguard.android.extra.TUNNEL_NAME "$TUNNEL_NAME" \
        -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1
    
    for j in $(seq 1 5); do
        sleep 2
        if check_tunnel; then
            log "✓ 广播方式启动成功"
            return 0
        fi
        log "  等待广播生效... ($((j * 2))/10 秒)"
    done
    
    log "  广播方式未成功"
    log "  方法 2: AutoJS 脚本..."
    am start -n org.autojs.autojs6/org.autojs.autojs.external.open.RunIntentActivity \
        -a android.intent.action.VIEW \
        -d "file:///sdcard/脚本/wireguard-connect.js" \
        -t "application/x-javascript" >/dev/null 2>&1
    
    for j in $(seq 1 8); do
        sleep 5
        if check_tunnel; then
            log "✓ AutoJS 方式启动成功"
            return 0
        fi
        log "  等待 AutoJS 执行... ($((j * 5))/40 秒)"
    done
    
    log "✗ AutoJS 方式超时"
    return 1
}

log "看门狗启动 - 监控隧道：$TUNNEL_NAME"
log "检查间隔：${CHECK_INTERVAL}秒"

sleep 60

while true; do
    if check_tunnel; then
        sleep "$CHECK_INTERVAL"
    else
        log "⚠ 检测到隧道断开！准备重连..."
        
        success=0
        for i in $(seq 1 $MAX_RETRY); do
            log "重试 $i/$MAX_RETRY"
            if start_tunnel; then
                success=1
                break
            fi
            log "等待 ${RETRY_DELAY}秒后重试..."
            sleep "$RETRY_DELAY"
        done
        
        if [ $success -eq 0 ]; then
            log "✗ 重连失败，将在下次循环继续尝试"
        fi
    fi
done
```

---

#### 3.2 简单版看门狗

**文件名称**: `wireguard-simple-watchdog.sh`  
**文件路径**: 根目录

**特点**: 
- 仅检查 tun0 接口是否存在
- 每 10 秒检查一次
- 重连方式：启动应用 + 发送广播

**完整源码**:

```bash
#!/system/bin/sh
# WireGuard be86u 简单看门狗脚本

LOG_TAG="WireGuard-Watchdog"
CHECK_INTERVAL=10

log() {
    /system/bin/log -t "$LOG_TAG" "$1"
}

check_tunnel() {
    if ip link show tun0 >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

start_tunnel() {
    log "检测到隧道断开，启动 AutoJS 连接脚本..."
    
    am start -n org.autojs.autojs6/org.autojs.autojs.ui.main.MainActivity >/dev/null 2>&1
    sleep 2
    
    am start -n com.wireguard.android/.activity.MainActivity >/dev/null 2>&1
    sleep 3
    
    am broadcast --user 0 \
        -a com.wireguard.android.action.SET_TUNNEL_STATE \
        -e com.wireguard.android.extra.TUNNEL_NAME be86u \
        -e com.wireguard.android.extra.TUNNEL_STATE true >/dev/null 2>&1
    
    sleep 5
    
    if check_tunnel; then
        log "✓ WireGuard 隧道启动成功"
        return 0
    else
        log "✗ WireGuard 隧道启动失败"
        return 1
    fi
}

log "看门狗启动 - 监控隧道：be86u"
log "检查间隔：${CHECK_INTERVAL}秒"

sleep 30

while true; do
    if check_tunnel; then
        sleep "$CHECK_INTERVAL"
    else
        log "⚠ 检测到隧道断开！"
        start_tunnel
        sleep "$CHECK_INTERVAL"
    fi
done
```

---

### 4️⃣ WireGuard 部署说明

#### 部署位置

1. **AutoJS6 脚本** (`wireguard-connect.js`)
   - 部署位置：`/sdcard/脚本/wireguard-connect.js`
   - 确保 AutoJS6 有 root 权限和无障碍权限

2. **开机自启动脚本** (`wireguard-boot.sh`)
   - 部署位置：`/data/adb/service.d/wireguard-boot.sh`
   - 需要 Magisk 环境
   - 设置执行权限：`chmod +x /data/adb/service.d/wireguard-boot.sh`

3. **看门狗脚本** (选择其中一个版本)
   - 推荐版本：`wireguard-watchdog.sh`
   - 部署位置：`/data/adb/service.d/wireguard-watchdog.sh`
   - 设置执行权限：`chmod +x /data/adb/service.d/wireguard-watchdog.sh`

#### 部署步骤

```bash
# 1. 推送 AutoJS6 脚本到手机
adb push scripts/wireguard-connect.js /sdcard/脚本/

# 2. 推送看门狗脚本到 Magisk 服务目录
adb push shell/wireguard-watchdog.sh /data/adb/service.d/wireguard-watchdog.sh
adb shell chmod +x /data/adb/service.d/wireguard-watchdog.sh

# 3. 查看日志确认脚本运行
adb logcat -s WireGuard-Watchdog
```

---

### 5️⃣ WireGuard 日志查看

```bash
# 查看 WireGuard 看门狗日志
adb logcat -s WireGuard-Watchdog

# 查看 WireGuard 启动日志
adb logcat -s WireGuard-Boot

# 查看所有相关日志
adb logcat | grep -E "WireGuard|WG|tun0"

# 检查 tun0 接口
adb shell ip addr show tun0

# 检查 WireGuard 进程
adb shell ps | grep wireguard
```

---

## Part 4: 开机自启动方案

### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Magisk service.d** | 系统级启动，最可靠 | 需要 Magisk root | 推荐：已 root 设备 |
| **Termux:Boot** | 简单，无需 Magisk 配置 | 需要安装插件 | 备选方案 |
| **组合部署** | 多层保障，最可靠 | 配置复杂 | 生产环境 |

---

### Magisk service.d 部署

#### 1. SSH 服务

```bash
# SSH 启动脚本
adb push shell/termux-ssh.sh /data/adb/service.d/termux-ssh.sh
adb shell chmod +x /data/adb/service.d/termux-ssh.sh

# SSH 看门狗
adb push shell/sshd-watchdog.sh /data/adb/service.d/sshd-watchdog.sh
adb shell chmod +x /data/adb/service.d/sshd-watchdog.sh
```

#### 2. WireGuard 服务

```bash
# WireGuard 启动脚本
adb push shell/wireguard-boot.sh /data/adb/service.d/wireguard-boot.sh
adb shell chmod +x /data/adb/service.d/wireguard-boot.sh

# WireGuard 看门狗
adb push shell/wireguard-watchdog.sh /data/adb/service.d/wireguard-watchdog.sh
adb shell chmod +x /data/adb/service.d/wireguard-watchdog.sh
```

#### 3. 重启验证

```bash
adb reboot

# 重启后检查
adb shell "ls -la /data/adb/service.d/"
adb logcat -s Termux-SSH
adb logcat -s WireGuard-Watchdog
```

---

### Termux:Boot 部署

#### 1. 安装 Termux:Boot

1. 在 F-Droid 或 GitHub 下载 Termux:Boot
2. 安装后授予 root 权限

#### 2. 配置启动脚本

```bash
# 在 Termux 中创建 boot 目录
mkdir -p ~/.termux/boot

# 复制综合看门狗脚本
cp ~/autosignin/shell/termux-boot/watchdog ~/.termux/boot/

# 设置执行权限
chmod +x ~/.termux/boot/watchdog
```

#### 3. 重启验证

- 重启后查看 Termux:Boot 通知确认启动成功

---

### 组合部署（最完整）

```bash
# ========== Magisk service.d ==========
# SSH 启动脚本
adb push shell/termux-ssh.sh /data/adb/service.d/termux-ssh.sh
adb shell chmod +x /data/adb/service.d/termux-ssh.sh

# SSH 看门狗
adb push shell/sshd-watchdog.sh /data/adb/service.d/sshd-watchdog.sh
adb shell chmod +x /data/adb/service.d/sshd-watchdog.sh

# WireGuard 看门狗
adb push shell/wireguard-watchdog.sh /data/adb/service.d/wireguard-watchdog.sh
adb shell chmod +x /data/adb/service.d/wireguard-watchdog.sh

# ========== Termux Boot ==========
mkdir -p ~/.termux/boot
cp ~/autosignin/shell/termux-boot/watchdog ~/.termux/boot/
chmod +x ~/.termux/boot/watchdog

# ========== 重启验证 ==========
adb reboot
```

---

## Part 5: 常用诊断命令

### Magisk 相关

```bash
# 检查 daemon 版本
adb shell "magisk -v"
adb shell "magisk -V"

# 检查 App 版本
adb shell "dumpsys package com.topjohnwu.magisk | grep -E 'versionCode|versionName'"

# 检查 Activity 组件（判断是否为 stub）
adb shell "pm dump com.topjohnwu.magisk | grep -E 'Activity|MAIN'" | head -5

# 检查 su 权限
adb shell "su -c 'id'"

# 监听日志
adb logcat -c && adb logcat -v time | grep -iE "magisk|topjohnwu|FATAL|crash"
```

---

### LSPosed 相关

```bash
# 检查模块状态
adb shell "ls -la /data/adb/modules/lsposed"

# 查看 LSPosed 日志
adb logcat -s LSPosed

# 检查 Zygisk 状态
adb shell "getprop | grep zygisk"

# 查看模块路径
adb shell "ls -la /data/adb/lspd/"
```

---

### SSH 相关

```bash
# 检查 SSH 进程
adb shell pgrep -f sshd

# 检查 SSH 端口（默认 8022）
adb shell netstat -tlnp | grep 8022

# 查看 SSH 启动日志
adb logcat -s Termux-SSH

# 查看 SSH 看门狗日志
adb logcat -s SSHD-Watchdog

# 检查 Magisk service.d 脚本
adb shell ls -la /data/adb/service.d/
```

---

### WireGuard 相关

```bash
# 检查 tun0 接口
adb shell ip addr show tun0

# 检查 WireGuard 进程
adb shell ps | grep wireguard

# 查看 WireGuard 启动日志
adb logcat -s WireGuard-Boot

# 查看 WireGuard 看门狗日志
adb logcat -s WireGuard-Watchdog

# Ping 网关测试
adb shell ping -c 1 -W 2 10.6.0.1
```

---

### 系统启动相关

```bash
# 检查系统启动完成状态
adb shell getprop sys.boot_completed

# 检查 Termux Boot 脚本
adb shell ls -la ~/.termux/boot/

# 查看所有服务脚本
adb shell ls -la /data/adb/service.d/
```

---

### Termux 修复方案

由于 `adb shell su -c` 命令超时，可以通过手机上的 Termux App 执行 root 命令：

**在 Termux 中执行**：

```bash
# 获取 root 权限
su

# 删除 magisk.db（Magisk 配置数据库）
rm -f /data/adb/magisk.db

# 删除 stub.apk（如果存在）
rm -f /data/stub.apk

# 重启设备
reboot
```

---

## 📊 问题总结

| 问题 | 根因 | 解决方案 |
|------|------|----------|
| Magisk App 闪退 | Daemon 检测到 App 版本不匹配��自动替换为 stub | 安装与 daemon 版本匹配的 APK |
| Magisk App 签名不匹配 | Daemon 中保存的签名与官方 APK 不同 | 删除 magisk.db 和 stub.apk 后重启 |
| LSPosed 崩溃 | LSPosed v1.9.2 与 Magisk v30.7 不兼容 | 升级/降级 LSPosed 或降级 Magisk |
| LSPosed 无法打开 | 误以为需要安装 APK | 使用拨号代码 `*#*#5776733#*#*` 或通知栏访问 |
| SSH 无法启动 | 用户身份错误或权限问题 | 使用 `su u0_a167 -c` 方式启动 |
| WireGuard 断连 | 隧道配置错误或网络问题 | 使用看门狗自动重连 |

---

## 📚 相关文档

- [一汽奥迪自动化程序文档.md](./一汽奥迪自动化程序文档.md) - AutoJS 自动化脚本
- [Android Telecom API 服务文档.md](./Android%20Telecom%20API%20服务文档.md) - 电话/短信 API 服务
- [AutoJS API 服务文档.md](./AutoJS%20API%20服务文档.md) - AutoJS 远程执行服务

---

**文档更新时间**: 2026-06-28  
**适用系统**: Android 14/15 with Magisk v28.1-v30.7  
**维护者**: AutoSignin Team
