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

/**
 * 执行 shell 命令
 */
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

/**
 * 检查连接状态
 */
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

/**
 * 打开应用并点击开关
 */
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
  
  // 检查当前状态
  var isChecked = switchWidget.checked();
  console.log("当前状态：" + (isChecked ? "已连接" : "已断开"));
  
  if (isChecked) {
    console.log("已经是连接状态");
    return true;
  }
  
  // 点击连接
  console.log("3. 点击连接开关");
  try {
    switchWidget.click();
    console.log("✓ 点击成功");
  } catch (e) {
    console.log("✗ 点击失败：" + e.message);
    return false;
  }
  
  // 等待连接
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
  
  console.log("✗ 连接超时");
  return false;
}

/**
 * 主函数
 */
function main() {
  // 先检查是否已经连接
  console.log("检查当前连接状态...");
  if (checkConnection()) {
    console.log("✓ 已经连接，无需操作");
    exit();
  }
  
  console.log("✗ 检测到断联，准备连接");
  
  // 尝试连接
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
  
  // 返回桌面
  home();
}

// 启动
main();
