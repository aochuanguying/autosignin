"auto";

// 清理成功打点文件：建议由 AutoJS6 每日定时任务触发一次，
// 用于开始新一天时重置“当天已成功”的状态。
var CONFIG = {
    scriptDir: "/sdcard/脚本",
    markFilePattern: /_success\.log$/
};

if (!files.exists(CONFIG.scriptDir)) {
    console.log("目录不存在，无需清理: " + CONFIG.scriptDir);
    exit();
}

var entries = files.listDir(CONFIG.scriptDir) || [];
var matchedFiles = [];
var removedCount = 0;

for (var i = 0; i < entries.length; i++) {
    var fileName = entries[i];
    if (CONFIG.markFilePattern.test(fileName)) {
        matchedFiles.push(files.join(CONFIG.scriptDir, fileName));
    }
}

if (matchedFiles.length === 0) {
    console.log("未找到需要删除的 _success.log 文件");
}

for (var j = 0; j < matchedFiles.length; j++) {
    var path = matchedFiles[j];
    try {
        if (files.exists(path)) {
            files.remove(path);
            console.log("已删除: " + path);
            removedCount++;
        } else {
            console.log("不存在: " + path);
        }
    } catch (e) {
        console.error("删除失败: " + path + " " + e);
    }
}

console.log("清理完成，共删除 " + removedCount + " 个 success 标记文件");
