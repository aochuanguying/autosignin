// AutoJS 告警脚本 - 通过 Bark 推送通知到手机

var CONFIG = {
    barkUrl: "https://api.day.app/Asbu4fr2HjGAjKbHANNbLS",
    iconUrl: "https://sf16-passport-sg.ibytedtos.com/img/user-avatar-alisg/4b93e0266e7787e68d447ef7231066fe~128x128.image",
    phoneNumber: "18953272532",
    apiBaseUrl: "http://localhost:5000",
    screenOffAfterRun: true
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
var AUDI_MARK_FILE = commonUtils.buildMarkFilePath("audi_signin");
var RQRUN_MARK_FILE = commonUtils.buildMarkFilePath("rqrun_signin");
var AUDI_POST_MARK_FILE = commonUtils.buildMarkFilePath("audi_post");
var SCHEDULER_LOCK_FILE = commonUtils.buildLockFilePath("hourly_scheduler");

// 请求无障碍权限
auto.waitFor();

// 通过 Bark 发送通知
function sendBarkNotification(title, message) {
    try {
        console.log("[Bark] 📱 开始发送 Bark 通知");
        
        // 使用标准格式：https://api.day.app/KEY/标题/内容?icon=图标 URL
        var url = CONFIG.barkUrl + "/" + encodeURIComponent(title) + "/" + encodeURIComponent(message) + "?icon=" + encodeURIComponent(CONFIG.iconUrl);
        console.log("[Bark] 请求 URL: " + url);
        
        var response = http.get(url);
        
        var responseBody = response.body.string();
        console.log("[Bark] HTTP 状态码：" + response.statusCode);
        console.log("[Bark] 响应内容：" + responseBody);
        
        if (response.statusCode === 200) {
            var result = JSON.parse(responseBody);
            if (result.code === 200) {
                console.log("[Bark] ✅ 通知发送成功！");
                return true;
            } else {
                console.error("[Bark] ❌ Bark API 返回失败：" + (result.message || "未知错误"));
                return false;
            }
        } else {
            console.error("[Bark] ❌ HTTP 错误：" + response.statusCode);
            return false;
        }
    } catch (e) {
        console.error("[Bark] ❌ 异常：" + e);
        console.error("[Bark] ❌ 堆栈：" + e.stack);
        return false;
    }
}

// 通过 Telecom API 拨打电话
function callByApi() {
    try {
        console.log("[callByApi] 📞 开始调用 Telecom API");
        console.log("[callByApi] API 地址：" + CONFIG.apiBaseUrl);
        
        // 构建请求
        var url = CONFIG.apiBaseUrl + "/api/v1/call";
        console.log("[callByApi] 请求 URL: " + url);
        console.log("[callByApi] 目标号码：" + CONFIG.phoneNumber);
        
        // 使用 http.postJson 发送 JSON 请求
        var response = http.postJson(url, {
            phone_number: CONFIG.phoneNumber
        });
        
        var responseBody = response.body.string();
        console.log("[callByApi] HTTP 状态码：" + response.statusCode);
        console.log("[callByApi] 响应内容：" + responseBody);
        
        if (response.statusCode === 200) {
            var result = JSON.parse(responseBody);
            if (result.success) {
                console.log("[callByApi] ✅ API 调用成功！");
                console.log("[callByApi] 📋 消息：" + result.message);
                return true;
            } else {
                console.error("[callByApi] ❌ API 返回失败：" + (result.message || "未知错误"));
                return false;
            }
        } else {
            console.error("[callByApi] ❌ HTTP 错误：" + response.statusCode);
            return false;
        }
    } catch (e) {
        console.error("[callByApi] ❌ 异常：" + e);
        console.error("[callByApi] ❌ 堆栈：" + e.stack);
        return false;
    }
}

function main() {
    try {
        console.log("========================================");
        console.log("🔔 auto_call.js 开始执行");
        console.log("📱 推送设备：Asbu4fr2HjGAjKbHANNbLS");
        console.log("========================================");
        
        if (files.exists(SCHEDULER_LOCK_FILE)) {
            console.log("⚠️ 检测到串行调度仍在执行，本次跳过告警检查：" + SCHEDULER_LOCK_FILE);
            return;
        }
        var audiOk = files.exists(AUDI_MARK_FILE);
        var rqrunOk = files.exists(RQRUN_MARK_FILE);
        var audiPostOk = files.exists(AUDI_POST_MARK_FILE);
        
        console.log("📊 任务状态检查：");
        console.log("   - audi_signin: " + (audiOk ? "✅ 成功" : "❌ 失败"));
        console.log("   - rqrun_signin: " + (rqrunOk ? "✅ 成功" : "❌ 失败"));
        console.log("   - audi_post: " + (audiPostOk ? "✅ 成功" : "❌ 失败"));
        
        if (audiOk && rqrunOk && audiPostOk) {
            console.log("✅ 截至本次检查窗口，签到和发帖均成功，不发送通知");
            return;
        }
        console.log("⚠️ 截至本次检查窗口，存在任务未成功，准备发送告警");

        // 构建告警消息
        var failureDetails = [];
        if (!audiOk) failureDetails.push("【奥迪签到】失败");
        if (!rqrunOk) failureDetails.push("【RQrun 签到】失败");
        if (!audiPostOk) failureDetails.push("【奥迪发帖】失败");
        
        var title = "签到任务异常";
        var message = failureDetails.join("、");
        
        console.log("📱 发送 Bark 通知：" + title + " - " + message);
        
        // 发送 Bark 通知
        var notificationSuccess = sendBarkNotification(title, message);
        
        if (notificationSuccess) {
            console.log("✅ Bark 通知已成功发送");
        } else {
            console.log("❌ Bark 通知发送失败");
        }
        
        // 拨打电话
        console.log("📞 拨打电话告警...");
        var callSuccess = callByApi();
        
        if (callSuccess) {
            console.log("✅ 电话已成功拨出");
            console.log("⏳ 等待 3 秒确保电话已拨出...");
            sleep(3000);
        } else {
            console.log("❌ 电话拨出失败");
        }
    } catch (e) {
        console.error("❌ 异常：" + e);
        console.error("❌ 执行失败：" + e);
        console.error("❌ 堆栈跟踪：" + e.stack);
    } finally {
        console.log("🔚 开始执行清理操作...");
        commonUtils.cleanup({
            screenOff: CONFIG.screenOffAfterRun
        });
        console.log("✅ 清理操作完成");
        console.log("========================================");
        console.log("🏁 auto_call.js 执行结束");
        console.log("========================================");
    }
}

main();
