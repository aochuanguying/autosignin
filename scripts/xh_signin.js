// AutoJS 测试脚本 - 信鸿 3.0 自动签到
"auto";

var CONFIG = {
  appPackage: "com.ss.android.lark.dahx258",
  appName: "信鸿3.0",
  
  // 步骤 2：工作台配置
  workbenchItemId: "textItem",
  workbenchItemText: "工作台",
  workbenchParentClass: "android.view.ViewGroup",
  
  // 步骤 3：签到入口配置
  signinEntryId: "name",
  signinEntryText: "签到",
  
  // 步骤 4：打卡 tab 配置
  clockInTabId: "microapp_m_tab_tv",
  clockInTabText: "打卡",
  
  // 步骤 5：上班打卡配置
  clockInBtnText: "上班打卡",
  
  // 步骤 6：下班打卡配置
  clockOffBtnText: "下班打卡",
  
  // 时间配置
  startupWaitMs: 20000,           // APP 启动等待超时
  waitAfterHomeReadyMs: 1000,     // 页面切换后等待时间
  useRoot: true,                  // 是否使用 Root 权限
  screenOffAfterRun: true,        // 运行后是否熄屏
  keepScreenOnMs: 300000,         // 设备保持亮屏时间（5 分钟）
  
  // 打卡区域等待超时（2 分钟）
  clockInRangeTimeoutMs: 120000,
  // 元素查找超时
  elementFindTimeoutMs: 5000,
  // 点击后等待页面更新
  clickWaitMs: 5000,
  // 打卡结果验证重试次数
  verifyRetryCount: 3,
  // 验证失败重试间隔
  verifyRetryIntervalMs: 2000,
  // 随机延迟范围（0-10 分钟）
  randomDelayMaxMinutes: 10,
  // 首页稳定检测次数
  homeStableCount: 3,
  // APP 启动重试次数
  appLaunchRetryCount: 10,
  // 启动重试间隔
  appLaunchRetryIntervalMs: 800
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

auto.waitFor();

function logStage(stage, detail) {
  if (detail) {
    console.log("[xinhong_signin] " + stage + " - " + detail);
    return;
  }
  console.log("[xinhong_signin] " + stage);
}

/**
 * 逐级向上查找父元素
 * @param {UiObject} element - 起始元素
 * @param {Object} condition - 查找条件，如 {className: "android.view.ViewGroup"} 或 {id: "icon_app"}
 * @param {number} maxDepth - 最大查找深度
 * @returns {UiObject|null} 找到的父元素，未找到返回 null
 */
function findParentByCondition(element, condition, maxDepth) {
  var depth = typeof maxDepth === "number" ? maxDepth : 10;
  var current = element.parent();
  
  for (var i = 0; current && i < depth; i++) {
    var match = true;
    
    // 检查 id 条件
    if (condition.id !== undefined) {
      try {
        if (current.id() !== condition.id) {
          match = false;
        }
      } catch (e) {
        match = false;
      }
    }
    
    // 检查 className 条件
    if (condition.className !== undefined) {
      try {
        if (current.className() !== condition.className) {
          match = false;
        }
      } catch (e) {
        match = false;
      }
    }
    
    // 检查 text 条件
    if (condition.text !== undefined) {
      try {
        if (current.text() !== condition.text) {
          match = false;
        }
      } catch (e) {
        match = false;
      }
    }
    
    if (match) {
      return current;
    }
    
    current = current.parent();
  }
  
  return null;
}

/**
 * 查找元素并点击其符合条件的父元素
 * @param {string} viewId - 元素 ID
 * @param {string} viewText - 元素文本
 * @param {Object} parentCondition - 父元素查找条件
 * @param {string} description - 描述信息
 * @param {number} timeoutMs - 超时时间
 * @returns {boolean} 是否成功
 */
function clickElementWithParent(viewId, viewText, parentCondition, description, timeoutMs) {
  var timeout = typeof timeoutMs === "number" ? timeoutMs : CONFIG.elementFindTimeoutMs;
  var deadline = Date.now() + timeout;
  var checkIntervalMs = 500; // 查找间隔
  
  logStage("查找" + description, "开始查找 - id=" + viewId + ", text=" + viewText);
  
  var checkCount = 0;
  var logMaxCount = 3; // 前 3 次详细日志
  while (Date.now() < deadline) {
    checkCount++;
    // 查找所有匹配 ID 的元素
    var elements = id(viewId).find();
    var totalSize = elements ? elements.size() : 0;
    
    // 详细日志：前 3 次 + 每 5 次
    if (checkCount <= logMaxCount || checkCount % 5 === 0) {
      logStage("查找" + description, "第 " + checkCount + " 次查找，找到 " + totalSize + " 个匹配元素");
    }
    
    if (!elements || totalSize === 0) {
      sleep(checkIntervalMs);
      continue;
    }
    
    // 遍历所有匹配的元素
    for (var i = 0; i < totalSize; i++) {
      var element = elements.get(i);
      
      // 验证文本
      var elemText = "";
      try {
        elemText = element.text();
        if (elemText !== viewText) {
          if (checkCount <= logMaxCount) {
            logStage("查找" + description, "第 " + (i + 1) + " 个元素文本不匹配：'" + elemText + "' != '" + viewText + "'");
          }
          continue;
        }
      } catch (e) {
        if (checkCount <= logMaxCount) {
          logStage("查找" + description, "第 " + (i + 1) + " 个元素文本获取失败：" + e);
        }
        continue;
      }
      
      logStage("查找" + description, "第 " + (i + 1) + " 个元素文本匹配，开始查找父元素");
      
      // 查找符合条件的父元素
      var parent = findParentByCondition(element, parentCondition, 10);
      if (!parent) {
        if (checkCount <= logMaxCount) {
          logStage("查找" + description, "第 " + (i + 1) + " 个元素未找到符合条件的父元素");
        }
        continue;
      }
      
      logStage("点击" + description, "✓ 找到目标（第 " + (i + 1) + " 个匹配元素），执行点击");
      commonUtils.smartClick(parent);
      sleep(800);
      return true;
    }
    
    sleep(checkIntervalMs);
  }
  
  logStage("查找" + description, "✗ 超时未找到（共查找 " + checkCount + " 次）");
  return false;
}



/**
 * 验证打卡结果
 * 在打卡区域内查找 text 以"已打卡"开头的元素
 * @param {UiObject} clockArea - 打卡区域元素
 * @param {string} areaType - 区域类型（上班/下班）
 * @returns {Object} {success: boolean, alreadyClockIn: boolean, message: string}
 */
function verifyClockInResult(clockArea, areaType) {
  logStage("验证打卡", "查找'已打卡'元素（" + areaType + "）");
  
  var elements = clockArea.find(textMatches("^已打卡.*"));
  if (elements && elements.size() > 0) {
    for (var i = 0; i < elements.size(); i++) {
      try {
        var elemText = elements.get(i).text();
        logStage("验证打卡", "✓ " + areaType + "已打卡：" + elemText);
        return { success: true, alreadyClockIn: true, message: elemText };
      } catch (e) {
        logStage("验证打卡", "第 " + (i + 1) + " 个元素文本获取失败：" + e);
      }
    }
  }
  
  logStage("验证打卡", "未找到'已打卡'元素（" + areaType + "）");
  return { success: false, alreadyClockIn: false, message: "未找到已打卡元素" };
}

/**
 * 检查是否已进入打卡范围
 * 在上班打卡区域内查找 text 以"已进入打卡范围"开头的元素
 * @param {UiObject} workArea - 上班打卡区域元素
 * @returns {boolean} 是否已进入打卡范围
 */
function checkInRange(workArea) {
  logStage("检查范围", "查找'已进入打卡范围'元素");
  
  var elements = workArea.find(textMatches("^已进入打卡范围.*"));
  if (elements && elements.size() > 0) {
    try {
      var elemText = elements.get(0).text();
      logStage("检查范围", "✓ 已进入范围：" + elemText);
      return true;
    } catch (e) {
      logStage("检查范围", "元素文本获取失败：" + e);
      return false;
    }
  }
  
  logStage("检查范围", "未进入范围");
  return false;
}

function waitForMainPageReady() {
  logStage("等待首页", "等待工作台元素出现");
  var deadline = Date.now() + CONFIG.startupWaitMs;
  var stableCount = 0;
  var checkIntervalMs = 500;
  var stableWaitMs = 300;
  var finalWaitMs = 500;
  
  while (Date.now() < deadline) {
    var elements = id(CONFIG.workbenchItemId).find();
    var found = false;
    
    if (elements && elements.size() > 0) {
      for (var i = 0; i < elements.size(); i++) {
        try {
          var elem = elements.get(i);
          if (elem.text() === CONFIG.workbenchItemText) {
            found = true;
            break;
          }
        } catch (e) {
          continue;
        }
      }
    }
    
    if (found) {
      stableCount++;
      logStage("等待首页", "第 " + stableCount + " 次找到工作台元素（共 " + elements.size() + " 个匹配）");
      
      if (stableCount >= CONFIG.homeStableCount) {
        logStage("首页已就绪", "工作台元素已稳定（连续" + CONFIG.homeStableCount + "次）");
        sleep(finalWaitMs);
        return true;
      }
      
      sleep(stableWaitMs);
      continue;
    } else {
      if (stableCount > 0) {
        logStage("等待首页", "页面刷新中，重置计数 (已计数:" + stableCount + ")");
        stableCount = 0;
      }
    }
    sleep(checkIntervalMs);
  }
  
  logStage("等待首页", "超时未找到稳定的工作台元素（超时：" + CONFIG.startupWaitMs + "ms）");
  return false;
}

function launchXinhongApp() {
  logStage("启动 APP", "准备拉起 " + CONFIG.appName);
  var foregroundOk = false;
  var launchError = null;
  
  for (var i = 0; i < CONFIG.appLaunchRetryCount; i++) {
    try {
      launchApp(CONFIG.appName);
    } catch (e) {
      launchError = e;
      logStage("启动 APP", "第 " + (i + 1) + " 次启动失败：" + e);
    }
    
    if (commonUtils.waitForAppForeground(CONFIG.appPackage, 1500)) {
      foregroundOk = true;
      logStage("启动 APP", "第 " + (i + 1) + " 次尝试成功进入前台");
      break;
    }
    sleep(CONFIG.appLaunchRetryIntervalMs);
  }

  if (foregroundOk) {
    logStage("启动 APP", "✓ 已进入前台");
  } else {
    logStage("启动 APP", "✗ 启动失败（重试" + CONFIG.appLaunchRetryCount + "次）" + (launchError ? "，错误：" + launchError : ""));
  }
  return foregroundOk;
}

function performClockIn() {
  logStage("步骤 5", "上班签到");
  var checkIntervalMs = 500;
  
  // 5.1 查找上班打卡区域
  logStage("步骤 5", "查找上班打卡区域（id=card0）");
  var workArea = id("card0").findOne(CONFIG.elementFindTimeoutMs);
  if (!workArea) {
    logStage("步骤 5", "✗ 未找到上班打卡区域");
    return false;
  }
  logStage("步骤 5", "✓ 找到上班打卡区域");
  sleep(checkIntervalMs);
  
  // 5.2 检查是否已上班打卡
  logStage("步骤 5", "检查是否已上班打卡");
  var checkResult = verifyClockInResult(workArea, "上班");
  if (checkResult.alreadyClockIn) {
    logStage("步骤 5", "✓ 当天已上班打卡：" + checkResult.message);
    return true;
  }
  logStage("步骤 5", "尚未打卡，继续执行打卡流程");
  
  // 5.3 等待进入打卡范围
  logStage("步骤 5", "等待进入打卡范围（最多 " + (CONFIG.clockInRangeTimeoutMs / 1000) + " 秒）");
  var inRange = false;
  var waitDeadline = Date.now() + CONFIG.clockInRangeTimeoutMs;
  var checkCount = 0;
  while (Date.now() < waitDeadline) {
    checkCount++;
    if (checkInRange(workArea)) {
      inRange = true;
      logStage("步骤 5", "✓ 已进入打卡范围（检查 " + checkCount + " 次）");
      break;
    }
    sleep(checkIntervalMs);
  }
  
  if (!inRange) {
    logStage("步骤 5", "✗ 等待超时，未进入打卡范围");
    return false;
  }
  
  // 5.4 点击上班打卡按钮
  logStage("步骤 5", "点击上班打卡按钮");
  var clockInBtnText = workArea.findOne(text(CONFIG.clockInBtnText));
  if (!clockInBtnText) {
    logStage("步骤 5", "✗ 未找到上班打卡按钮");
    return false;
  }
  
  // 获取坐标并点击
  var bounds = clockInBtnText.bounds();
  var centerX = (bounds.left + bounds.right) / 2;
  var centerY = (bounds.top + bounds.bottom) / 2;
  
  logStage("步骤 5", "点击坐标：[" + centerX + ", " + centerY + "]");
  shell("input tap " + centerX + " " + centerY, true);
  sleep(CONFIG.clickWaitMs);
  
  // 5.6 验证打卡结果
  logStage("步骤 5", "验证打卡结果（最多重试 " + CONFIG.verifyRetryCount + " 次）");
  for (var i = 0; i < CONFIG.verifyRetryCount; i++) {
    var finalResult = verifyClockInResult(workArea, "上班");
    if (finalResult.alreadyClockIn) {
      logStage("步骤 5", "✓ 上班打卡成功：" + finalResult.message);
      return true;
    }
    if (i < CONFIG.verifyRetryCount - 1) {
      logStage("步骤 5", "第 " + (i + 1) + " 次验证失败，等待 " + (CONFIG.verifyRetryIntervalMs / 1000) + " 秒后重试");
      sleep(CONFIG.verifyRetryIntervalMs);
    }
  }
  logStage("步骤 5", "✗ 打卡失败，未检测到已打卡状态");
  return false;
}

/**
 * 解析打卡时间并判断是否在 18:00 之后
 * @param {string} clockInMessage - 打卡消息，如"已打卡 17:30"
 * @returns {boolean} true=在 18:00 之后，false=在 18:00 之前
 */
function isAfterSixPM(clockInMessage) {
  try {
    // 提取时间部分（格式：已打卡 HH:mm）
    var timeMatch = clockInMessage.match(/已打卡\s*(\d{1,2}):(\d{2})/);
    if (!timeMatch) {
      logStage("时间解析", "无法从消息中提取时间：" + clockInMessage);
      return false;
    }
    
    var hour = parseInt(timeMatch[1]);
    var minute = parseInt(timeMatch[2]);
    
    logStage("时间解析", "解析打卡时间：" + hour + ":" + (minute < 10 ? "0" + minute : minute));
    
    // 判断是否在 18:00 之后
    if (hour > 18) {
      logStage("时间解析", "打卡时间在 18:00 之后");
      return true;
    } else if (hour < 18) {
      logStage("时间解析", "打卡时间在 18:00 之前");
      return false;
    } else {
      // 18 点整，判断分钟
      if (minute >= 0) {
        logStage("时间解析", "打卡时间为 18:00 或之后");
        return true;
      } else {
        logStage("时间解析", "打卡时间在 18:00 之前");
        return false;
      }
    }
  } catch (e) {
    logStage("时间解析", "解析失败：" + e);
    return false;
  }
}

/**
 * 点击更新打卡按钮
 * @param {UiObject} clockArea - 打卡区域
 * @returns {boolean} 是否成功
 */
function clickUpdateClockIn(clockArea) {
  logStage("更新打卡", "查找'更新打卡'按钮");
  var updateBtnText = clockArea.findOne(text("更新打卡"));
  if (!updateBtnText) {
    logStage("更新打卡", "✗ 未找到'更新打卡'按钮");
    return false;
  }
  
  logStage("更新打卡", "✓ 找到'更新打卡'按钮");
  
  // 获取坐标并点击
  var bounds = updateBtnText.bounds();
  var centerX = (bounds.left + bounds.right) / 2;
  var centerY = (bounds.top + bounds.bottom) / 2;
  
  logStage("更新打卡", "点击坐标：[" + centerX + ", " + centerY + "]");
  shell("input tap " + centerX + " " + centerY, true);
  sleep(1000); // 等待弹出框出现
  
  // 查找并点击"确定"按钮
  logStage("更新打卡", "查找'确定'弹出框按钮");
  var confirmBtn = text("确定").findOne(2000);
  if (confirmBtn) {
    logStage("更新打卡", "✓ 找到'确定'按钮，执行点击");
    var confirmBounds = confirmBtn.bounds();
    var confirmX = (confirmBounds.left + confirmBounds.right) / 2;
    var confirmY = (confirmBounds.top + confirmBounds.bottom) / 2;
    shell("input tap " + confirmX + " " + confirmY, true);
    sleep(CONFIG.clickWaitMs);
  } else {
    logStage("更新打卡", "⚠ 未找到'确定'按钮，继续验证");
    sleep(CONFIG.clickWaitMs - 1000);
  }
  
  // 验证更新打卡结果
  logStage("更新打卡", "验证更新打卡结果");
  var elements = clockArea.find(textMatches("^已打卡.*"));
  if (elements && elements.size() > 0) {
    try {
      var elemText = elements.get(0).text();
      logStage("更新打卡", "✓ 更新打卡成功：" + elemText);
      return true;
    } catch (e) {
      logStage("更新打卡", "获取结果失败：" + e);
    }
  }
  
  logStage("更新打卡", "✗ 更新打卡失败");
  return false;
}

function performClockOff() {
  logStage("步骤 6", "下班签到");
  var checkIntervalMs = 500;
  
  // 6.1 查找下班打卡区域
  logStage("步骤 6", "查找下班打卡区域（id=last_clock_timeline_card）");
  var clockOffArea = id("last_clock_timeline_card").findOne(CONFIG.elementFindTimeoutMs);
  if (!clockOffArea) {
    logStage("步骤 6", "✗ 未找到下班打卡区域");
    return false;
  }
  logStage("步骤 6", "✓ 找到下班打卡区域");
  sleep(checkIntervalMs);
  
  // 6.2 检查是否已下班打卡
  logStage("步骤 6", "检查是否已下班打卡");
  var checkResult = verifyClockInResult(clockOffArea, "下班");
  
  if (checkResult.alreadyClockIn) {
    logStage("步骤 6", "检测到已打卡：" + checkResult.message);
    
    // 解析打卡时间，判断是否在 18:00 之后
    var afterSixPM = isAfterSixPM(checkResult.message);
    
    if (afterSixPM) {
      logStage("步骤 6", "✓ 打卡时间在 18:00 之后，今日已下班打卡");
      return true;
    } else {
      logStage("步骤 6", "打卡时间在 18:00 之前，需要更新打卡");
      
      // 点击更新打卡按钮
      if (clickUpdateClockIn(clockOffArea)) {
        logStage("步骤 6", "✓ 更新打卡完成");
        return true;
      } else {
        logStage("步骤 6", "✗ 更新打卡失败");
        return false;
      }
    }
  }
  
  logStage("步骤 6", "尚未打卡，继续执行打卡流程");
  
  // 6.3 等待进入打卡范围
  logStage("步骤 6", "等待进入打卡范围（最多 " + (CONFIG.clockInRangeTimeoutMs / 1000) + " 秒）");
  var inRange = false;
  var waitDeadline = Date.now() + CONFIG.clockInRangeTimeoutMs;
  var checkCount = 0;
  while (Date.now() < waitDeadline) {
    checkCount++;
    if (checkInRange(clockOffArea)) {
      inRange = true;
      logStage("步骤 6", "✓ 已进入打卡范围（检查 " + checkCount + " 次）");
      break;
    }
    sleep(checkIntervalMs);
  }
  
  if (!inRange) {
    logStage("步骤 6", "✗ 等待超时，未进入打卡范围");
    return false;
  }
  
  // 6.4 查找下班打卡按钮
  logStage("步骤 6", "查找下班打卡按钮（text=下班打卡）");
  var clockOffBtnText = clockOffArea.findOne(text(CONFIG.clockOffBtnText));
  if (!clockOffBtnText) {
    logStage("步骤 6", "✗ 未找到下班打卡按钮");
    return false;
  }
  
  // 获取坐标并点击
  var bounds = clockOffBtnText.bounds();
  var centerX = (bounds.left + bounds.right) / 2;
  var centerY = (bounds.top + bounds.bottom) / 2;
  
  logStage("步骤 6", "点击坐标：[" + centerX + ", " + centerY + "]");
  shell("input tap " + centerX + " " + centerY, true);
  sleep(CONFIG.clickWaitMs);
  
  // 6.6 验证打卡结果
  logStage("步骤 6", "验证打卡结果（最多重试 " + CONFIG.verifyRetryCount + " 次）");
  for (var i = 0; i < CONFIG.verifyRetryCount; i++) {
    var finalResult = verifyClockInResult(clockOffArea, "下班");
    if (finalResult.alreadyClockIn) {
      logStage("步骤 6", "✓ 下班打卡成功：" + finalResult.message);
      return true;
    }
    if (i < CONFIG.verifyRetryCount - 1) {
      logStage("步骤 6", "第 " + (i + 1) + " 次验证失败，等待 " + (CONFIG.verifyRetryIntervalMs / 1000) + " 秒后重试");
      sleep(CONFIG.verifyRetryIntervalMs);
    }
  }
  logStage("步骤 6", "✗ 打卡失败，未检测到已打卡状态");
  return false;
}

/**
 * 获取随机延迟时间（0-MAX 分钟）
 * @returns {number} 延迟毫秒数
 */
function getRandomDelay() {
  var randomMinutes = Math.floor(Math.random() * (CONFIG.randomDelayMaxMinutes + 1));
  var delayMs = randomMinutes * 60 * 1000;
  logStage("随机延迟", "生成随机延迟：" + randomMinutes + " 分钟（" + (delayMs / 1000 / 60).toFixed(1) + " 分钟）");
  return delayMs;
}

/**
 * 执行完整的打卡流程（导航 + 打卡）
 * @param {string} clockType - 打卡类型："上班" 或 "下班"
 * @returns {boolean} 是否成功
 */
function performFullClockProcess(clockType) {
  logStage("开始执行", "执行" + clockType + "打卡流程");
  var postClickWaitMs = 1000;
  
  commonUtils.prepareDevice({ keepMs: CONFIG.keepScreenOnMs });
  logStage("设备准备", "已亮屏并保持唤醒 " + (CONFIG.keepScreenOnMs / 1000) + " 秒");

  // 强制停止用于清理残留状态
  commonUtils.forceStop(CONFIG.appPackage, CONFIG.useRoot);
  sleep(1500);
  logStage("清理状态", "已强制停止历史进程");

  if (!launchXinhongApp()) {
    logStage("错误", "打开 APP 失败或未进入前台");
    return false;
  }

  if (!waitForMainPageReady()) {
    logStage("错误", "首页未就绪，可能 APP 启动失败");
    return false;
  }

  sleep(CONFIG.waitAfterHomeReadyMs);
  logStage("首页稳定", "等待 " + CONFIG.waitAfterHomeReadyMs + "ms 后继续");

  // ========== 步骤 1：点击消息，校验休假状态 ==========
  logStage("步骤 1", "点击消息，校验休假状态");
  if (!clickElementWithParent(
    CONFIG.workbenchItemId,
    "消息",
    { className: CONFIG.workbenchParentClass },
    "消息",
    CONFIG.elementFindTimeoutMs
  )) {
    logStage("步骤 1", "✗ 未找到'消息'元素");
    return false;
  }
  sleep(postClickWaitMs);
  
  // 检查休假状态
  var statusElements = id("custom_status_title").find();
  if (statusElements && statusElements.size() > 0) {
    for (var i = 0; i < statusElements.size(); i++) {
      try {
        var statusText = statusElements.get(i).text();
        logStage("步骤 1", "找到状态元素：" + statusText);
        if (statusText && statusText.indexOf("休假") !== -1) {
          logStage("步骤 1", "✓ 检测到休假状态：" + statusText + "，跳过打卡");
          return true;
        }
      } catch (e) {
        logStage("步骤 1", "第 " + (i + 1) + " 个状态元素文本获取失败：" + e);
      }
    }
  }
  logStage("步骤 1", "未检测到休假状态");
  
  // ========== 步骤 2：点击工作台 ==========
  logStage("步骤 2", "点击工作台");
  if (!clickElementWithParent(
    CONFIG.workbenchItemId,
    CONFIG.workbenchItemText,
    { className: CONFIG.workbenchParentClass },
    "工作台",
    CONFIG.elementFindTimeoutMs
  )) {
    logStage("步骤 2", "✗ 点击工作台失败");
    return false;
  }
  logStage("步骤 2", "✓ 点击工作台成功");
  sleep(CONFIG.waitAfterHomeReadyMs);
  
  // ========== 步骤 3：点击签到 ==========
  logStage("步骤 3", "点击签到");
  if (!clickElementWithParent(
    CONFIG.signinEntryId,
    CONFIG.signinEntryText,
    {},
    "签到入口",
    CONFIG.elementFindTimeoutMs
  )) {
    logStage("步骤 3", "✗ 点击签到失败");
    return false;
  }
  logStage("步骤 3", "✓ 点击签到成功");
  sleep(CONFIG.waitAfterHomeReadyMs);
  
  // ========== 步骤 4：检查今日休息 ==========
  logStage("步骤 4", "等待页面加载（3 秒）");
  sleep(3000);  // 增加等待时间，确保页面完全加载
  
  logStage("步骤 4", "检查今日休息");
  var restElements = text("今日休息").find();
  if (restElements && restElements.size() > 0) {
    logStage("步骤 4", "✓ 发现'今日休息'元素，今天休息");
    return true;
  }
  logStage("步骤 4", "未发现'今日休息'，继续执行打卡");
  
  // ========== 步骤 5/6：执行打卡 ==========
  if (clockType === "上班") {
    if (!performClockIn()) {
      console.error("步骤 5：上班签到失败");
      return false;
    }
  } else if (clockType === "下班") {
    if (!performClockOff()) {
      logStage("错误", "步骤 6：下班签到失败");
      return false;
    }
  }
  
  return true;
}

function main() {
  var screenOffDelayMs = 1000;
  
  try {
    var now = new Date();
    var hour = now.getHours();
    var minute = now.getMinutes();
    var currentTimeStr = hour + ":" + (minute < 10 ? "0" + minute : minute);
    
    logStage("时间检查", "当前时间：" + currentTimeStr);
    
    if (hour < 9) {
      logStage("时间策略", "当前时间在 9:00 之前，准备执行上班打卡");
      var delayMs = getRandomDelay();
      logStage("时间策略", "等待 " + Math.round(delayMs / 1000 / 60) + " 分钟后执行上班打卡");
      
      if (device.isScreenOn()) {
        device.cancelKeepingAwake();
        shell("input keyevent 223", true);
        sleep(screenOffDelayMs);
      }
      sleep(delayMs);
      
      if (!performFullClockProcess("上班")) {
        logStage("错误", "上班打卡流程执行失败");
        return;
      }
    } else if (hour >= 18) {
      logStage("时间策略", "当前时间在 18:00 之后，准备执行下班打卡");
      var delayMs = getRandomDelay();
      logStage("时间策略", "等待 " + Math.round(delayMs / 1000 / 60) + " 分钟后执行下班打卡");
      
      if (device.isScreenOn()) {
        device.cancelKeepingAwake();
        shell("input keyevent 223", true);
        sleep(screenOffDelayMs);
      }
      sleep(delayMs);
      
      if (!performFullClockProcess("下班")) {
        logStage("错误", "下班打卡流程执行失败");
        return;
      }
    } else {
      logStage("时间策略", "当前时间不在允许范围内（9:00 之前或 18:00 之后），不执行打卡");
      return;
    }
    
  } catch (e) {
    logStage("错误", "执行异常：" + e);
  } finally {
    logStage("执行结束", "进入统一收尾");
    commonUtils.cleanup({
      packageName: CONFIG.appPackage,
      forceStop: true,
      useRoot: CONFIG.useRoot,
      screenOff: CONFIG.screenOffAfterRun
    });
  }
}

main();
