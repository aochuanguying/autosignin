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

# 事件日志文件路径（测试模式下使用）
EVENT_LOG_FILE = "/sdcard/脚本/call_sms_events.log"

# Bark 推送配置（iOS 实时通知）
BARK_URL = "https://api.day.app/Asbu4fr2HjGAjKbHANNbLS"
BARK_ENABLED = True  # 是否启用 Bark 推送
BARK_ICON = "https://sf16-passport-sg.ibytedtos.com/img/user-avatar-alisg/4b93e0266e7787e68d447ef7231066fe~128x128.image"  # 自定义图标

# 服务器基础 URL（生产环境）
SERVER_BASE_URL = "https://yqad.hxfssc.com:8088"

# 转发 API 路径
CALL_FORWARD_PATH = "/api/posts/mobile/missed-calls"
SMS_FORWARD_PATH = "/api/posts/mobile/sms"

# API Token（外部设备访问，格式：Bearer <token>）
API_TOKEN = "api_token_c5d7f7a306cbd78886ae57d6547aee48d59eeeb94de29234972a074105dc0aff"

# 轮询间隔（秒）- 短信优先级更高，轮询更频繁
CALL_POLL_INTERVAL = 10  # 来电轮询间隔
SMS_POLL_INTERVAL = 5   # 短信轮询间隔（更及时）

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================
# 状态管理
# ============================================================


def init_state_db():
    """初始化状态数据库"""
    try:
        # 直接执行 SQL，使用分号分隔多个命令
        commands = [
            "CREATE TABLE IF NOT EXISTS forward_state (id INTEGER PRIMARY KEY, last_call_timestamp TEXT, last_call_id INTEGER, last_sms_timestamp TEXT, last_sms_id INTEGER, pending_calls TEXT, pending_sms TEXT);",
            "INSERT OR IGNORE INTO forward_state (id, last_call_timestamp, last_call_id, last_sms_timestamp, last_sms_id, pending_calls, pending_sms) VALUES (1, '0', 0, '0', 0, '[]', '[]');"
        ]
        
        for sql in commands:
            # 使用 subprocess 直接执行，避免 shell 转义问题
            command = ['su', '-c', f'{SQLITE3_PATH} {STATE_DB} "{sql}"']
            try:
                result = subprocess.run(command, capture_output=True, text=True, timeout=10)
                if result.returncode != 0 and "already exists" not in result.stderr:
                    logger.error(f"SQL 执行失败：{result.stderr}")
            except Exception as e:
                logger.error(f"SQL 执行异常：{e}")
    except Exception as e:
        logger.error(f"初始化状态数据库异常：{e}")


def load_state():
    """从数据库加载转发状态"""
    init_state_db()
    
    try:
        sql = "SELECT last_call_timestamp, last_call_id, last_sms_timestamp, last_sms_id, pending_calls, pending_sms FROM forward_state WHERE id = 1;"
        command = ['su', '-c', f'{SQLITE3_PATH} {STATE_DB} "{sql}"']
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and result.stdout:
            parts = result.stdout.split("|")
            if len(parts) >= 6:
                state = {
                    "last_call_timestamp": parts[0] or "0",
                    "last_call_id": int(parts[1]) if parts[1] else 0,
                    "last_sms_timestamp": parts[2] or "0",
                    "last_sms_id": int(parts[3]) if parts[3] else 0,
                    "pending_calls": json.loads(parts[4] or "[]"),
                    "pending_sms": json.loads(parts[5] or "[]")
                }
                logger.info(f"加载状态成功：call_id={state['last_call_id']}, sms_id={state['last_sms_id']}")
                return state
            else:
                logger.warning(f"状态字段数量不足：{len(parts)}, stdout='{result.stdout}'")
        else:
            logger.warning(f"加载状态数据库失败：returncode={result.returncode}, stdout='{result.stdout}', stderr='{result.stderr}'")
    except Exception as e:
        logger.warning(f"加载状态数据库异常：{e}")
    
    # 如果数据库加载失败，返回初始状态
    logger.warning("使用初始状态：call_id=0, sms_id=0")
    return {
        "last_call_timestamp": "0",
        "last_sms_timestamp": "0",
        "last_call_id": 0,
        "last_sms_id": 0,
        "pending_calls": [],
        "pending_sms": []
    }


def save_state(state, update_type='both'):
    """保存转发状态到数据库
    
    Args:
        state: 状态字典
        update_type: 'call' | 'sms' | 'both' - 更新哪种状态
    """
    init_state_db()
    
    try:
        # 根据更新类型构建不同的 SQL 语句
        if update_type == 'call':
            # 只更新来电相关字段
            sql = f"UPDATE forward_state SET last_call_timestamp = '{state['last_call_timestamp']}', last_call_id = {state['last_call_id']}, pending_calls = '{json.dumps(state.get('pending_calls', []))}' WHERE id = 1;"
        elif update_type == 'sms':
            # 只更新短信相关字段
            sql = f"UPDATE forward_state SET last_sms_timestamp = '{state['last_sms_timestamp']}', last_sms_id = {state['last_sms_id']}, pending_sms = '{json.dumps(state.get('pending_sms', []))}' WHERE id = 1;"
        else:
            # 更新所有字段
            sql = f"UPDATE forward_state SET last_call_timestamp = '{state['last_call_timestamp']}', last_call_id = {state['last_call_id']}, last_sms_timestamp = '{state['last_sms_timestamp']}', last_sms_id = {state['last_sms_id']}, pending_calls = '{json.dumps(state.get('pending_calls', []))}', pending_sms = '{json.dumps(state.get('pending_sms', []))}' WHERE id = 1;"
        
        # 执行 SQL
        command = ['su', '-c', f'{SQLITE3_PATH} {STATE_DB} "{sql}"']
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            logger.error(f"保存状态数据库失败：{result.stderr}")
    except Exception as e:
        logger.error(f"保存状态数据库异常：{e}")


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


def query_missed_calls(last_timestamp, last_id=0):
    """查询未接来电（type=3），按 date 增量 + _id 去重"""
    command = (
        f'su -c "{SQLITE3_PATH} {CALL_LOG_DB} '
        f"\\\"SELECT _id, number, date FROM calls "
        f"WHERE type = 3 AND date > {last_timestamp} "
        f'ORDER BY date ASC;\\\""'
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
            call_id = int(parts[0])
            # 如果 _id <= last_id，跳过（已处理过）
            if call_id <= last_id:
                continue
            calls.append({
                "call_id": call_id,
                "phone_number": parts[1],
                "call_time": parts[2]
            })
    return calls


def query_new_sms(last_timestamp, last_id=0):
    """查询新接收短信（type=1），按 date 增量 + _id 去重"""
    command = (
        f'su -c "{SQLITE3_PATH} {SMS_DB} '
        f"\\\"SELECT _id, address, body, date FROM sms "
        f"WHERE type = 1 AND date > {last_timestamp} "
        f'ORDER BY date ASC;\\\""'
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
            sms_id = int(parts[0])
            # 如果 _id <= last_id，跳过（已处理过）
            if sms_id <= last_id:
                continue
            sms_list.append({
                "sms_id": sms_id,
                "phone_number": parts[1],
                "content": parts[2],
                "sms_time": parts[3]
            })
    return sms_list


# ============================================================
# HTTP 转发
# ============================================================


def ms_to_iso(ms_timestamp):
    """将 Unix 毫秒时间戳转为 ISO 8601 格式"""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


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
        log_dir = os.path.dirname(EVENT_LOG_FILE)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(EVENT_LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {event_type} | {json.dumps(data, ensure_ascii=False)}\n")
    except Exception as e:
        logger.error(f"写入事件日志失败：{e}")


def ms_to_readable(ms_timestamp):
    """将 Unix 毫秒时间戳转为可读格式"""
    try:
        from datetime import datetime, timezone, timedelta
        # Android 使用本地时区，UTC+8
        tz = timezone(timedelta(hours=8))
        dt = datetime.fromtimestamp(int(ms_timestamp) / 1000, tz=tz)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ms_timestamp


def bark_push(title, body):
    """通过 Bark 推送通知到 iOS 设备"""
    if not BARK_ENABLED:
        return True
    try:
        # Bark URL 格式：https://api.day.app/key/标题/内容
        # 支持 icon 参数自定义图标
        import urllib.parse
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_body = urllib.parse.quote(body, safe="")
        icon_url = urllib.parse.quote(BARK_ICON, safe="")
        url = f"{BARK_URL}/{encoded_title}/{encoded_body}?icon={icon_url}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except Exception as e:
        logger.error(f"Bark 推送失败：{e}")
        return False


def forward_call(call):
    """转发单条未接来电"""
    data = {
        "phone_number": call["phone_number"],
        "received_at": ms_to_iso(call["call_time"])
    }
    if TEST_MODE:
        write_event_log("MISSED_CALL", data)
        logger.info(f"📞 未接来电：{call['phone_number']} (time={call['call_time']})")
        # 测试模式不发送 Bark 推送，避免重复通知
        return True

    url = f"{SERVER_BASE_URL}{CALL_FORWARD_PATH}"
    result = http_post(url, data)
    if result["success"]:
        logger.info(f"✓ 未接来电已转发：{call['phone_number']} (time={call['call_time']})")
        bark_push(call["phone_number"], f"未接来电：{ms_to_readable(call['call_time'])}")
    else:
        logger.error(f"✗ 未接来电转发失败：{call['phone_number']}, 原因：{result.get('error')}")
    return result["success"]


def forward_sms(sms):
    """转发单条短信"""
    data = {
        "phone_number": sms["phone_number"],
        "content": sms["content"],
        "received_at": ms_to_iso(sms["sms_time"])
    }
    if TEST_MODE:
        write_event_log("NEW_SMS", data)
        logger.info(f"💬 新短信：{sms['phone_number']} | {sms['content'][:50]}... (time={sms['sms_time']})")
        # 测试模式不发送 Bark 推送，避免重复通知
        return True

    url = f"{SERVER_BASE_URL}{SMS_FORWARD_PATH}"
    result = http_post(url, data)
    if result["success"]:
        logger.info(f"✓ 短信已转发：{sms['phone_number']} (time={sms['sms_time']})")
        bark_push(sms["phone_number"], sms["content"])
    else:
        logger.error(f"✗ 短信转发失败：{sms['phone_number']}, 原因：{result.get('error')}")
    return result["success"]


# ============================================================
# 轮询循环
# ============================================================


def poll_missed_calls(state):
    """轮询未接来电"""
    new_calls = query_missed_calls(state["last_call_timestamp"], state.get("last_call_id", 0))

    # 先处理 pending 队列
    pending = state.get("pending_calls", [])
    if pending:
        logger.info(f"重试转发 {len(pending)} 条待处理的未接来电...")
        still_pending = []
        for call in pending:
            if not forward_call(call):
                still_pending.append(call)
        state["pending_calls"] = still_pending

    # 处理新记录
    for call in new_calls:
        if not forward_call(call):
            state["pending_calls"].append(call)

    # 更新最后时间戳和 _id
    if new_calls:
        state["last_call_timestamp"] = new_calls[-1]["call_time"]
        state["last_call_id"] = new_calls[-1]["call_id"]


def poll_new_sms(state):
    """轮询新短信"""
    new_sms_list = query_new_sms(state["last_sms_timestamp"], state.get("last_sms_id", 0))

    # 先处理 pending 队列
    pending = state.get("pending_sms", [])
    if pending:
        logger.info(f"重试转发 {len(pending)} 条待处理的短信...")
        still_pending = []
        for sms in pending:
            if not forward_sms(sms):
                still_pending.append(sms)
        state["pending_sms"] = still_pending

    # 处理新记录
    for sms in new_sms_list:
        if not forward_sms(sms):
            state["pending_sms"].append(sms)

    # 更新最后时间戳和 _id
    if new_sms_list:
        state["last_sms_timestamp"] = new_sms_list[-1]["sms_time"]
        state["last_sms_id"] = new_sms_list[-1]["sms_id"]


def call_poll_loop():
    """来电轮询线程"""
    logger.info(f"来电监听已启动（间隔 {CALL_POLL_INTERVAL}s）")
    while True:
        try:
            state = load_state()
            poll_missed_calls(state)
            save_state(state, update_type='call')
        except Exception as e:
            logger.error(f"来电轮询异常：{e}")
        time.sleep(CALL_POLL_INTERVAL)


def sms_poll_loop():
    """短信轮询线程"""
    logger.info(f"短信监听已启动（间隔 {SMS_POLL_INTERVAL}s）")
    while True:
        try:
            state = load_state()
            poll_new_sms(state)
            save_state(state, update_type='sms')
        except Exception as e:
            logger.error(f"短信轮询异常：{e}")
        time.sleep(SMS_POLL_INTERVAL)


# ============================================================
# 主入口
# ============================================================


def main():
    logger.info("=== 未接来电 & 短信转发服务启动 ===")

    if TEST_MODE:
        logger.info("⚠ 测试模式：事件将记录到日志文件，不调用转发 API")
        logger.info(f"事件日志：{EVENT_LOG_FILE}")

    # 检查 Root 权限
    if not check_root():
        logger.error("未检测到 Root 权限，服务无法运行")
        return

    logger.info(f"服务器：{SERVER_BASE_URL}")
    logger.info(f"来电 API：{CALL_FORWARD_PATH}")
    logger.info(f"短信 API：{SMS_FORWARD_PATH}")
    logger.info(f"状态数据库：{STATE_DB}")

    # 启动两个轮询线程
    call_thread = threading.Thread(target=call_poll_loop, daemon=True)
    sms_thread = threading.Thread(target=sms_poll_loop, daemon=True)

    call_thread.start()
    sms_thread.start()

    logger.info("服务已启动，等待事件...")

    try:
        # 主线程保持运行
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("服务已停止")


if __name__ == "__main__":
    main()
