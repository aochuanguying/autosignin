// AutoJS 测试脚本 - RQrun 自动签到
"auto";

var CONFIG = {
    appPackage: "cn.runningquotient.rq",
    appName: "RQrun",
    startupAdWaitMs: 12000,
    openButtonDesc: "open",
    checkinEntryId: "nav_item_checkin",
    checkinSuccessTitleId: "tv_setting_header_view_title",
    checkinSuccessTitleText: "RQ签到",
    sidebarOpenTimeoutMs: 5000,
    checkinSuccessTimeoutMs: 15000,
    waitAfterCheckinMs: 10000,
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
var MARK_FILE = commonUtils.getCurrentMarkFilePath("rqrun_signin");

auto.waitFor();

function logStage(stage, detail) {
    if (detail) {
        console.log("[rqrun_signin] " + stage + " - " + detail);
        return;
    }
    console.log("[rqrun_signin] " + stage);
}

function checkRunnerLevelReady() {
    logStage("检查首页加载", "查找 tv_runner_run_level 元素");
    var levelNode = id("tv_runner_run_level").findOne(3000);
    if (!levelNode) {
        logStage("检查首页加载", "未找到 tv_runner_run_level 元素");
        return false;
    }
    
    var levelText = levelNode.text();
    if (!levelText) {
        logStage("检查首页加载", "tv_runner_run_level 文本为空");
        return false;
    }
    
    // 提取数字并判断是否 > 0
    var levelNum = parseInt(levelText.replace(/[^0-9]/g, ""), 10);
    if (isNaN(levelNum)) {
        logStage("检查首页加载", "tv_runner_run_level 文本非数字：" + levelText);
        return false;
    }
    
    if (levelNum > 0) {
        logStage("检查首页加载", "tv_runner_run_level 值为 " + levelNum + "，首页已加载完毕");
        return true;
    }
    
    logStage("检查首页加载", "tv_runner_run_level 值为 " + levelNum + "，继续等待");
    return false;
}

function waitForMainPageReadyWithLevelCheck() {
    logStage("等待首页", "先检查 tv_runner_run_level 元素");
    var deadline = Date.now() + CONFIG.startupAdWaitMs;
    
    // 先等待 tv_runner_run_level > 0
    var levelReady = false;
    while (Date.now() < deadline) {
        if (checkRunnerLevelReady()) {
            levelReady = true;
            break;
        }
        sleep(500);
    }
    
    if (!levelReady) {
        logStage("等待首页", "tv_runner_run_level 检查超时");
        return false;
    }
    
    // 再等待侧边栏按钮出现
    logStage("等待首页", "等待侧边栏按钮出现");
    deadline = Date.now() + CONFIG.startupAdWaitMs;
    while (Date.now() < deadline) {
        var openBtn = className("android.widget.ImageButton").desc(CONFIG.openButtonDesc).findOne(800);
        if (openBtn) {
            logStage("首页已就绪", "侧边栏按钮已出现");
            return true;
        }
        sleep(500);
    }
    
    logStage("等待首页", "侧边栏按钮未出现");
    return false;
}

function launchRqrunApp() {
    logStage("启动 APP", "准备拉起 " + CONFIG.appName);
    for (var i = 0; i < 10; i++) {
        try {
            launchApp(CONFIG.appName);
        } catch (e) {
        }
        if (commonUtils.waitForAppForeground(CONFIG.appPackage, 1500)) {
            logStage("启动 APP", "已进入前台");
            return true;
        }
        sleep(800);
    }
    logStage("启动 APP", "拉起失败");
    return false;
}

function openSidebar() {
    // "open" 为侧边栏按钮的 content-desc，属于首页的业务特征；
    // 这里不只关心"点了按钮",还要关心"签到入口是否真的出现"。
    logStage("打开侧边栏", "准备点击侧边栏按钮");
    var openBtn = className("android.widget.ImageButton").desc(CONFIG.openButtonDesc).findOne(20000);
    if (!openBtn) {
        logStage("打开侧边栏", "未找到侧边栏按钮");
        return false;
    }
    commonUtils.clickBoundsCenter(openBtn);
    sleep(1500);
    var sidebarReady = !!id(CONFIG.checkinEntryId).findOne(CONFIG.sidebarOpenTimeoutMs);
    if (sidebarReady) {
        logStage("打开侧边栏", "已点击 open 按钮并看到签到入口");
        return true;
    }
    logStage("打开侧边栏", "未看到签到入口");
    return false;
}

function performCheckin() {
    logStage("执行签到", "准备点击签到入口");
    commonUtils.clickById(CONFIG.checkinEntryId, 20000);
    logStage("执行签到", "已点击签到入口，等待结果页出现");

    var successNode = id(CONFIG.checkinSuccessTitleId).text(CONFIG.checkinSuccessTitleText).findOne(CONFIG.checkinSuccessTimeoutMs);
    if (!successNode) {
        logStage("执行签到", "未看到成功标题，可能签到失败");
        return false;
    }

    // 保留少量缓冲，兼容页面动画和接口刷新；真正的成功判断仍以标题栏
    // "tv_setting_header_view_title = RQ 签到"出现为准。
    sleep(CONFIG.waitAfterCheckinMs);
    commonUtils.writeSuccessMark(MARK_FILE);
    logStage("执行签到", "已看到" + CONFIG.checkinSuccessTitleText + "标题并写入成功打点文件");
    return true;
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

        if (!launchRqrunApp()) {
            logStage("启动失败", "打开 APP 失败或未进入前台");
            return;
        }

        if (!waitForMainPageReadyWithLevelCheck()) {
            logStage("启动失败", "首页未就绪，可能仍停留在广告页");
            return;
        }
        logStage("首页已就绪", "tv_runner_run_level > 0 且侧边栏按钮已出现");

        if (!openSidebar()) {
            logStage("打开侧边栏", "失败，未看到签到入口");
            return;
        }

        if (!performCheckin()) {
            logStage("签到失败", "未看到标题");
            return;
        }
    } catch (e) {
        console.error(e);
        console.error("执行失败：" + e);
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
