"auto";

var CONFIG = {
  appPackage: "com.timanetworks.android.frame.audisuper.release",
  appName: "一汽奥迪",
  startupAdWaitMs: 12000,
  imageDir: "/sdcard/Pictures/AUDI",
  // 录制上传脚本：相册 UI 改版或权限弹窗都会导致回放失败，属于最脆弱的一环
  recordedAutoFile: "/sdcard/脚本/audi_post.auto",
  waitAfterAutoExecMs: 20000,
  waitAfterPublishMs: 8000,
  waitAfterMineTabMs: 2000,
  waitAfterEarnRewardMs: 1500,
  remoteBaseUrl: "https://yqad.hxfssc.com:8088/api",
  // 本次重构不外置 token，仅做结构与稳定性优化（避免引入行为变化）
  remoteToken: "api_token_c5d7f7a306cbd78886ae57d6547aee48d59eeeb94de29234972a074105dc0aff",
  remoteGeneratePath: "/posts/generate",
  remoteBatchPath: "/posts/batch",
  remoteTaskPathPrefix: "/posts/tasks/",
  remoteConfirmPath: "/posts/confirm",
  remotePayload: {
    useTopic: true,
    mode: "featured"
  },
  remoteUseAsync: true,
  // 同步接口超时时间增大到 900 秒（15 分钟），因为发帖逻辑复杂，生成帖子时间长
  remoteTimeoutSec: 900,
  remotePollIntervalMs: 2000,
  remotePollTimeoutMs: 600000,
  remotePollSchedule: [
    { endMs: 90000, intervalMs: 0, allowRequest: false },
    { endMs: 240000, intervalMs: 20000, allowRequest: true },
    { endMs: 600000, intervalMs: 10000, allowRequest: true }
  ],
  remoteEnableSyncFallback: true,
  remoteFallbackOnTimeout: true,
  remoteFallbackOnTaskFailed: true,
  remoteFallbackOnNetworkError: true,
  remoteFallbackMaxConsecutiveErrors: 5,
  remoteOverallTimeoutMs: 0,
  waitForEditorAfterAutoMs: 120000,
  uploadWaitTimeoutMs: 180000,
  uploadPollIntervalMs: 800,
  uploadStableSuccessMs: 60000,
  uploadStableAllowZero: true,
  useRoot: true,
  screenOffAfterRun: true,
  // 设备亮屏时间：发帖流程较长，设置为 20 分钟
  keepScreenOnMs: 1200000
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
var MARK_FILE = commonUtils.getCurrentMarkFilePath("audi_post");
// 使用局部变量替代全局变量存储 taskId
var postTaskId = null;

auto.waitFor();

function logStage(stage, detail) {
  if (detail) {
    console.log("[audi_post] " + stage + " - " + detail);
    return;
  }
  console.log("[audi_post] " + stage);
}

function countImagesInDir(dirPath) {
  if (!files.exists(dirPath)) {
    console.log("图片目录不存在：" + dirPath);
    return 0;
  }
  var fileNames = files.listDir(dirPath, function(name) {
    return /\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(String(name));
  });
  return (fileNames && fileNames.length) ? fileNames.length : 0;
}

function runRecordedAuto(autoFilePath, waitMs) {
  if (!files.exists(autoFilePath)) {
    throw new Error("未找到录制文件：" + autoFilePath);
  }
  console.log("开始执行录制文件：" + autoFilePath);
  commonUtils.runRecordedAuto(autoFilePath, waitMs || CONFIG.waitAfterAutoExecMs);
}

function getUploadedImageElementCount() {
  var items = id("common_add_picture_grid_delete").find();
  return items ? items.size() : 0;
}

function clearEditTextById(viewId, timeout) {
  commonUtils.clearTextById(viewId, timeout);
}

function waitForEditorPageReady(timeoutMs) {
  return commonUtils.waitUntil(function() {
    return !!id("content_edittext").findOne(200);
  }, timeoutMs || 20000, 300);
}

function waitForLeaveEditorPage(timeoutMs) {
  return commonUtils.waitUntil(function() {
    return !id("content_edittext").findOne(200);
  }, timeoutMs || 15000, 300);
}

function waitForUploadSuccess(localImageCount, timeoutMs) {
  var local = typeof localImageCount === "number" ? localImageCount : 0;
  if (local <= 0) {
    return true;
  }
  var expected = local >= 9 ? 9 : local;
  var deadline = Date.now() + (timeoutMs || CONFIG.uploadWaitTimeoutMs);
  var lastCount = -1;
  var lastChangeAt = Date.now();
  var stableSuccessMs = typeof CONFIG.uploadStableSuccessMs === "number" ? CONFIG.uploadStableSuccessMs : 0;
  logStage("等待上传", "local=" + local + ", expected=" + expected + ", timeoutMs=" + (timeoutMs || CONFIG.uploadWaitTimeoutMs));
  while (Date.now() < deadline) {
    var current = getUploadedImageElementCount();
    if (current !== lastCount) {
      lastCount = current;
      lastChangeAt = Date.now();
      logStage("上传进度", current + "/" + expected);
    }
    if (isUploadSuccess(local, current)) {
      sleep(600);
      return isUploadSuccess(local, getUploadedImageElementCount());
    }
    if (stableSuccessMs > 0 && Date.now() - lastChangeAt >= stableSuccessMs) {
      if (CONFIG.uploadStableAllowZero || current > 0) {
        logStage("上传兜底成功", "stableMs=" + stableSuccessMs + ", page=" + current + ", expected=" + expected);
        return true;
      }
    }
    sleep(CONFIG.uploadPollIntervalMs);
  }
  return false;
}

function deleteAllUploadedImages() {
  var maxRounds = 12;
  for (var i = 0; i < maxRounds; i++) {
    var items = id("common_add_picture_grid_delete").find();
    if (!items || items.size() === 0) {
      return;
    }
    commonUtils.clickBoundsCenter(items.get(0));
    sleep(1000);
  }
  console.log("删除历史图片达到上限，可能仍有残留");
}

function isUploadSuccess(localImageCount, uploadedElementCount) {
  if (localImageCount >= 9) {
    return uploadedElementCount === 9;
  }
  return uploadedElementCount === localImageCount;
}

function isPostSuccess(timeout) {
  var maxRetries = 3;
  var retryInterval = 2000;
  var checkTimeout = timeout || 8000;
  
  for (var attempt = 1; attempt <= maxRetries; attempt++) {
    logStage("审核中检测", "第 " + attempt + "/" + maxRetries + " 次尝试");
    
    var statusNode = id("tv_feed_status").text("审核中").findOne(checkTimeout);
    if (statusNode) {
      logStage("审核中检测", "第 " + attempt + " 次尝试成功，找到审核中状态");
      return true;
    }
    
    // 尝试检测可能的其他状态文本
    var statusNodeDots = id("tv_feed_status").text("审核中...").findOne(checkTimeout);
    if (statusNodeDots) {
      logStage("审核中检测", "第 " + attempt + " 次尝试成功，找到审核中...状态");
      return true;
    }
    
    if (attempt < maxRetries) {
      logStage("审核中检测", "第 " + attempt + " 次未找到，" + retryInterval + "ms 后重试");
      sleep(retryInterval);
    }
  }
  
  logStage("审核中检测", "所有重试完成，未找到审核中状态");
  return false;
}

function buildAuthHeaders() {
  var headers = {};
  if (CONFIG.remoteToken) {
    headers["Authorization"] = "Bearer " + CONFIG.remoteToken;
  }
  return headers;
}

function buildUrl(path) {
  return CONFIG.remoteBaseUrl.replace(/\/+$/, "") + path;
}

function getRemotePollPolicy(elapsedMs) {
  var schedule = CONFIG.remotePollSchedule;
  if (schedule && schedule.length) {
    for (var i = 0; i < schedule.length; i++) {
      var item = schedule[i];
      if (item && typeof item.endMs === "number" && elapsedMs < item.endMs) {
        return item;
      }
    }
  }
  return { endMs: CONFIG.remotePollTimeoutMs, intervalMs: CONFIG.remotePollIntervalMs, allowRequest: true };
}

function buildRemotePollStageText(policy) {
  if (!policy) {
    return "";
  }
  var endMs = typeof policy.endMs === "number" ? policy.endMs : 0;
  var intervalMs = typeof policy.intervalMs === "number" ? policy.intervalMs : 0;
  if (policy.allowRequest) {
    return "endMs=" + endMs + ", intervalMs=" + intervalMs;
  }
  return "endMs=" + endMs + ", silent";
}

function getErrorMessage(e) {
  if (!e) {
    return "";
  }
  if (typeof e === "string") {
    return e;
  }
  if (e && typeof e.message === "string") {
    return e.message;
  }
  try {
    return String(e);
  } catch (e2) {
    return "";
  }
}

function shouldFallbackForErrorMessage(msg) {
  var m = String(msg || "");
  if (!m) {
    return false;
  }
  if (CONFIG.remoteFallbackOnTimeout && m.indexOf("轮询任务超时") >= 0) {
    return true;
  }
  if (CONFIG.remoteFallbackOnTaskFailed && (m.indexOf("任务失败:") >= 0 || m.indexOf("轮询任务失败") >= 0)) {
    return true;
  }
  if (CONFIG.remoteFallbackOnNetworkError && m.indexOf("轮询连续错误达到阈值") >= 0) {
    return true;
  }
  if (CONFIG.remoteFallbackOnNetworkError && (m.indexOf("批量生成接口请求失败") >= 0 || m.indexOf("批量生成接口返回失败") >= 0)) {
    return true;
  }
  return false;
}

function runWithOverallTimeout(startAt, fn) {
  if (!CONFIG.remoteOverallTimeoutMs || CONFIG.remoteOverallTimeoutMs <= 0) {
    return fn();
  }
  if (Date.now() - startAt >= CONFIG.remoteOverallTimeoutMs) {
    throw new Error("获取发帖内容整体超时");
  }
  return fn();
}

function fetchRemotePostDataByGenerate() {
  var url = buildUrl(CONFIG.remoteGeneratePath);
  var res = http.postJson(url, CONFIG.remotePayload, {
    headers: buildAuthHeaders(),
    timeout: CONFIG.remoteTimeoutSec
  });
  if (!res || res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error("发帖 API 请求失败：" + (res ? (res.statusCode + " " + res.statusMessage) : "no response"));
  }
  var json = res.body.json();
  if (!json || !json.success || !json.data) {
    throw new Error("发帖 API 返回失败");
  }
  // 保存 taskId 用于后续回调
  postTaskId = json.data.taskId;
  logStage("生成内容", "taskId=" + postTaskId);
  return json.data;
}

function fetchRemotePostDataByBatch() {
  var url = buildUrl(CONFIG.remoteBatchPath);
  var payload = {
    count: 1,
    useTopic: CONFIG.remotePayload.useTopic,
    mode: CONFIG.remotePayload.mode
  };
  var res = http.postJson(url, payload, {
    headers: buildAuthHeaders(),
    timeout: CONFIG.remoteTimeoutSec
  });
  if (!res || res.statusCode < 200 || res.statusCode >= 300) {
    throw new Error("批量生成接口请求失败：" + (res ? (res.statusCode + " " + res.statusMessage) : "no response"));
  }
  var json = res.body.json();
  if (!json || !json.success || !json.taskId) {
    throw new Error("批量生成接口返回失败");
  }
  var taskId = String(json.taskId);

  // 异步接口调用成功后息屏，参考 xh_signin.js 的息屏逻辑
  logStage("异步调用成功", "taskId=" + taskId + ", 执行息屏");
  if (device.isScreenOn()) {
    device.cancelKeepingAwake();
    shell("input keyevent 223", true);
    sleep(1000);
  }

  var startAt = Date.now();
  var deadline = startAt + CONFIG.remotePollTimeoutMs;
  var lastStageText = "";
  var consecutiveErrors = 0;
  var maxConsecutiveErrors = typeof CONFIG.remoteFallbackMaxConsecutiveErrors === "number" ? CONFIG.remoteFallbackMaxConsecutiveErrors : 0;
  logStage("轮询任务", "taskId=" + taskId + ", timeoutMs=" + CONFIG.remotePollTimeoutMs + ", 息屏等待中");
  while (true) {
    var now = Date.now();
    if (now >= deadline) {
      break;
    }
    var elapsedMs = now - startAt;
    var policy = getRemotePollPolicy(elapsedMs);
    var stageText = buildRemotePollStageText(policy);
    if (stageText !== lastStageText) {
      lastStageText = stageText;
      logStage("轮询任务阶段", stageText);
    }
    if (!policy.allowRequest) {
      var waitMs = policy.endMs - elapsedMs;
      if (waitMs < 200) {
        waitMs = 200;
      }
      if (now + waitMs > deadline) {
        waitMs = deadline - now;
      }
      sleep(waitMs);
      continue;
    }
    var taskUrl = buildUrl(CONFIG.remoteTaskPathPrefix + taskId);
    var taskRes = null;
    try {
      taskRes = http.get(taskUrl, {
        headers: buildAuthHeaders(),
        timeout: CONFIG.remoteTimeoutSec
      });
    } catch (e) {
    }
    if (!taskRes || taskRes.statusCode < 200 || taskRes.statusCode >= 300) {
      consecutiveErrors++;
      if (maxConsecutiveErrors > 0 && consecutiveErrors >= maxConsecutiveErrors) {
        throw new Error("轮询连续错误达到阈值：" + consecutiveErrors);
      }
      var intervalMs = typeof policy.intervalMs === "number" && policy.intervalMs > 0 ? policy.intervalMs : CONFIG.remotePollIntervalMs;
      if (Date.now() + intervalMs > deadline) {
        intervalMs = deadline - Date.now();
      }
      if (intervalMs > 0) {
        sleep(intervalMs);
      }
      continue;
    }
    var taskJson = taskRes.body.json();
    if (!taskJson || !taskJson.success) {
      consecutiveErrors++;
      if (maxConsecutiveErrors > 0 && consecutiveErrors >= maxConsecutiveErrors) {
        throw new Error("轮询连续错误达到阈值：" + consecutiveErrors);
      }
      var intervalMs2 = typeof policy.intervalMs === "number" && policy.intervalMs > 0 ? policy.intervalMs : CONFIG.remotePollIntervalMs;
      if (Date.now() + intervalMs2 > deadline) {
        intervalMs2 = deadline - Date.now();
      }
      if (intervalMs2 > 0) {
        sleep(intervalMs2);
      }
      continue;
    }
    consecutiveErrors = 0;
    if (taskJson.status === "completed") {
      var results = taskJson.results;
      if (results && results.length) {
        logStage("轮询任务完成", "taskId=" + taskId);
        // 获取到帖子内容后亮屏，参考 xh_signin.js 的亮屏逻辑
        logStage("获取到帖子内容", "执行亮屏处理后续逻辑");
        device.wakeUpIfNeeded();
        device.keepScreenDim(typeof CONFIG.keepScreenOnMs === "number" ? CONFIG.keepScreenOnMs : 1200000);
        // 保存 taskId 用于后续回调
        postTaskId = results[0].taskId;
        logStage("生成内容", "taskId=" + postTaskId);
        return results[0];
      }
      throw new Error("任务已完成但无 results");
    }
    if (taskJson.status === "failed" || taskJson.status === "error") {
      throw new Error("任务失败：" + (taskJson.error || taskJson.code || ""));
    }
    var intervalMs3 = typeof policy.intervalMs === "number" && policy.intervalMs > 0 ? policy.intervalMs : CONFIG.remotePollIntervalMs;
    if (Date.now() + intervalMs3 > deadline) {
      intervalMs3 = deadline - Date.now();
    }
    if (intervalMs3 > 0) {
      sleep(intervalMs3);
    }
  }
  throw new Error("轮询任务超时");
}

function fetchRemotePostData() {
  var overallStartAt = Date.now();
  if (!CONFIG.remoteUseAsync) {
    return runWithOverallTimeout(overallStartAt, function() {
      return fetchRemotePostDataByGenerate();
    });
  }
  if (!CONFIG.remoteEnableSyncFallback) {
    return runWithOverallTimeout(overallStartAt, function() {
      return fetchRemotePostDataByBatch();
    });
  }
  try {
    return runWithOverallTimeout(overallStartAt, function() {
      return fetchRemotePostDataByBatch();
    });
  } catch (e) {
    var asyncErrMsg = getErrorMessage(e);
    if (!shouldFallbackForErrorMessage(asyncErrMsg)) {
      throw e;
    }
    logStage("异步失败", asyncErrMsg);
    logStage("触发兜底", "切换同步 generate");
    try {
      return runWithOverallTimeout(overallStartAt, function() {
        return fetchRemotePostDataByGenerate();
      });
    } catch (e2) {
      var syncErrMsg = getErrorMessage(e2);
      throw new Error("异步失败：" + asyncErrMsg + "; 同步兜底失败：" + syncErrMsg);
    }
  }
}

function buildPostText(data) {
  var title = data.title ? String(data.title) : "";
  var content = data.content ? String(data.content) : "";
  var topics = [];
  if (data.topics && data.topics.length) {
    for (var i = 0; i < data.topics.length; i++) {
      var t = data.topics[i];
      if (t && t.name) {
        topics.push(String(t.name));
      }
    }
  }
  var topicsText = topics.join(" ");
  return [title, content, topicsText].filter(function(s) {
    return s && String(s).trim().length > 0;
  }).join("\n\n");
}

function clearDir(dirPath) {
  files.ensureDir(dirPath);
  var names = files.listDir(dirPath) || [];
  for (var i = 0; i < names.length; i++) {
    var p = dirPath + "/" + names[i];
    if (files.isFile(p)) {
      files.remove(p);
    }
  }
}

function guessFileName(url, fallbackIndex) {
  var u = String(url || "");
  var name = u.replace(/\?.*$/, "").replace(/^.*\//, "");
  if (!name) {
    name = "image_" + fallbackIndex + ".jpg";
  }
  return name;
}

function getRemoteOrigin() {
  var m = String(CONFIG.remoteBaseUrl || "").match(/^(https?:\/\/[^\/]+)/i);
  return m ? m[1] : "";
}

function normalizeRemoteResourceUrl(url) {
  var u = String(url || "");
  if (/^https?:\/\//i.test(u)) {
    return u;
  }
  var origin = getRemoteOrigin();
  if (!origin) {
    return u;
  }
  if (u.charAt(0) === "/") {
    return origin + u;
  }
  return origin + "/" + u;
}

function downloadImagesToDir(images, dirPath) {
  clearDir(dirPath);
  if (!images || !images.length) {
    return 0;
  }
  var headers = buildAuthHeaders();
  var count = 0;
  var downloadedFiles = [];
  for (var i = 0; i < images.length; i++) {
    var img = images[i];
    if (!img || !img.url) {
      continue;
    }
    var url = normalizeRemoteResourceUrl(img.url);
    console.log("下载图片：" + url);
    var fileName = img.filename ? String(img.filename) : guessFileName(url, i + 1);
    var dest = dirPath + "/" + fileName;
    var res = http.get(url, {
      headers: headers
    });
    if (!res || res.statusCode < 200 || res.statusCode >= 300) {
      throw new Error("图片下载失败：" + (res ? (res.statusCode + " " + res.statusMessage) : "no response"));
    }
    files.writeBytes(dest, res.body.bytes());
    downloadedFiles.push(dest);
    count++;
  }
  
  // Android 15 修复：使用 Root 权限修复媒体扫描问题
  if (downloadedFiles.length > 0) {
    logStage("媒体扫描", "Root 方案：修复权限 + 触发扫描");
    try {
      // 步骤 1: 修改文件权限为 644 (全局可读)
      logStage("步骤 1", "Root: 修改文件权限为 644");
      for (var j = 0; j < downloadedFiles.length; j++) {
        var chmodCmd = "chmod 644 \"" + downloadedFiles[j] + "\"";
        var chmodResult = shell(chmodCmd, true); // 使用 Root
        if (chmodResult.code === 0) {
          console.log("权限修改成功：" + downloadedFiles[j]);
        } else {
          console.error("权限修改失败：" + downloadedFiles[j]);
        }
        sleep(50);
      }
      sleep(500);
      
      // 步骤 2: 修改目录权限为 755
      logStage("步骤 2", "Root: 修改目录权限为 755");
      var chmodDirCmd = "chmod 755 \"" + dirPath + "\"";
      var chmodDirResult = shell(chmodDirCmd, true);
      if (chmodDirResult.code === 0) {
        logStage("目录权限修改成功", dirPath);
      } else {
        logStage("目录权限修改失败", "code=" + chmodDirResult.code);
      }
      sleep(500);
      
      // 步骤 3: 修改文件所有者为 media_rw
      logStage("步骤 3", "Root: 修改文件所有者为 media_rw");
      for (var j = 0; j < downloadedFiles.length; j++) {
        var chownCmd = "chown media_rw:media_rw \"" + downloadedFiles[j] + "\"";
        var chownResult = shell(chownCmd, true);
        if (chownResult.code === 0) {
          console.log("所有者修改成功：" + downloadedFiles[j]);
        } else {
          console.error("所有者修改失败：" + downloadedFiles[j]);
        }
        sleep(50);
      }
      sleep(500);
      
      // 步骤 4: 清除媒体存储数据
      logStage("步骤 4", "Root: 清除媒体存储数据");
      var clearCmd = "pm clear com.android.providers.media";
      var clearResult = shell(clearCmd, true);
      console.log("清除媒体存储 code: " + clearResult.code);
      sleep(1000);
      
      var stopCmd = "am force-stop com.android.providers.media";
      var stopResult = shell(stopCmd, true);
      console.log("force-stop code: " + stopResult.code);
      sleep(500);
      
      // 步骤 5: 使用 Root 权限触发媒体扫描 (content call)
      logStage("步骤 5", "Root: content call scan_volume");
      var scanCmd = "content call --uri content://media --method scan_volume --arg external_primary";
      var scanResult = shell(scanCmd, true);
      console.log("scan_volume (Root) code: " + scanResult.code);
      
      if (scanResult.code === 0) {
        logStage("成功", "等待扫描完成 (10 秒)...");
        sleep(10000);
      } else {
        logStage("scan_volume 失败", "尝试 am broadcast");
        // 备用方案：使用 am broadcast
        for (var j = 0; j < downloadedFiles.length; j++) {
          var broadcastCmd = "am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://" + downloadedFiles[j];
          var broadcastResult = shell(broadcastCmd, true);
          if (broadcastResult.code === 0) {
            console.log("广播扫描成功：" + downloadedFiles[j]);
          }
          sleep(100);
        }
        sleep(3000);
      }
      
      logStage("媒体扫描完成", "已处理 " + downloadedFiles.length + " 个文件");
      
    } catch (e) {
      logStage("媒体扫描异常", getErrorMessage(e));
    }
  }
  
  return count;
}

// 调用发帖确认接口
function confirmPostSuccess(taskId, postId, success) {
  if (!taskId) {
    logStage("确认回调", "taskId 为空，跳过回调");
    return;
  }
  
  var url = buildUrl(CONFIG.remoteConfirmPath);
  var payload = {
    taskId: taskId,
    success: success
  };
  
  if (postId) {
    payload.postId = postId;
  }
  
  try {
    var res = http.postJson(url, payload, {
      headers: buildAuthHeaders(),
      timeout: 30
    });
    
    if (!res || res.statusCode < 200 || res.statusCode >= 300) {
      logStage("确认回调失败", "HTTP " + (res ? res.statusCode : "no response"));
      return false;
    }
    
    var json = res.body.json();
    if (json && json.success) {
      logStage("确认回调成功", "taskId=" + taskId + ", success=" + success);
      if (json.remainingUses !== undefined) {
        logStage("主题剩余次数", json.remainingUses);
      }
      return true;
    } else {
      logStage("确认回调返回失败", json ? (json.error || json.message) : "unknown error");
      return false;
    }
  } catch (e) {
    logStage("确认回调异常", getErrorMessage(e));
    return false;
  }
}

function main() {
  try {
    // 检查成功标记文件，如果存在则不再执行
    if (files.exists(MARK_FILE)) {
      logStage("跳过执行", "成功标记文件已存在：" + MARK_FILE);
      return;
    }
    
    logStage("开始执行");
    commonUtils.prepareDevice({ keepMs: CONFIG.keepScreenOnMs });
    logStage("设备准备", "已亮屏并保持唤醒 " + (CONFIG.keepScreenOnMs / 1000) + " 秒");
    commonUtils.forceStop(CONFIG.appPackage, CONFIG.useRoot);
    sleep(1500);
    logStage("清理状态", "已强制停止历史进程");

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
    if (!foregroundOk) {
      console.error("打开 APP 失败或未进入前台");
      return;
    }
    if (!commonUtils.ensureAppForeground(CONFIG.appPackage, CONFIG.appName, 30000, {})) {
      console.error("APP 未处于前台：" + CONFIG.appPackage);
      return;
    }
    
    // App 启动后会先出现广告页；必须等待广告结束或首页控件出现，否则后续点击全部会落空。
    // 参考 audi_signin.js 的成功逻辑：等待底部导航元素出现
    logStage("等待首页", "等待底部导航出现");
    var homePageDeadline = Date.now() + CONFIG.startupAdWaitMs;
    var homePageReady = false;
    while (Date.now() < homePageDeadline) {
      var tab = id("navigation_main_fifth_tab").findOne(800);
      if (tab) {
        logStage("首页已就绪", "底部导航已出现");
        homePageReady = true;
        break;
      }
      sleep(500);
    }
    
    if (!homePageReady) {
      logStage("启动失败", "首页未就绪，可能仍停留在广告页");
      return;
    }
    
    // 广告页关闭后还会有一个短暂稳定期
    sleep(3000);
    logStage("首页稳定", "等待 3000ms 后继续");
    
    logStage("启动 APP", "已进入前台");

    // 以控件出现作为等待条件；避免长时间固定 sleep 导致"快时浪费、慢时不够"
    logStage("进入发帖入口", "打开我的页并进入任务");
    
    // 参考 audi_signin.js 的成功逻辑：点击我的 Tab 后等待页面就绪
    var minePageReady = false;
    for (var i = 0; i < 3; i++) {
      commonUtils.clickById("navigation_main_fifth_tab", 20000);
      // 点击后先固定等待一段时间让页面开始加载
      sleep(1500);
      // 等待 personal_name 元素出现（最多 3000ms），这是页面就绪的标志
      var personalName = id("personal_name").findOne(3000);
      if (!personalName) {
        logStage("我的页面", "第 " + (i + 1) + " 次未找到 personal_name 元素");
        sleep(800);
        continue;
      }
      
      logStage("我的页面", "已通过 personal_name 确认进入【我的】页（第 " + (i + 1) + " 次）");
      minePageReady = true;
      break;
    }
    
    if (!minePageReady) {
      logStage("我的页面", "未能进入我的页，脚本终止");
      return;
    }
    
    commonUtils.clickByText("赚取奖励", 15000);
    sleep(CONFIG.waitAfterEarnRewardMs);
    logStage("赚取奖励等待", "已等待 " + CONFIG.waitAfterEarnRewardMs + "ms");
    commonUtils.clickFirstByText("去完成", 15000);

    logStage("远程生成", "请求发帖内容与图片");
    var remoteData = fetchRemotePostData();
    console.log("远程数据：" + JSON.stringify(remoteData));
    var postText = buildPostText(remoteData);
    logStage("下载图片", "写入本地目录：" + CONFIG.imageDir);
    downloadImagesToDir(remoteData.images || [], CONFIG.imageDir);

    logStage("编辑内容", "清理历史内容并填入新文案");
    clearEditTextById("content_edittext", 15000);
    deleteAllUploadedImages();
    commonUtils.setTextById("content_edittext", postText, 15000);
    var localImageCount = countImagesInDir(CONFIG.imageDir);
    if (localImageCount > 0) {
      logStage("上传图片", "local=" + localImageCount);
      commonUtils.clickById("home_layout_photo", 15000);
      waitForLeaveEditorPage(15000);
      runRecordedAuto(CONFIG.recordedAutoFile, 0);
      if (!waitForEditorPageReady(CONFIG.waitForEditorAfterAutoMs)) {
        console.log("录制回放后未回到编辑页，可能未点到确定");
        // 发布失败，回调告知服务端
        confirmPostSuccess(postTaskId, null, false);
        return;
      }
      var ok = waitForUploadSuccess(localImageCount, CONFIG.uploadWaitTimeoutMs);
      var uploadedElementCount = getUploadedImageElementCount();
      if (!ok) {
        console.log("图片上传等待超时，local=" + localImageCount + ", page=" + uploadedElementCount);
        // 发布失败，回调告知服务端
        confirmPostSuccess(postTaskId, null, false);
        return;
      }
      logStage("发布", "图片已上传，准备发布");
      commonUtils.clickById("common_title_right_desc_text", 15000);
      logStage("发布", "已点击发布按钮，等待 " + CONFIG.waitAfterPublish + "ms");
      sleep(CONFIG.waitAfterPublish);
      
      // 检查是否有二次确认按钮
      var continueBtn = id("publish_continue").findOne(2000);
      if (continueBtn) {
        logStage("发布", "发现二次确认按钮，点击继续发布");
        commonUtils.clickBoundsCenter(continueBtn);
        sleep(CONFIG.waitAfterPublish);
        logStage("发布", "二次确认等待完成，开始检测审核中状态");
      } else {
        logStage("发布", "未发现二次确认按钮，直接检测审核中状态");
      }
      
      if (isPostSuccess(5000)) {
        commonUtils.writeSuccessMark(MARK_FILE);
        logStage("结果校验", "已检测到审核中，写入成功打点文件");
        // 发布成功，回调确认
        confirmPostSuccess(postTaskId, null, true);
      } else {
        logStage("结果校验", "发帖结果校验失败，未找到审核中状态");
        // 发布失败，回调告知服务端
        confirmPostSuccess(postTaskId, null, false);
      }
    } else {
      commonUtils.clickById("common_title_right_desc_text", 15000);
      logStage("发布", "已点击发布按钮，等待 " + CONFIG.waitAfterPublish + "ms");
      sleep(CONFIG.waitAfterPublish);
      
      // 检查是否有二次确认按钮
      var continueBtn = id("publish_continue").findOne(2000);
      if (continueBtn) {
        logStage("发布", "发现二次确认按钮，点击继续发布");
        commonUtils.clickBoundsCenter(continueBtn);
        sleep(CONFIG.waitAfterPublish);
        logStage("发布", "二次确认等待完成，开始检测审核中状态");
      } else {
        logStage("发布", "未发现二次确认按钮，直接检测审核中状态");
      }
      
      if (isPostSuccess(5000)) {
        commonUtils.writeSuccessMark(MARK_FILE);
        logStage("结果校验", "已检测到审核中，写入成功打点文件");
        // 发布成功，回调确认
        confirmPostSuccess(postTaskId, null, true);
      } else {
        logStage("结果校验", "发帖结果校验失败，未找到审核中状态");
        // 发布失败，回调告知服务端
        confirmPostSuccess(postTaskId, null, false);
      }
    }
  } catch (e) {
    console.error(e);
    console.error("执行失败：" + e);
    // 异常情况下也尝试回调告知服务端
    try {
      confirmPostSuccess(postTaskId, null, false);
    } catch (confirmError) {
      logStage("异常回调失败", getErrorMessage(confirmError));
    }
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
