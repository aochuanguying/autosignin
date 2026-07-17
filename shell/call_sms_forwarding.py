#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
未接来电 & 短信转发服务
运行在已 Root 的 Android 设备 Termux 环境中
通过 Root + sqlite3 轮询系统数据库，检测新事件并通过 HTTP API 转发到远程服务器
"""

import json
import subprocess
import logging
import logging.handlers
import os
import time
import threading
import urllib.request
import urllib.error

# ============================================================
# 配置项（直接修改此处，重启不丢失）
# ============================================================

# 测试模式：True = 仅记录到日志文件不调 API，False = 正常转发
TEST_MODE = False

# 脚本运行目录（日志存放于此）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 日志文件路径（放在脚本同目录下）
LOG_FILE = os.path.join(SCRIPT_DIR, "call_sms_forwarding.log")

# 事件日志文件路径（测试模式下使用）
EVENT_LOG_FILE = os.path.join(SCRIPT_DIR, "call_sms_events.log")

# Bark 推送配置（iOS 实时通知）
BARK_URL = "https://api.day.app/Asbu4fr2HjGAjKbHANNbLS"
BARK_ENABLED = True  # 是否启用 Bark 推送
BARK_ICON = "https://sf16-passport-sg.ibytedtos.com/img/user-avatar-alisg/4b93e0266e7787e68d447ef7231066fe~128x128.image"

# 服务器基础 URL（生产环境）
SERVER_BASE_URL = "https://yqad.hxfssc.com:8088"

# 转发 API 路径
CALL_FORWARD_PATH = "/api/posts/mobile/missed-calls"
SMS_FORWARD_PATH = "/api/posts/mobile/sms"

# API Token（外部设备访问，格式：Bearer <token>）
API_TOKEN = "api_token_1640a8b188784e52e08e11eb8dcab3a9fcea5a8d6b03e1235d6705938eed853a"

# 轮询间隔（秒）
CALL_POLL_INTERVAL = 10
SMS_POLL_INTERVAL = 5

# HTTP 请求超时（秒）
HTTP_TIMEOUT = 15

# 状态数据库路径（放在脚本运行目录下）
STATE_DB = "/data/data/com.termux/files/home/scripts/call_sms_forwarding_state.db"

# 数据库路径
CALL_LOG_DB = "/data/data/com.android.providers.contacts/databases/calllog.db"
SMS_DB = "/data/data/com.android.providers.telephony/databases/mmssms.db"

# Termux sqlite3 路径
SQLITE3_PATH = "/data/data/com.termux/files/usr/bin/sqlite3"

# ============================================================
# 日志配置
# ============================================================

def setup_logging():
    """配置日志：同时输出到文件和控制台"""
    os.makedirs(os.path.dirname(LOG_FILE) if os.path.dirname(LOG_FILE) else SCRIPT_DIR, exist_ok=True)

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # 文件 handler（带轮转，每个文件最大 1MB，保留 3 个备份）
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=1 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()


# ============================================================
# 状态数据库管理
# 四个独立状态：
#   http_call_ts / http_call_id   → HTTP转发 + 未接来电
#   http_sms_ts  / http_sms_id    → HTTP转发 + 短信
#   bark_call_ts / bark_call_id   → Bark推送 + 未接来电
#   bark_sms_ts  / bark_sms_id    → Bark推送 + 短信
# ============================================================

def run_root_sql(sql):
    """以 root 身份执行 sqlite3 命令，返回 (returncode, stdout, stderr)
    将 SQL 写入 sdcard 临时文件，通过 shell 重定向执行，避免引号转义。"""
    tmp_sql = f"/sdcard/tmp_sql_{int(time.time() * 1000)}.sql"
    try:
        with open(tmp_sql, "w") as f:
            f.write(sql)
        cmd = ['su', '-c', f'{SQLITE3_PATH} {STATE_DB} < {tmp_sql}']
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        logger.error(f"run_root_sql exception: {e}")
        return 1, "", str(e)
    finally:
        try:
            os.remove(tmp_sql)
        except Exception:
            pass


def init_state_db():
    """初始化状态数据库（纯数字/文本字段，无 JSON，无引号转义问题）"""
    create_sql = (
        "CREATE TABLE IF NOT EXISTS forward_state ("
        "  id INTEGER PRIMARY KEY,"
        "  http_call_ts TEXT DEFAULT '0',"
        "  http_call_id INTEGER DEFAULT 0,"
        "  http_sms_ts TEXT DEFAULT '0',"
        "  http_sms_id INTEGER DEFAULT 0,"
        "  bark_call_ts TEXT DEFAULT '0',"
        "  bark_call_id INTEGER DEFAULT 0,"
        "  bark_sms_ts TEXT DEFAULT '0',"
        "  bark_sms_id INTEGER DEFAULT 0"
        ");"
    )
    insert_sql = (
        "INSERT OR IGNORE INTO forward_state (id) VALUES (1);"
    )

    try:
        rc, out, err = run_root_sql(create_sql)
        if rc != 0:
            logger.error(f"创建状态表失败：{err}")
            return False
        rc, out, err = run_root_sql(insert_sql)
        if rc != 0:
            logger.error(f"初始化状态行失败：{err}")
            return False
        return True
    except Exception as e:
        logger.error(f"初始化状态数据库异常：{e}")
        return False


# 内存缓存：保存最后一次成功加载的状态，防止数据库故障时回退到 id=0 导致全量重发
_last_good_state = None


def load_state():
    """加载全部四个状态，数据库故障时使用上次成功加载的缓存"""
    global _last_good_state
    init_state_db()

    try:
        sql = "SELECT http_call_ts, http_call_id, http_sms_ts, http_sms_id, bark_call_ts, bark_call_id, bark_sms_ts, bark_sms_id FROM forward_state WHERE id = 1;"
        rc, out, err = run_root_sql(sql)

        if rc == 0 and out:
            parts = out.split("|")
            if len(parts) >= 8:
                state = {
                    "http_call": {"ts": parts[0] or "0", "id": int(parts[1]) if parts[1] else 0},
                    "http_sms":  {"ts": parts[2] or "0", "id": int(parts[3]) if parts[3] else 0},
                    "bark_call": {"ts": parts[4] or "0", "id": int(parts[5]) if parts[5] else 0},
                    "bark_sms":  {"ts": parts[6] or "0", "id": int(parts[7]) if parts[7] else 0},
                }
                _last_good_state = state
                return state
        logger.warning(f"加载状态失败，rc={rc}, out='{out}', err='{err}'")
    except Exception as e:
        logger.warning(f"加载状态异常：{e}")

    # 使用上次成功加载的缓存，避免回退到 id=0 导致全量重发
    if _last_good_state is not None:
        logger.warning("使用内存缓存状态（避免全量重发）")
        return _last_good_state

    # 仅首次启动且数据库完全不可用时才 fallback
    return {
        "http_call": {"ts": "0", "id": 0},
        "http_sms":  {"ts": "0", "id": 0},
        "bark_call": {"ts": "0", "id": 0},
        "bark_sms":  {"ts": "0", "id": 0},
    }


def save_state(state, update_type='http_call'):
    """保存单个状态到数据库

    Args:
        state: 状态字典（由 load_state() 返回的整体结构）
        update_type: 'http_call' | 'http_sms' | 'bark_call' | 'bark_sms'
    """
    init_state_db()

    entry = state.get(update_type, {})
    ts = entry.get("ts", "0")
    rid = entry.get("id", 0)

    # 只用数字和文本，完全不需要引号转义
    sql = f"UPDATE forward_state SET {update_type}_ts = '{ts}', {update_type}_id = {rid} WHERE id = 1;"

    try:
        rc, out, err = run_root_sql(sql)
        if rc != 0:
            logger.error(f"保存状态 [{update_type}] 失败：{err}")
    except Exception as e:
        logger.error(f"保存状态 [{update_type}] 异常：{e}")


# ============================================================
# Shell 命令执行
# ============================================================


def execute_shell(command):
    """执行 shell 命令并返回结果"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timeout", "returncode": -1}
    except Exception as e:
        return {"success": False, "error": str(e), "returncode": -1}


def check_root():
    """检查 Root 权限"""
    result = execute_shell('su -c "echo root_ok"')
    return result["success"] and "root_ok" in result["stdout"]


# ============================================================
# 数据库查询
# ============================================================


def query_missed_calls_by_id(since_id=0):
    """查询未接来电（type=3），纯按 _id 增量，用于补偿和正常轮询"""
    command = (
        f'su -c "{SQLITE3_PATH} {CALL_LOG_DB} '
        f"\\\"SELECT _id, number, date FROM calls "
        f"WHERE type = 3 AND _id > {since_id} "
        f'ORDER BY _id ASC;\\\""'
    )
    result = execute_shell(command)
    if not result["success"]:
        logger.error(f"查询通话记录失败：{result.get('stderr', result.get('error'))}")
        return []

    calls = []
    lines = result["stdout"].split("\n") if result["stdout"] else []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            calls.append({
                "call_id": int(parts[0]),
                "phone_number": parts[1],
                "call_time": parts[2]
            })
    return calls


def query_new_sms_by_id(since_id=0):
    """查询新接收短信（type=1），纯按 _id 增量，用于补偿和正常轮询"""
    command = (
        f'su -c "{SQLITE3_PATH} {SMS_DB} '
        f"\\\"SELECT _id, address, body, date FROM sms "
        f"WHERE type = 1 AND _id > {since_id} "
        f'ORDER BY _id ASC;\\\""'
    )
    result = execute_shell(command)
    if not result["success"]:
        logger.error(f"查询短信数据库失败：{result.get('stderr', result.get('error'))}")
        return []

    sms_list = []
    lines = result["stdout"].split("\n") if result["stdout"] else []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split("|")
        if len(parts) >= 4:
            sms_list.append({
                "sms_id": int(parts[0]),
                "phone_number": parts[1],
                "content": parts[2],
                "sms_time": parts[3]
            })
    return sms_list


# ============================================================
# 时间格式化
# ============================================================


def ms_to_iso(ms_timestamp):
    """将 Unix 毫秒时间戳转为 ISO 8601 格式"""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def ms_to_readable(ms_timestamp):
    """将 Unix 毫秒时间戳转为可读格式（UTC+8）"""
    try:
        from datetime import datetime, timezone, timedelta
        tz = timezone(timedelta(hours=8))
        dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ms_timestamp)


# ============================================================
# HTTP 转发
# ============================================================


def http_post(url, data):
    """发送 HTTP POST 请求（Bearer Token 认证）"""
    try:
        json_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=json_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_TOKEN}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return {"success": True, "status": resp.status}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {"success": False, "status": e.code, "error": f"{e} | {body}"}
    except urllib.error.URLError as e:
        return {"success": False, "error": str(e.reason)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_event_log(event_type, data):
    """将事件写入日志文件"""
    try:
        os.makedirs(os.path.dirname(EVENT_LOG_FILE) if os.path.dirname(EVENT_LOG_FILE) else SCRIPT_DIR,
                    exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(EVENT_LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {event_type} | {json.dumps(data, ensure_ascii=False)}\n")
    except Exception as e:
        logger.error(f"写入事件日志失败：{e}")


def bark_push(title, body):
    """通过 Bark 推送通知到 iOS 设备"""
    if not BARK_ENABLED:
        return True
    try:
        import urllib.parse
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_body = urllib.parse.quote(body, safe="")
        icon_url = urllib.parse.quote(BARK_ICON, safe="")
        url = f"{BARK_URL}/{encoded_title}/{encoded_body}?icon={icon_url}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            logger.info(f"Bark 推送成功：{title}")
            return True
    except Exception as e:
        logger.error(f"Bark 推送失败：{e}")
        return False


def forward_call_via_http(call):
    """HTTP 转发未接来电"""
    data = {
        "phone_number": call["phone_number"],
        "received_at": ms_to_iso(call["call_time"])
    }
    if TEST_MODE:
        write_event_log("MISSED_CALL_HTTP", data)
        logger.info(f"[HTTP] 未接来电：{call['phone_number']} (time={call['call_time']})")
        return True

    url = f"{SERVER_BASE_URL}{CALL_FORWARD_PATH}"
    result = http_post(url, data)
    if result["success"]:
        logger.info(f"[HTTP] 未接来电已转发：{call['phone_number']}")
        return True
    else:
        logger.error(f"[HTTP] 未接来电转发失败：{call['phone_number']}, 原因：{result.get('error')}")
        return False


def forward_call_via_bark(call):
    """Bark 推送未接来电"""
    return bark_push(call["phone_number"], f"未接来电：{ms_to_readable(call['call_time'])}")


def forward_sms_via_http(sms):
    """HTTP 转发短信"""
    data = {
        "phone_number": sms["phone_number"],
        "content": sms["content"],
        "received_at": ms_to_iso(sms["sms_time"])
    }
    if TEST_MODE:
        write_event_log("NEW_SMS_HTTP", data)
        logger.info(f"[HTTP] 新短信：{sms['phone_number']} | {sms['content'][:50]}...")
        return True

    url = f"{SERVER_BASE_URL}{SMS_FORWARD_PATH}"
    result = http_post(url, data)
    if result["success"]:
        logger.info(f"[HTTP] 短信已转发：{sms['phone_number']}")
        return True
    else:
        logger.error(f"[HTTP] 短信转发失败：{sms['phone_number']}, 原因：{result.get('error')}")
        return False


def forward_sms_via_bark(sms):
    """Bark 推送短信"""
    return bark_push(sms["phone_number"], sms["content"])


# ============================================================
# 轮询逻辑 — 四个独立状态，互不干扰
# ============================================================


def forward_and_update_calls(records, forward_func, state, update_type):
    """遍历通话记录并转发，最后更新状态"""
    for record in records:
        forward_func(record)
    if records:
        last = records[-1]
        state[update_type]["ts"] = last["call_time"]
        state[update_type]["id"] = last["call_id"]
        save_state(state, update_type)


def forward_and_update_sms(records, forward_func, state, update_type):
    """遍历短信记录并转发，最后更新状态"""
    for record in records:
        forward_func(record)
    if records:
        last = records[-1]
        state[update_type]["ts"] = last["sms_time"]
        state[update_type]["id"] = last["sms_id"]
        save_state(state, update_type)


def compensate(state):
    """首次启动补偿：扫描从 last_id 之后的所有遗漏记录并推送"""
    logger.info("执行启动补偿扫描...")

    # ---- HTTP + 未接来电 ----
    missed_http_calls = query_missed_calls_by_id(state["http_call"]["id"])
    if missed_http_calls:
        logger.info(f"[补偿] 发现 {len(missed_http_calls)} 条遗漏未接来电 (HTTP)")
    forward_and_update_calls(missed_http_calls, forward_call_via_http, state, "http_call")

    # ---- HTTP + 短信 ----
    missed_http_sms = query_new_sms_by_id(state["http_sms"]["id"])
    if missed_http_sms:
        logger.info(f"[补偿] 发现 {len(missed_http_sms)} 条遗漏短信 (HTTP)")
    forward_and_update_sms(missed_http_sms, forward_sms_via_http, state, "http_sms")

    # ---- Bark + 未接来电 ----
    missed_bark_calls = query_missed_calls_by_id(state["bark_call"]["id"])
    if missed_bark_calls:
        logger.info(f"[补偿] 发现 {len(missed_bark_calls)} 条遗漏未接来电 (Bark)")
    forward_and_update_calls(missed_bark_calls, forward_call_via_bark, state, "bark_call")

    # ---- Bark + 短信 ----
    missed_bark_sms = query_new_sms_by_id(state["bark_sms"]["id"])
    if missed_bark_sms:
        logger.info(f"[补偿] 发现 {len(missed_bark_sms)} 条遗漏短信 (Bark)")
    forward_and_update_sms(missed_bark_sms, forward_sms_via_bark, state, "bark_sms")

    logger.info("启动补偿扫描完成")


def poll_and_forward(state):
    """根据四个独立状态分别轮询并转发

    四个维度（纯 ID 增量查询，无时间戳依赖）：
      - http_call: HTTP转发 + 未接来电
      - http_sms:  HTTP转发 + 短信
      - bark_call: Bark推送 + 未接来电
      - bark_sms:  Bark推送 + 短信

    转发失败也更新状态（不重试）。
    """
    # ---- HTTP + 未接来电 ----
    http_call_new = query_missed_calls_by_id(state["http_call"]["id"])
    forward_and_update_calls(http_call_new, forward_call_via_http, state, "http_call")

    # ---- HTTP + 短信 ----
    http_sms_new = query_new_sms_by_id(state["http_sms"]["id"])
    forward_and_update_sms(http_sms_new, forward_sms_via_http, state, "http_sms")

    # ---- Bark + 未接来电 ----
    bark_call_new = query_missed_calls_by_id(state["bark_call"]["id"])
    forward_and_update_calls(bark_call_new, forward_call_via_bark, state, "bark_call")

    # ---- Bark + 短信 ----
    bark_sms_new = query_new_sms_by_id(state["bark_sms"]["id"])
    forward_and_update_sms(bark_sms_new, forward_sms_via_bark, state, "bark_sms")


def poll_loop():
    """统一轮询线程（每 5 秒一次），启动时先执行补偿扫描"""
    interval = min(CALL_POLL_INTERVAL, SMS_POLL_INTERVAL)
    logger.info(f"轮询服务已启动（间隔 {interval}s）")

    # 启动补偿：扫描遗漏记录
    try:
        state = load_state()
        compensate(state)
    except Exception as e:
        logger.error(f"启动补偿异常：{e}")

    while True:
        try:
            state = load_state()
            poll_and_forward(state)
        except Exception as e:
            logger.error(f"轮询异常：{e}")
        time.sleep(interval)


# ============================================================
# 主入口
# ============================================================


def main():
    logger.info("=== 未接来电 & 短信转发服务启动 ===")

    # 单实例保护：检查 PID 文件
    pid_file = os.path.join(SCRIPT_DIR, "call_sms_forwarding.pid")
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                old_pid = int(f.read().strip())
            # 检查进程是否还在运行
            os.kill(old_pid, 0)
            logger.error(f"另一个实例已在运行 (PID: {old_pid})，退出")
            return
        except (ProcessLookupError, ValueError, OSError):
            # 进程不存在，清理旧 PID 文件
            pass

    # 写入当前 PID
    try:
        with open(pid_file, "w") as f:
            f.write(str(os.getpid()))
    except Exception as e:
        logger.warning(f"写入 PID 文件失败：{e}")

    if TEST_MODE:
        logger.info("测试模式：事件将记录到日志文件，不调用转发 API")
        logger.info(f"事件日志：{EVENT_LOG_FILE}")

    logger.info(f"日志文件：{LOG_FILE}")

    # 检查 Root 权限
    if not check_root():
        logger.error("未检测到 Root 权限，服务无法运行")
        return

    logger.info(f"服务器：{SERVER_BASE_URL}")
    logger.info(f"状态数据库：{STATE_DB}")
    logger.info("四个独立状态：http_call | http_sms | bark_call | bark_sms")

    # 启动轮询线程
    thread = threading.Thread(target=poll_loop, daemon=True)
    thread.start()

    logger.info("服务已启动，等待事件...")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("服务已停止")
    finally:
        # 清理 PID 文件
        try:
            os.remove(pid_file)
        except Exception:
            pass


if __name__ == "__main__":
    main()
