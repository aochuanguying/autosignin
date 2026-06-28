// 公共工具模块（AutoJS6）
//
// 设计要点：
// 1) 通过 eval(files.read(...)) 加载，因此文件内容以“返回对象字面量”的形式导出；
// 2) 只承载通用能力，不包含具体 App 的业务选择器与流程；
// 3) 关键动作尽量提供可配置项，避免在业务脚本里散落魔法值。
({
    // 成功打点文件根目录：与现有脚本保持一致，便于告警脚本统一判断
    markDir: "/sdcard/脚本",

    // 从脚本路径中提取不带扩展名的基名，用于推导默认打点文件名
    getScriptBaseName: function(scriptPath) {
        return String(scriptPath).replace(/^.*[\\/]/, "").replace(/\.js$/i, "");
    },

    getScriptDir: function() {
        try {
            var source = engines.myEngine().getSource();
            var sourcePath = String(source);
            return sourcePath.replace(/[\\/][^\\/]*$/, "");
        } catch (e) {
            return null;
        }
    },

    nowText: function() {
        try {
            return new Date().toLocaleString();
        } catch (e) {
            return String(new Date());
        }
    },

    // 构造成功打点文件路径：/sdcard/脚本/<name>_success.log
    buildMarkFilePath: function(scriptName) {
        return this.markDir + "/" + scriptName + "_success.log";
    },

    // 构造运行态文件路径：用于锁文件、运行中标记等共享状态
    buildRuntimeFilePath: function(fileName) {
        return this.markDir + "/" + fileName;
    },

    buildLockFilePath: function(lockName) {
        return this.buildRuntimeFilePath(lockName + ".lock");
    },

    // 获取当前脚本的打点文件路径：优先从当前脚本文件名推导，无法获取时使用 fallback
    getCurrentMarkFilePath: function(fallbackScriptName) {
        try {
            var source = engines.myEngine().getSource();
            return this.buildMarkFilePath(this.getScriptBaseName(source));
        } catch (e) {
            return this.buildMarkFilePath(fallbackScriptName);
        }
    },

    removeIfExists: function(path) {
        try {
            if (files.exists(path)) {
                files.remove(path);
            }
        } catch (e) {
        }
    },

    ensureDirExists: function(dirPath) {
        try {
            if (!files.exists(dirPath)) {
                files.createWithDirs(files.join(dirPath, ".keep"));
                files.remove(files.join(dirPath, ".keep"));
            }
        } catch (e) {
        }
    },

    writeTextFile: function(filePath, content) {
        try {
            var parent = String(filePath).replace(/[\\/][^\\/]*$/, "");
            if (parent && parent !== filePath) {
                this.ensureDirExists(parent);
            }
            files.write(filePath, String(content));
            return true;
        } catch (e) {
            return false;
        }
    },

    // 设备准备：亮屏、保持唤醒、解锁
    prepareDevice: function(options) {
        var opts = options || {};
        // 默认 15 分钟，覆盖大部分脚本执行场景
        // 复杂脚本（如 audi_post）建议在 CONFIG 中显式配置 keepMs
        var keepMs = typeof opts.keepMs === "number" ? opts.keepMs : 900000;
        if (!device.isScreenOn()) {
            device.wakeUp();
            sleep(1000);
        }
        device.keepScreenOn(keepMs);
        if (opts.skipSwipeUnlock) {
            return;
        }
        // 解锁方法：使用 keyevent 82（菜单键）- 经测试在 LineageOS 上有效
        shell("input keyevent 82", true);
        sleep(2000);
    },

    // 强制停止 App：用于清理残留状态；useRoot=true 时依赖设备 Root 能力
    forceStop: function(packageName, useRoot) {
        if (!packageName) {
            return;
        }
        try {
            shell("am force-stop " + packageName, !!useRoot);
        } catch (e) {
        }
    },

    waitForAppForeground: function(packageName, timeoutMs) {
        var deadline = Date.now() + (timeoutMs || 15000);
        while (Date.now() < deadline) {
            try {
                if (currentPackage() === packageName) {
                    return true;
                }
            } catch (e) {
            }
            sleep(300);
        }
        return false;
    },

    // 确保 App 在前台：为减少“偶发拉起失败”，采用多策略兜底
    ensureAppForeground: function(packageName, appName, timeoutMs, options) {
        var opts = options || {};
        var deadline = Date.now() + (timeoutMs || 30000);
        while (Date.now() < deadline) {
            if (this.waitForAppForeground(packageName, 800)) {
                return true;
            }
            // 前台拉起采用多策略兜底：launchPackage -> launchApp(name) -> monkey
            if (!opts.skipLaunchPackage) {
                try {
                    app.launchPackage(packageName);
                } catch (e) {
                }
            }
            if (appName && !opts.skipLaunchAppName) {
                try {
                    launchApp(appName);
                } catch (e) {
                }
            }
            if (!opts.skipMonkey) {
                try {
                    shell("monkey -p " + packageName + " -c android.intent.category.LAUNCHER 1", true);
                } catch (e) {
                }
            }
            sleep(1200);
        }
        return false;
    },

    // 通用条件等待：用于替换纯 sleep（例如等待包名、等待控件出现）
    waitUntil: function(checkFn, timeoutMs, intervalMs) {
        var deadline = Date.now() + (timeoutMs || 10000);
        var interval = typeof intervalMs === "number" ? intervalMs : 300;
        while (Date.now() < deadline) {
            try {
                if (checkFn()) {
                    return true;
                }
            } catch (e) {
            }
            sleep(interval);
        }
        return false;
    },

    // 点击控件中心点：比 w.click() 更通用（部分控件 click 不稳定）
    clickBoundsCenter: function(w) {
        var b = w.bounds();
        click(b.centerX(), b.centerY());
    },

    // 优先走控件自身 click；若控件本身不可点击，则向上找可点击父节点；最后才退回中心点点击。
    // 这样可以兼容底部 Tab、列表项等“子节点有 id，但真正可点击的是父容器”的场景。
    smartClick: function(w) {
        if (!w) {
            throw new Error("smartClick 传入了空控件");
        }
        try {
            if (typeof w.click === "function" && w.click()) {
                return true;
            }
        } catch (e) {
        }

        try {
            var parent = w.parent();
            for (var i = 0; parent && i < 5; i++) {
                if (typeof parent.click === "function" && parent.click()) {
                    return true;
                }
                parent = parent.parent();
            }
        } catch (e) {
        }

        this.clickBoundsCenter(w);
        return true;
    },

    findOneById: function(viewId, timeoutMs) {
        return id(viewId).findOne(timeoutMs || 10000);
    },

    findOneByText: function(t, timeoutMs) {
        return text(t).findOne(timeoutMs || 10000);
    },

    // 通过 ID 查找并点击；找不到直接抛错，便于上层 try/catch 统一处理
    clickById: function(viewId, timeoutMs) {
        var w = this.findOneById(viewId, timeoutMs);
        if (!w) {
            throw new Error("未找到ID: " + viewId);
        }
        this.smartClick(w);
        sleep(1200);
        return w;
    },

    // 通过文本查找并点击；用于“文案相对稳定”的入口（例如菜单项）
    clickByText: function(t, timeoutMs) {
        var w = this.findOneByText(t, timeoutMs);
        if (!w) {
            throw new Error("未找到文本: " + t);
        }
        this.smartClick(w);
        sleep(1200);
        return w;
    },

    // 点击第一个匹配文本：用于存在多个同名入口的场景
    clickFirstByText: function(t, timeoutMs) {
        var end = Date.now() + (timeoutMs || 10000);
        while (Date.now() < end) {
            var ws = text(t).find();
            if (ws && ws.size() > 0) {
                this.smartClick(ws.get(0));
                sleep(1200);
                return ws.get(0);
            }
            sleep(300);
        }
        throw new Error("未找到文本(第一个): " + t);
    },

    // 输入框设置文本：优先使用控件 setText，无法使用时回退到全局 setText
    setTextById: function(viewId, value, timeoutMs) {
        var w = this.findOneById(viewId, timeoutMs);
        if (!w) {
            throw new Error("未找到ID: " + viewId);
        }
        w.click();
        sleep(300);
        if (typeof w.setText === "function") {
            w.setText(value);
        } else {
            setText(value);
        }
        sleep(800);
        return w;
    },

    clearTextById: function(viewId, timeoutMs) {
        return this.setTextById(viewId, "", timeoutMs);
    },

    writeSuccessMark: function(markFilePath) {
        files.write(markFilePath, "success " + this.nowText());
    },

    // 统一收尾：可选强杀目标 App；取消保持唤醒；回桌面；可选熄屏
    cleanup: function(options) {
        var opts = options || {};
        try {
            if (opts.packageName && opts.forceStop) {
                this.forceStop(opts.packageName, opts.useRoot);
                sleep(1500);
            }
        } catch (e) {
        }
        try {
            device.cancelKeepingAwake();
        } catch (e) {
        }
        try {
            home();
            sleep(800);
        } catch (e) {
        }
        if (opts.screenOff) {
            try {
                // keyevent 223：熄屏（保持与原脚本一致的“跑完即熄屏”习惯）
                shell("input keyevent 223", true);
            } catch (e) {
            }
        }
    },

    // 执行录制回放：用于图片选择/上传等难以稳定选择器化的流程
    runRecordedAuto: function(autoFilePath, waitMs) {
        if (!files.exists(autoFilePath)) {
            throw new Error("未找到录制文件: " + autoFilePath);
        }
        engines.execAutoFile(autoFilePath);
        var actualWaitMs = 20000;
        if (typeof waitMs === "number") {
            actualWaitMs = waitMs;
        }
        if (actualWaitMs > 0) {
            sleep(actualWaitMs);
        }
    }
})
