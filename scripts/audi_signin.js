// AutoJS 测试脚本 - 一汽奥迪自动签到
"auto";

var CONFIG = {
  appPackage: "com.timanetworks.android.frame.audisuper.release",
  appName: "一汽奥迪",
  mineTabId: "navigation_main_fifth_tab",
  minePageReadyId: "personal_name",
  signinText: "每日签到",
  startupAdWaitMs: 12000,
  waitAfterHomeReadyMs: 3000,
  waitAfterSigninMs: 10000,
  useRoot: true,
  screenOffAfterRun: true,
  // 设备亮屏时间：签到流程较短，设置为 5 分钟
  keepScreenOnMs: 300000
};

function loadCommonUtils() {
  try {
    var source = engines.myEngine().getSource();
    var sourcePath = String(source);
    var scriptDir = sourcePath.replace(/[\\/][^\\/]*$/, "");
    return eval(files.read(scriptDir + "/common_utils.js"));
  } catch (e) {
    return eval(files.read("/sdcard/脚本/common_utils.js"));
  }
}

var commonUtils = loadCommonUtils();
// 成功打点文件：用于告警脚本判断"是否完成"；仅在业务成功且校验通过后写入
var MARK_FILE = commonUtils.getCurrentMarkFilePath("audi_signin");

auto.waitFor();

function logStage(stage, detail) {
  if (detail) {
    console.log("[audi_signin] " + stage + " - " + detail);
    return;
  }
  console.log("[audi_signin] " + stage);
}

function waitForMainPageReady() {
  logStage("等待首页", "等待底部导航出现");
  var deadline = Date.now() + CONFIG.startupAdWaitMs;
  while (Date.now() < deadline) {
    var tab = id(CONFIG.mineTabId).findOne(800);
    if (tab) {
      logStage("首页已就绪", "底部导航已出现");
      return true;
    }
    sleep(500);
  }
  return false;
}

function launchAudiApp() {
  logStage("启动 APP", "准备拉起 " + CONFIG.appName);
  var foregroundOk = false;
  for (var i = 0; i < 10; i++) {
    try {
      launchApp(CONFIG.appName);
    } catch (e) {
    }
    if (commonUtils.waitForAppForeground(CONFIG.appPackage, 1500)) {
      foregroundOk = true;
      break;
    }
    sleep(800);
  }

  if (foregroundOk) {
    logStage("启动 APP", "已进入前台");
  }
  return foregroundOk;
}

function checkAccountLoggedIn() {
  logStage("检查登录账号", "查找 personal_name 元素");
  var personalNameNode = id(CONFIG.minePageReadyId).findOne(3000);
  if (!personalNameNode) {
    logStage("检查登录账号", "未找到 personal_name 元素");
    return false;
  }
  
  var nameText = personalNameNode.text();
  if (!nameText) {
    logStage("检查登录账号", "personal_name 文本为空");
    return false;
  }
  
  if (nameText === "王大锤") {
    logStage("检查登录账号", "账号校验通过：" + nameText);
    return true;
  }
  
  logStage("检查登录账号", "账号不匹配，当前登录：" + nameText + "（期望：王大锤）");
  return false;
}

function openMineTabAndWaitForSignin() {
  // 根本原因已经确认：这个 Tab 不能再走通用封装，必须保留 tab.click() 的专用路径。
  // 因此这里明确直接对节点自身 click()，只在异常时才退回 smartClick 兜底。
  for (var i = 0; i < 3; i++) {
    var tab = id(CONFIG.mineTabId).findOne(5000);
    if (!tab) {
      logStage("打开我的页", "第 " + (i + 1) + " 次未找到底部 Tab");
      sleep(800);
      continue;
    }

    logStage("打开我的页", "第 " + (i + 1) + " 次尝试点击底部 Tab");
    try {
      tab.click();
    } catch (e) {
      commonUtils.smartClick(tab);
    }

    sleep(1500);

    var personalName = id(CONFIG.minePageReadyId).findOne(3000);
    if (!personalName) {
      logStage("打开我的页", "点击后仍未进入【我的】页");
      continue;
    }

    logStage("打开我的页", "已通过 personal_name 确认进入【我的】页");
    
    // 新增：校验登录账号是否为"王大锤"
    if (!checkAccountLoggedIn()) {
      logStage("账号校验失败", "当前登录账号不是王大锤，停止执行");
      return {
        success: false,
        signinBtn: null,
        alreadySigned: false,
        accountError: true
      };
    }
    
    var signinBtn = text(CONFIG.signinText).findOne(3000);
    if (signinBtn) {
      logStage("检查签到入口", "已看到【每日签到】入口");
      return {
        success: true,
        signinBtn: signinBtn,
        alreadySigned: false
      };
    }

    logStage("检查签到入口", "未找到【每日签到】，判定今天已签到");
    return {
      success: true,
      signinBtn: null,
      alreadySigned: true
    };
  }

  return {
    success: false,
    signinBtn: null,
    alreadySigned: false
  };
}

function performSignin(signinBtn) {
  logStage("执行签到", "准备点击【每日签到】");
  try {
    signinBtn.click();
  } catch (e) {
    commonUtils.smartClick(signinBtn);
  }
  sleep(CONFIG.waitAfterSigninMs);
  commonUtils.writeSuccessMark(MARK_FILE);
  logStage("执行签到", "已写入成功打点文件");
}

function unlockScreen() {
  logStage("解锁屏幕", "使用 keyevent 82 解锁");
  
  // 点亮屏幕
  if (!device.isScreenOn()) {
    device.wakeUp();
    sleep(1000);
  }
  
  // 方法 2：keyevent 82（菜单键）- 测试验证有效
  shell("input keyevent 82", true);
  sleep(2000);
  
  logStage("解锁屏幕", "解锁完成，当前包名：" + (currentPackage() || "桌面"));
}

function main() {
  try {
    // 检查成功标记文件，如果存在则不再执行
    if (files.exists(MARK_FILE)) {
      logStage("跳过执行", "成功标记文件已存在：" + MARK_FILE);
      return;
    }
    
    logStage("开始执行");
    
    // 使用自定义解锁方法
    unlockScreen();
    
    device.keepScreenOn(CONFIG.keepScreenOnMs);
    logStage("设备准备", "已亮屏、解锁并保持唤醒 " + (CONFIG.keepScreenOnMs / 1000) + " 秒");

    // 强制停止用于清理残留状态；依赖 Root 时 useRoot=true
    commonUtils.forceStop(CONFIG.appPackage, CONFIG.useRoot);
    sleep(1500);
    logStage("清理状态", "已强制停止历史进程");

    if (!launchAudiApp()) {
      logStage("启动失败", "打开 APP 失败或未进入前台");
      return;
    }

    // App 启动后会先出现广告页；必须等待广告结束或首页控件出现，否则后续点击全部会落空。
    if (!waitForMainPageReady()) {
      logStage("启动失败", "首页未就绪，可能仍停留在广告页");
      return;
    }

    // 广告页关闭后还会有一个短暂稳定期；保留这段缓冲，贴近原来能工作的时序。
    sleep(CONFIG.waitAfterHomeReadyMs);
    logStage("首页稳定", "等待 " + CONFIG.waitAfterHomeReadyMs + "ms 后继续");

    var minePageState = openMineTabAndWaitForSignin();
    if (!minePageState.success) {
      // 如果是账号校验失败，不再重试
      if (minePageState.accountError) {
        logStage("账号校验失败", "脚本终止");
        return;
      }
      logStage("打开我的页", "未成功进入我的页");
      return;
    }
    if (minePageState.alreadySigned) {
      commonUtils.writeSuccessMark(MARK_FILE);
      logStage("执行签到", "今日已签到，按成功处理并写入打点文件");
      return;
    }
    performSignin(minePageState.signinBtn);
  } catch (e) {
    console.error(e);
    console.error("执行失败：" + e);
  } finally {
    logStage("执行结束", "进入统一收尾");
    // keyevent 223：熄屏；保持与原脚本一致的收尾习惯，避免手机长亮耗电
    commonUtils.cleanup({
      packageName: CONFIG.appPackage,
      forceStop: true,
      useRoot: CONFIG.useRoot,
      screenOff: CONFIG.screenOffAfterRun
    });
  }
}

main();
