# Android Telecom API 服务文档

## 📋 目录

1. [服务简介](#服务简介)
2. [功能特性](#功能特性)
3. [系统架构](#系统架构)
4. [项目结构](#项目结构)
5. [完整脚本源码](#完整脚本源码)
   - [server.py - 主服务脚本](#1-serverpy---主服务脚本)
   - [install.sh - 安装脚本](#2-installsh---安装脚本)
   - [start-service.sh - 服务管理脚本](#3-start-servicesh---服务管理脚本)
   - [setup-boot-start.sh - 开机自启动配置脚本](#4-setup-boot-startsh---开机自启动配置脚本)
   - [boot-start.sh - 开机自启动主脚本](#5-boot-startsh---开机自启动主脚本)
   - [termux-boot/boot-start.sh - Termux Boot 启动脚本](#6-termux-bootboot-startsh---termux-boot-启动脚本)
6. [API 接口文档](#api-接口文档)
7. [使用示例](#使用示例)
8. [部署指南](#部署指南)
9. [服务管理](#服务管理)
10. [开机自启动](#开机自启动)
11. [网络配置](#网络配置)
12. [安全建议](#安全建议)
13. [故障排查](#故障排查)
14. [高级配置](#高级配置)
15. [短信&电话上报系统](#短信&电话上报系统)
    - [系统概述](#系统概述)
    - [完整脚本源码](#call_sms_forwardingpy-完整源码)
    - [配置说明](#配置说明)
    - [部署步骤](#部署步骤)
    - [Bark 推送配置](#bark-推送配置)
    - [常见问题](#常见问题)

---

## 🎯 服务简介

Android Telecom API 是在已 root 的 Android 设备上提供电话和短信功能的 HTTP REST API 服务。

**核心功能**:
- ✅ 拨打电话
- ✅ 发送短信
- ✅ 获取短信收件箱
- ✅ 获取通话记录
- ✅ 获取设备信息
- 🔒 API Token 认证
- 📝 日志记录
- 🔄 后台服务运行

**项目位置**: `/Users/mac/Documents/workspace/krio/autosignin/android-telecom-api/`

---

## ✨ 功能特性

- ✅ **RESTful API 接口** - 标准的 HTTP REST 接口
- ✅ **电话功能** - 远程拨打电话
- ✅ **短信功能** - 远程发送短信
- ✅ **短信收件箱** - 获取历史短信
- ✅ **通话记录** - 获取历史通话记录
- ✅ **设备信息** - 获取设备基本信息
- ✅ **Bearer Token 认证** - 安全保障
- ✅ **开机自启动** - Termux:Boot / Magisk 支持
- ✅ **服务管理** - start/stop/restart/status/logs
- ✅ **完整的日志系统** - 本地日志 + logcat

---

## 🏗️ 系统架构

```
┌──────────────┐      HTTP API       ┌─────────────┐
│   客户端      │ ◄─────────────────► │ Python      │
│  (curl/SDK)  │   Port: 5000        │ Flask Server│
└──────────────┘                     └──────┬──────┘
                                            │
                                    调用系统 Telecom API
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
              ┌─────▼─────┐          ┌──────▼──────┐         ┌─────▼─────┐
              │  拨号器    │          │ 短信中心    │         │ 通讯录    │
              │  (Call)   │          │  (SMS)      │         │  (Contact)│
              └───────────┘          └─────────────┘         └───────────┘
```

---

## 📁 项目结构

```
android-telecom-api/
├── server.py                      # 主服务脚本（Python Flask）
├── install.sh                     # 安装脚本
├── start-service.sh               # 服务管理脚本
├── setup-boot-start.sh            # 开机自启动配置脚本
├── boot-start.sh                  # 开机自启动主脚本
├── INSTALL_COMMANDS.txt           # 快速安装命令
├── termux-boot/
│   ├── boot-start.sh              # Termux Boot 启动脚本
│   └── boot-start-fixed.sh        # 修复版启动脚本
└── doc/
    └── Android Telecom API 服务文档.md  # 本文档
```

---

## 📜 完整脚本源码

### 1. server.py - 主服务脚本

**位置**: `android-telecom-api/server.py`

**功能**: Flask HTTP 服务器，提供电话/短信 API 接口

**API 端点**:
- `GET /health` - 健康检查
- `POST /api/v1/call` - 拨打电话
- `POST /api/v1/sms/send` - 发送短信
- `GET /api/v1/sms/inbox` - 获取短信收件箱
- `GET /api/v1/call/log` - 获取通话记录
- `GET /api/v1/device/info` - 获取设备信息

**完整源码**:

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Android 电话/短信 HTTP API 服务
运行在已 root 的 Android 设备的 Termux 环境中
通过 HTTP 接口提供打电话和发短信功能
"""

import json
import subprocess
import logging
from flask import Flask, request, jsonify
from functools import wraps
import os

app = Flask(__name__)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API Token 认证（建议修改）
API_TOKEN = os.environ.get('TELECOM_API_TOKEN', 'your-secret-token-here')


def require_auth(f):
    """API 认证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '')
        if token.startswith('Bearer '):
            token = token[7:]
        
        if not token or token != API_TOKEN:
            return jsonify({
                'success': False,
                'error': 'Unauthorized',
                'message': 'Invalid or missing API token'
            }), 401
        
        return f(*args, **kwargs)
    return decorated


def execute_shell_command(command):
    """执行 shell 命令并返回结果"""
    try:
        logger.info(f"执行命令：{command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Command timeout',
            'returncode': -1
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'returncode': -1
        }


def check_root():
    """检查是否具有 root 权限"""
    result = execute_shell_command('su -c "echo root_access_granted"')
    return result['success'] and 'root_access_granted' in result['stdout']


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({
        'status': 'ok',
        'service': 'android-telecom-api',
        'root_access': check_root()
    })


@app.route('/api/v1/call', methods=['POST'])
@require_auth
def make_call():
    """
    拨打电话 API
    POST /api/v1/call
    Body: {"phone_number": "1234567890"}
    """
    try:
        data = request.get_json()
        
        if not data or 'phone_number' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing phone_number parameter'
            }), 400
        
        phone_number = data['phone_number']
        
        # 验证电话号码格式
        if not phone_number or not isinstance(phone_number, str):
            return jsonify({
                'success': False,
                'error': 'Invalid phone number'
            }), 400
        
        # 使用 root 权限执行电话拨打命令
        # 方法 1: 使用 am start 命令通过 Intent 拨号
        command = f'su -c "am start -a android.intent.action.CALL -d tel:{phone_number}"'
        
        result = execute_shell_command(command)
        
        if result['success']:
            logger.info(f"电话已拨打：{phone_number}")
            return jsonify({
                'success': True,
                'message': f'Call initiated to {phone_number}',
                'phone_number': phone_number
            })
        else:
            logger.error(f"拨打电话失败：{result}")
            return jsonify({
                'success': False,
                'error': 'Failed to make call',
                'details': result.get('stderr', result.get('error', 'Unknown error'))
            }), 500
            
    except Exception as e:
        logger.error(f"拨打电话异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/sms/send', methods=['POST'])
@require_auth
def send_sms():
    """
    发送短信 API
    POST /api/v1/sms/send
    Body: {"phone_number": "1234567890", "message": "Hello"}
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'Missing request body'
            }), 400
        
        phone_number = data.get('phone_number')
        message = data.get('message', '')
        
        if not phone_number:
            return jsonify({
                'success': False,
                'error': 'Missing phone_number parameter'
            }), 400
        
        if not isinstance(phone_number, str) or not isinstance(message, str):
            return jsonify({
                'success': False,
                'error': 'Invalid parameters'
            }), 400
        
        # 使用 Termux:API 发送短信（真正后台发送）
        # termux-sms-send 不需要 root 权限，但需要 Termux:API 应用和短信权限
        # 注意：短信内容中的特殊字符需要转义
        escaped_message = message.replace('"', '\\"').replace('$', '\\$')
        command = f'termux-sms-send -n "{phone_number}" "{escaped_message}"'
        
        result = execute_shell_command(command)
        
        if result['success']:
            logger.info(f"短信已发送到：{phone_number}")
            return jsonify({
                'success': True,
                'message': f'SMS sent to {phone_number}',
                'phone_number': phone_number,
                'message_length': len(message)
            })
        else:
            logger.error(f"发送短信失败：{result}")
            return jsonify({
                'success': False,
                'error': 'Failed to send SMS',
                'details': result.get('stderr', result.get('error', 'Unknown error'))
            }), 500
            
    except Exception as e:
        logger.error(f"发送短信异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/sms/inbox', methods=['GET'])
@require_auth
def get_sms_inbox():
    """
    获取收件箱短信 API
    GET /api/v1/sms/inbox?limit=10
    """
    try:
        limit = request.args.get('limit', '10')
        
        try:
            limit = int(limit)
            if limit > 100:
                limit = 100
            if limit < 1:
                limit = 1
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid limit parameter'
            }), 400
        
        # 读取短信数据库需要 root 权限
        # 短信存储在 /data/data/com.android.providers.telephony/databases/mmssms.db
        # 使用 Termux 的 sqlite3 路径
        command = f"""
        su -c "/data/data/com.termux/files/usr/bin/sqlite3 /data/data/com.android.providers.telephony/databases/mmssms.db \
        'SELECT address, body, date, type FROM sms ORDER BY date DESC LIMIT {limit};'"
        """
        
        result = execute_shell_command(command)
        
        if result['success']:
            # 解析 SQLite 输出 (默认用 | 分隔)
            messages = []
            lines = result['stdout'].strip().split('\n') if result['stdout'] else []
            
            for line in lines:
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 4:
                        messages.append({
                            'phone_number': parts[0],
                            'body': parts[1],
                            'timestamp': parts[2],
                            'type': 'received' if parts[3] == '1' else 'sent'
                        })
            
            return jsonify({
                'success': True,
                'messages': messages,
                'count': len(messages)
            })
        else:
            logger.error(f"获取短信失败：{result}")
            return jsonify({
                'success': False,
                'error': 'Failed to retrieve SMS inbox',
                'details': result.get('stderr', result.get('error', 'Unknown error'))
            }), 500
            
    except Exception as e:
        logger.error(f"获取短信异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/call/log', methods=['GET'])
@require_auth
def get_call_log():
    """
    获取通话记录 API
    GET /api/v1/call/log?limit=10
    """
    try:
        limit = request.args.get('limit', '10')
        
        try:
            limit = int(limit)
            if limit > 100:
                limit = 100
            if limit < 1:
                limit = 1
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid limit parameter'
            }), 400
        
        # 读取通话记录数据库
        # 使用 Termux 的 sqlite3 路径
        # Android 15 通话记录存储在 calllog.db 的 calls 表中
        command = f"""
        su -c "/data/data/com.termux/files/usr/bin/sqlite3 /data/data/com.android.providers.contacts/databases/calllog.db \
        'SELECT number, duration, date, type FROM calls ORDER BY date DESC LIMIT {limit};'"
        """
        
        result = execute_shell_command(command)
        
        if result['success']:
            calls = []
            lines = result['stdout'].strip().split('\n') if result['stdout'] else []
            
            for line in lines:
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 4:
                        call_type = parts[3]
                        type_map = {
                            '1': 'incoming',
                            '2': 'outgoing',
                            '3': 'missed',
                            '5': 'rejected'
                        }
                        calls.append({
                            'phone_number': parts[0],
                            'duration': parts[1],
                            'timestamp': parts[2],
                            'type': type_map.get(call_type, 'unknown')
                        })
            
            return jsonify({
                'success': True,
                'calls': calls,
                'count': len(calls)
            })
        else:
            logger.error(f"获取通话记录失败：{result}")
            return jsonify({
                'success': False,
                'error': 'Failed to retrieve call log',
                'details': result.get('stderr', result.get('error', 'Unknown error'))
            }), 500
            
    except Exception as e:
        logger.error(f"获取通话记��异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/device/info', methods=['GET'])
@require_auth
def get_device_info():
    """
    获取设备信息 API
    GET /api/v1/device/info
    """
    try:
        # 获取设备信息
        commands = {
            'model': 'getprop ro.product.model',
            'manufacturer': 'getprop ro.product.manufacturer',
            'android_version': 'getprop ro.build.version.release',
            'sdk_version': 'getprop ro.build.version.sdk',
            'phone_number': 'service call iphonesubinfo 1 | grep -oE "[0-9a-f]{8}" | tr -d "." | head -c 15'
        }
        
        info = {}
        for key, cmd in commands.items():
            result = execute_shell_command(f'su -c "{cmd}"')
            info[key] = result.get('stdout', '').strip() if result['success'] else 'N/A'
        
        return jsonify({
            'success': True,
            'device_info': info
        })
        
    except Exception as e:
        logger.error(f"获取设备信息异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Not Found',
        'message': 'The requested endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal Server Error',
        'message': 'An unexpected error occurred'
    }), 500


if __name__ == '__main__':
    # 检查 root 权限
    if not check_root():
        logger.warning("警告：未检测到 root 权限，部分功能可能无法正常工作")
    
    logger.info("启动 Android Telecom API 服务...")
    logger.info(f"API Token: {API_TOKEN[:4]}...{API_TOKEN[-4:] if len(API_TOKEN) > 8 else '****'}")
    
    # 启动 Flask 服务器
    # 监听所有网络接口，端口 5000
    app.run(host='0.0.0.0', port=5000, debug=False)
```

---

### 2. install.sh - 安装脚本

**位置**: `android-telecom-api/install.sh`

**功能**: 自动安装 Python 依赖、创建配置、生成 API Token

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/sh
# Android Telecom API 安装脚本
# 用于在已 root 的 Termux 环境中安装和配置服务

echo "======================================"
echo "Android Telecom API 安装脚本"
echo "======================================"

# 检查是否在 Termux 中运行
if [ ! -d "/data/data/com.termux/files" ]; then
    echo "错误：此脚本只能在 Termux 环境中运行"
    exit 1
fi

# 检查 root 权限
echo "检查 root 权限..."
if ! su -c "echo root_access_granted" 2>/dev/null | grep -q "root_access_granted"; then
    echo "警告：未检测到 root 权限，部分功能可能无法正常工作"
    echo "请确保您的设备已 root 并授予 Termux root 权限"
fi

# 更新包管理器
echo "更新 Termux 包管理器..."
pkg update -y

# 安装 Python 和依赖
echo "安装 Python 和相关依赖..."
pkg install -y python sqlite

# 安装 Python 包
echo "安装 Python 依赖包..."
pip install flask

# 创建配置目录
echo "创建配置目录..."
CONFIG_DIR="$HOME/.telecom-api"
mkdir -p "$CONFIG_DIR"

# 生成或读取 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    echo "使用现有的 API Token..."
    API_TOKEN=$(cat "$CONFIG_DIR/api_token")
else
    echo "生成新的 API Token..."
    API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "$API_TOKEN" > "$CONFIG_DIR/api_token"
    chmod 600 "$CONFIG_DIR/api_token"
fi

# 授予读取短信和通话记录数据库的权限
echo "配置数据库访问权限..."
# 注意：这需要 root 权限，并且不同 ROM 可能路径不同
# 脚本会在运行时尝试访问，这里只做提示

# 创建服务启动脚本
echo "创建服务启动脚本..."
cat > "$CONFIG_DIR/start.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/sh
# 启动 Telecom API 服务

CONFIG_DIR="$HOME/.telecom-api"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 加载 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$CONFIG_DIR/api_token")
fi

# 启动服务
echo "启动服务..."
python3 "$SCRIPT_DIR/server.py"
EOF

chmod +x "$CONFIG_DIR/start.sh"

# 创建 systemd 服务文件（如果支持）
if [ -d "/etc/systemd/system" ]; then
    echo "创建 systemd 服务..."
    cat > /etc/systemd/system/telecom-api.service << EOF
[Unit]
Description=Android Telecom API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$SCRIPT_DIR
Environment=TELECOM_API_TOKEN=$API_TOKEN
ExecStart=/data/data/com.termux/files/usr/bin/python3 $SCRIPT_DIR/server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    systemctl enable telecom-api
    echo "systemd 服务已创建并启用"
fi

# 显示完成信息
echo ""
echo "======================================"
echo "安装完成！"
echo "======================================"
echo ""
echo "API Token: $API_TOKEN"
echo "（已保存到 $CONFIG_DIR/api_token）"
echo ""
echo "启动服务："
echo "  $CONFIG_DIR/start.sh"
echo ""
echo "或者手动启动："
echo "  export TELECOM_API_TOKEN=$API_TOKEN"
echo "  python3 server.py"
echo ""
echo "服务将在 http://0.0.0.0:5000 监听"
echo ""
echo "API 端点:"
echo "  GET  /health              - 健康检查"
echo "  POST /api/v1/call         - 拨打电话"
echo "  POST /api/v1/sms/send     - 发送短信"
echo "  GET  /api/v1/sms/inbox    - 获取短信收件箱"
echo "  GET  /api/v1/call/log     - 获取通话记录"
echo "  GET  /api/v1/device/info  - 获取设备信息"
echo ""
echo "使用示例:"
echo "  curl -X POST http://localhost:5000/api/v1/call \\"
echo "    -H \"Authorization: Bearer $API_TOKEN\" \\"
echo "    -H \"Content-Type: application/json\" \\"
echo "    -d '{\"phone_number\": \"1234567890\"}'"
echo ""
```

---

### 3. start-service.sh - 服务管理脚本

**位置**: `android-telecom-api/start-service.sh`

**功能**: 服务的启动、停止、重启、状态查看、日志查看

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/sh
# Telecom API 服务管理脚本
# 支持启动、停止、重启和查看状态

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$HOME/.telecom-api/server.pid"
LOG_FILE="$HOME/.telecom-api/server.log"
CONFIG_DIR="$HOME/.telecom-api"

# 确保配置目录存在
mkdir -p "$CONFIG_DIR"

# 加载 API Token
if [ -f "$CONFIG_DIR/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$CONFIG_DIR/api_token")
fi

start() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务已在运行 (PID: $(cat "$PID_FILE"))"
        exit 1
    fi
    
    echo "启动 Telecom API 服务..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    
    sleep 2
    
    if kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务启动成功 (PID: $(cat "$PID_FILE"))"
        echo "日志文件：$LOG_FILE"
    else
        echo "服务启动失败，请查看日志：$LOG_FILE"
        exit 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "服务未运行 (无 PID 文件)"
        exit 1
    fi
    
    PID=$(cat "$PID_FILE")
    
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "服务未运行 (进程不存在)"
        rm -f "$PID_FILE"
        exit 1
    fi
    
    echo "停止服务 (PID: $PID)..."
    kill "$PID"
    
    # 等待进程结束
    i=1
    while [ $i -le 10 ]; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "服务已停止"
            rm -f "$PID_FILE"
            break
        fi
        sleep 1
        i=$((i + 1))
    done
    
    # 强制停止
    echo "强制停止服务..."
    kill -9 "$PID"
    rm -f "$PID_FILE"
    echo "服务已强制停止"
}

restart() {
    stop
    sleep 2
    start
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
        echo "服务运行中"
        echo "  PID: $(cat "$PID_FILE")"
        echo "  端口：5000"
        echo "  日志：$LOG_FILE"
        
        # 显示最近 10 行日志
        echo ""
        echo "最近日志:"
        tail -n 10 "$LOG_FILE"
    else
        echo "服务未运行"
        rm -f "$PID_FILE"
        exit 1
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -n 50 "$LOG_FILE"
    else
        echo "日志文件不存在"
    fi
}

show_token() {
    if [ -f "$CONFIG_DIR/api_token" ]; then
        TOKEN=$(cat "$CONFIG_DIR/api_token")
        echo "API Token: $TOKEN"
    else
        echo "API Token 未设置"
    fi
}

# 主程序
case "${1:-status}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    token)
        show_token
        ;;
    *)
        echo "用法：$0 {start|stop|restart|status|logs|token}"
        echo ""
        echo "命令:"
        echo "  start   - 启动服务"
        echo "  stop    - 停止服务"
        echo "  restart - 重启服务"
        echo "  status  - 查看服务状态"
        echo "  logs    - 查看最近日志"
        echo "  token   - 显示 API Token"
        exit 1
        ;;
esac
```

---

### 4. setup-boot-start.sh - 开机自启动配置脚本

**位置**: `android-telecom-api/setup-boot-start.sh`

**功能**: 配置 Termux Boot 开机自启动

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/sh
# 设置开机自启动脚本
# 此脚本需要在 Termux 环境中运行一次，用于配置开机自启动

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOOT_DIR="$HOME/.termux/boot"

echo "======================================"
echo "Telecom API 开机自启动配置"
echo "======================================"
echo ""

# 检查是否在 Termux 中运行
if [ ! -d "/data/data/com.termux" ]; then
    echo "错误：此脚本必须在 Termux 环境中运行"
    exit 1
fi

# 1. 安装 termux-boot 包
echo "1. 安装 termux-boot 包..."
pkg install termux-boot -y
if [ $? -eq 0 ]; then
    echo "   ✓ termux-boot 安装成功"
else
    echo "   ✗ termux-boot 安装失败"
    exit 1
fi

# 2. 创建 boot 目录
echo ""
echo "2. 创建 boot 目录..."
mkdir -p "$BOOT_DIR"
if [ $? -eq 0 ]; then
    echo "   ✓ 目录创建成功：$BOOT_DIR"
else
    echo "   ✗ 目录创建失败"
    exit 1
fi

# 3. 复制启动脚本
echo ""
echo "3. 复制启动脚本到 boot 目录..."
cp "$SCRIPT_DIR/boot-start.sh" "$BOOT_DIR/"
if [ $? -eq 0 ]; then
    echo "   ✓ 脚本复制成功"
else
    echo "   ✗ 脚本复制失败"
    exit 1
fi

# 4. 设置执行权限
echo ""
echo "4. 设置执行权限..."
chmod +x "$BOOT_DIR/boot-start.sh"
chmod +x "$SCRIPT_DIR/boot-start.sh"
chmod +x "$SCRIPT_DIR/start-service.sh"
echo "   ✓ 权限设置完成"

# 5. 验证配置
echo ""
echo "5. 验证配置..."
if [ -f "$BOOT_DIR/boot-start.sh" ]; then
    echo "   ✓ 启动脚本已就位：$BOOT_DIR/boot-start.sh"
    echo "   ✓ 主启动脚本：$SCRIPT_DIR/boot-start.sh"
else
    echo "   ✗ 配置验证失败"
    exit 1
fi

echo ""
echo "======================================"
echo "✓ 开机自启动配置完成！"
echo "======================================"
echo ""
echo "下次设备重启后，Telecom API 服务将自动启动。"
echo ""
echo "您可以测试启动脚本："
echo "  $SCRIPT_DIR/boot-start.sh"
echo ""
echo "或者手动启动服务："
echo "  $SCRIPT_DIR/start-service.sh start"
echo ""
```

---

### 5. boot-start.sh - 开机自启动主脚本

**位置**: `android-telecom-api/boot-start.sh`

**功能**: 设备启动时自动启动 Telecom API 服务

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/bash
# Telecom API 开机自启动脚本
# 在设备启动后自动启动服务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_SCRIPT="$SCRIPT_DIR/start-service.sh"
PID_FILE="$HOME/.telecom-api/server.pid"
LOG_FILE="$HOME/.telecom-api/boot-start.log"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
}

log "=== 开机自启动脚本开始执行 ==="

# 等待系统完全启动（可选延迟）
log "等待系统启动完成..."
sleep 30

# 检查服务是否已经在运行
if [ -f "$PID_FILE" ] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    log "服务已在运行 (PID: $(cat "$PID_FILE"))，无需启动"
    exit 0
fi

# 确保服务脚本存在且可执行
if [ ! -x "$SERVICE_SCRIPT" ]; then
    log "错误：服务脚本不存在或不可执行：$SERVICE_SCRIPT"
    exit 1
fi

# 启动服务
log "正在启动 Telecom API 服务..."
cd "$SCRIPT_DIR"

# 加载 API Token
if [ -f "$HOME/.telecom-api/api_token" ]; then
    export TELECOM_API_TOKEN=$(cat "$HOME/.telecom-api/api_token")
    log "已加载 API Token"
fi

# 启动服务
nohup python3 "$SCRIPT_DIR/server.py" > "$HOME/.telecom-api/server.log" 2>&1 &
SERVER_PID=$!
echo $SERVER_PID > "$PID_FILE"

# 等待并验证服务是否启动成功
sleep 3

if kill -0 $SERVER_PID 2>/dev/null; then
    log "服务启动成功 (PID: $SERVER_PID)"
    log "=== 开机自启动完成 ==="
    exit 0
else
    log "服务启动失败，PID: $SERVER_PID 不存在"
    log "=== 开机自启动失败 ==="
    exit 1
fi
```

---

### 6. termux-boot/boot-start.sh - Termux Boot 启动脚本

**位置**: `android-telecom-api/termux-boot/boot-start.sh`

**功能**: 被 Termux:Boot 应用在系统启动后执行

**完整源码**:

```bash
#!/data/data/com.termux/files/usr/bin/bash
# Termux Boot 自启动脚本
# 此��件会被 Termux:Boot 应用在系统启动完成后自动执行

# 等待网络和服务完全启动
sleep 10

# 执行主启动脚本
/data/data/com.termux/files/usr/bin/bash /data/data/com.termux/files/home/autosignin/android-telecom-api/boot-start.sh
```

---

## ⚙️ 核心配置

| 配置项 | 值 |
|--------|-----|
| **服务端口** | 5000 |
| **监听地址** | 0.0.0.0 (允许局域网访问) |
| **认证方式** | Bearer Token |
| **Token 位置** | `~/.telecom-api/api_token` |
| **日志位置** | `~/.telecom-api/server.log` |
| **配置目录** | `~/.telecom-api/` |

---

## 🌐 API 接口文档

### 认证方式

所有 API 请求需要在 Header 中携带 Bearer Token：

```
Authorization: Bearer YOUR_API_TOKEN
```

API Token 存储在：`$HOME/.telecom-api/api_token`

---

### 1. 健康检查

**接口**: `GET /health`

**响应**:
```json
{
  "status": "ok",
  "service": "android-telecom-api",
  "root_access": true
}
```

**示例**:
```bash
curl http://192.168.50.149:5000/health
```

---

### 2. 拨打电话

**接口**: `POST /api/v1/call`

**请求头**:
```
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

**请求体**:
```json
{
  "phone_number": "1234567890"
}
```

**响应**:
```json
{
  "success": true,
  "message": "Call initiated to 1234567890",
  "phone_number": "1234567890"
}
```

**示例**:
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"1234567890"}' \
  http://192.168.50.149:5000/api/v1/call
```

---

### 3. 发送短信

**接口**: `POST /api/v1/sms/send`

**请求头**:
```
Authorization: Bearer YOUR_API_TOKEN
Content-Type: application/json
```

**请求体**:
```json
{
  "phone_number": "1234567890",
  "message": "Hello World"
}
```

**响应**:
```json
{
  "success": true,
  "message": "SMS sent to 1234567890",
  "phone_number": "1234567890",
  "message_length": 11
}
```

**示例**:
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"1234567890","message":"Hello from API"}' \
  http://192.168.50.149:5000/api/v1/sms/send
```

---

### 4. 获取短信收件箱

**接口**: `GET /api/v1/sms/inbox?limit=10`

**请求头**:
```
Authorization: Bearer YOUR_API_TOKEN
```

**参数**:
- `limit` (可选): 返回数量，默认 10，最大 100

**响应**:
```json
{
  "success": true,
  "messages": [
    {
      "phone_number": "1234567890",
      "body": "Hello",
      "timestamp": "1234567890",
      "type": "received"
    }
  ],
  "count": 1
}
```

**示例**:
```bash
curl -X GET \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  "http://192.168.50.149:5000/api/v1/sms/inbox?limit=5"
```

---

### 5. 获取通话记录

**接口**: `GET /api/v1/call/log?limit=10`

**请求头**:
```
Authorization: Bearer YOUR_API_TOKEN
```

**参数**:
- `limit` (可选): 返回数量，默认 10，最大 100

**响应**:
```json
{
  "success": true,
  "calls": [
    {
      "phone_number": "1234567890",
      "duration": "120",
      "timestamp": "1234567890",
      "type": "incoming"
    }
  ],
  "count": 1
}
```

**示例**:
```bash
curl -X GET \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  "http://192.168.50.149:5000/api/v1/call/log?limit=5"
```

---

### 6. 获取设备信息

**接口**: `GET /api/v1/device/info`

**请求头**:
```
Authorization: Bearer YOUR_API_TOKEN
```

**响应**:
```json
{
  "success": true,
  "device_info": {
    "model": "Pixel 8",
    "manufacturer": "Google",
    "android_version": "15",
    "sdk_version": "35",
    "phone_number": "1234567890"
  }
}
```

**示例**:
```bash
curl -X GET \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  http://192.168.50.149:5000/api/v1/device/info
```

---

## 💡 使用示例

### cURL 示例

```bash
# 定义变量
API_TOKEN="your-api-token-here"
BASE_URL="http://your-device-ip:5000"

# 拨打电话
curl -X POST "$BASE_URL/api/v1/call" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"1234567890"}'

# 发送短信
curl -X POST "$BASE_URL/api/v1/sms/send" \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"phone_number":"1234567890","message":"Hello from API"}'

# 获取短信
curl -X GET "$BASE_URL/api/v1/sms/inbox?limit=5" \
  -H "Authorization: Bearer $API_TOKEN"

# 获取通话记录
curl -X GET "$BASE_URL/api/v1/call/log?limit=5" \
  -H "Authorization: Bearer $API_TOKEN"

# 获取设备信息
curl -X GET "$BASE_URL/api/v1/device/info" \
  -H "Authorization: Bearer $API_TOKEN"
```

---

### Python 示例

```python
import requests

BASE_URL = "http://your-device-ip:5000"
API_TOKEN = "your-api-token-here"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# 拨打电话
response = requests.post(
    f"{BASE_URL}/api/v1/call",
    headers=headers,
    json={"phone_number": "1234567890"}
)
print(response.json())

# 发送短信
response = requests.post(
    f"{BASE_URL}/api/v1/sms/send",
    headers=headers,
    json={"phone_number": "1234567890", "message": "Hello"}
)
print(response.json())

# 获取短信
response = requests.get(
    f"{BASE_URL}/api/v1/sms/inbox?limit=5",
    headers=headers
)
print(response.json())

# 获取通话记录
response = requests.get(
    f"{BASE_URL}/api/v1/call/log?limit=5",
    headers=headers
)
print(response.json())

# 获取设备信息
response = requests.get(
    f"{BASE_URL}/api/v1/device/info",
    headers=headers
)
print(response.json())
```

---

### Node.js 示例

```javascript
const axios = require('axios');

const BASE_URL = 'http://your-device-ip:5000';
const API_TOKEN = 'your-api-token-here';

const config = {
  headers: {
    'Authorization': `Bearer ${API_TOKEN}`,
    'Content-Type': 'application/json'
  }
};

// 拨打电话
axios.post(`${BASE_URL}/api/v1/call`, {
  phone_number: '1234567890'
}, config)
.then(response => console.log(response.data))
.catch(error => console.error(error));

// 发送短信
axios.post(`${BASE_URL}/api/v1/sms/send`, {
  phone_number: '1234567890',
  message: 'Hello from Node.js'
}, config)
.then(response => console.log(response.data))
.catch(error => console.error(error));
```

---

## 📦 部署指南

### 系统要求

- Android 设备（已 root）
- Termux 应用
- Android 15 兼容

---

### 步骤 1：在 Termux 中准备环境

```bash
# 进入目录
cd /data/data/com.termux/files/home/autosignin/android-telecom-api
```

---

### 步骤 2：运行安装脚本

```bash
chmod +x install.sh
./install.sh
```

**安装脚本会**:
- ✅ 安装 Python 和依赖包
- ✅ 生成 API Token
- ✅ 创建服务管理脚本
- ✅ 创建配置目录 `~/.telecom-api`

---

### 步骤 3：启动服务

```bash
chmod +x start-service.sh
./start-service.sh start
```

---

### 步骤 4：检查服务状态

```bash
./start-service.sh status
```

---

## 🔧 服务管理

### 基本命令

```bash
# 启动服务
./start-service.sh start

# 停止服务
./start-service.sh stop

# 重启服务
./start-service.sh restart

# 查看状态
./start-service.sh status

# 查看日志
./start-service.sh logs

# 查看 API Token
./start-service.sh token
```

---

### 手动管理

```bash
# 查看进程
adb shell ps -A | grep python

# 查看端口
adb shell netstat -tlnp | grep 5000

# 查看日志
adb shell cat ~/.telecom-api/server.log

# 重启服务
adb shell "su -c 'pkill -f server.py; cd ~/autosignin/android-telecom-api && python3 server.py &'"
```

---

## 🔄 开机自启动

### 配置自动启动

```bash
# 1. 运行自启动配置脚本（只需运行一次）
chmod +x setup-boot-start.sh
./setup-boot-start.sh
```

**配置脚本会**:
- ✅ 安装 `termux-boot` 包
- ✅ 创建 `~/.termux/boot` 目录
- ✅ 复制启动脚本到 boot 目录
- ✅ 设置执行权限

---

### 授予自启动权限

1. 打开 Android 的 **设置** → **应用** → **Termux:Boot**
2. 进入 **自启动管理** 或 **电池优化**
3. 允许 Termux:Boot 自启动
4. 将 Termux 和 Termux:Boot 加入电池优化白名单

---

### 测试自启动

```bash
# 手动测试启动脚本
./boot-start.sh

# 等待几秒后，检查服务状态
./start-service.sh status
```

---

### 重启验证

```bash
# 重启设备
adb reboot

# 重启后检查服务是否自动运行
./start-service.sh status

# 查看自启动日志
cat ~/.telecom-api/boot-start.log

# 查看服务日志
cat ~/.telecom-api/server.log
```

---

### 禁用自启动

```bash
# 删除 boot 目录中的脚本
rm ~/.termux/boot/boot-start.sh
```

---

## 🌐 网络配置

### 监听地址

服务默认监听 `0.0.0.0:5000`，允许局域网访问。

---

### 获取设备 IP

在 Termux 中运行：

```bash
ip addr show
# 或
ifconfig
```

---

### 防火墙设置

确保 Android 防火墙允许 5000 端口访问（如有需要）。

---

## 🔒 安全建议

### 1. 修改默认 API Token

```bash
# 生成新 Token
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# 保存到配置文件
echo "your-new-token" > ~/.telecom-api/api_token

# 重启服务
./start-service.sh restart
```

---

### 2. 使用 HTTPS（生产环境推荐）

- 使用反向代理（如 nginx）
- 配置 SSL 证书

---

### 3. 限制访问 IP

- 在路由器或防火墙层面限制
- 只允许信任的 IP 访问

---

### 4. 定期查看日志

```bash
./start-service.sh logs
```

---

### 5. 不要将 API Token 泄露给他人

---

## 🔍 故障排查

### 服务无法启动

```bash
# 查看日志
./start-service.sh logs

# 手动运行查看错误
python3 server.py
```

---

### Root 权限问题

确保 Termux 已获得 root 权限：

```bash
su -c "echo test"
```

---

### 数据库访问失败

不同 Android ROM 的短信/通话数据库路径可能不同：

- 短信：`/data/data/com.android.providers.telephony/databases/mmssms.db`
- 通话：`/data/data/com.android.providers.contacts/databases/calls.db`

可能需要根据实际路径修改 `server.py` 中的 SQL 查询命令。

---

### 端口被占用

修改监听端口：

```bash
export FLASK_RUN_PORT=5001
python3 server.py
```

或在 `server.py` 中修改 `app.run()` 的 port 参数。

---

### 服务自动停止

Android 系统可能会杀死后台进程。解决方案：

1. **关闭电池优化**
   - 设置 → 应用 → Termux → 电池 → 无限制

2. **锁定后台**
   - 在多任务界面锁定 Termux

3. **使用 termux-wake-lock**
   - 在启动脚本中添加 `termux-wake-lock`

---

## ⚙️ 高级配置

### 修改监听端口

编辑 `server.py`，找到最后一行：

```python
app.run(host='0.0.0.0', port=5000, debug=False)
```

修改 port 参数。

---

### 环境变量

- `TELECOM_API_TOKEN`: API 认证 Token
- `FLASK_ENV`: 运行环境（development/production）
- `FLASK_DEBUG`: 调试模式（0/1）

---

### 修改启动延迟

如果系统启动较慢，可以增加等待时间：

编辑 `termux-boot/boot-start.sh`：

```bash
sleep 30  # 增加等待时间
```

---

### 添加启动通知

在 `boot-start.sh` 中添加：

```bash
termux-notification --title "Telecom API" --content "服务已启动"
```

---

### 网络依赖

如果服务依赖网络，可以在 `boot-start.sh` 中添加网络检查：

```bash
# 等待网��就绪
while ! ping -c 1 8.8.8.8 &>/dev/null; do
    sleep 2
done
```

---

## 📁 项目结构

```
android-telecom-api/
├── server.py              # 主服务器代码
├── install.sh             # 安装脚本
├── start-service.sh       # 服务管理脚本
├── boot-start.sh          # 开机自启动脚本
├── setup-boot-start.sh    # 自启动配置脚本
├── termux-boot/           # Termux Boot 目录
│   └── boot-start.sh      # Termux:Boot 启动脚本
└── README.md              # 说明文档
```

---

## ⚠️ 注意事项

1. **此服务需要 root 权限**
2. **请确保在安全的网络环境中使用**
3. **不要将 API Token 泄露给他人**
4. **生产环境建议使用 HTTPS**
5. **Android 15 可能对后台服务有限制，可能需要保持 Termux 在前台运行**
6. **使用开机自启动功能时，请确保授予 Termux:Boot 自启动权限**

---

## 📚 相关文档

- ~~[打电话&发短信.md](./打电话&发短信.md)~~ - 已整合到本文档
- ~~[短信&电话上报.md](./短信&电话上报.md)~~ - 已整合到本文档

---

## 📬 短信&电话上报系统

### 系统概述

**短信&电话上报系统** 是一个独立的后台服务，与 Android Telecom API 互补但功能不同：

| 特性 | Android Telecom API | 短信&电话上报系统 |
|------|---------------------|------------------|
| **方向** | 远程 → 手机（拉取） | 手机 → 远程（推送） |
| **功能** | 打电话、发短信、查询 | 未接来电上报、短信上报 |
| **实现方式** | HTTP Server (Flask) | Python 轮询脚本 |
| **触发方式** | 被动响应 API 调用 | 主动轮询数据库 |
| **推送通知** | ❌ 无 | ✅ Bark iOS 推送 |
| **脚本文件** | `server.py` | `call_sms_forwarding.py` |

**系统特点**：
- ✅ 基于 SQLite 数据库轮询（可靠性优先）
- ✅ 状态持久化，重启不丢失
- ✅ 双重去重机制（时间戳 + _id）
- ✅ Bark iOS 推送通知
- ✅ 生产环境部署（HTTPS）

---

### call_sms_forwarding.py 完整源码

**脚本位置**: 
- 本地：`/Users/mac/Documents/workspace/krio/autosignin/scripts/call_sms_forwarding.py`
- 手机：`/data/data/com.termux/files/home/scripts/call_sms_forwarding.py`

**完整源码**:

```python
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
        commands = [
            "CREATE TABLE IF NOT EXISTS forward_state (id INTEGER PRIMARY KEY, last_call_timestamp TEXT, last_call_id INTEGER, last_sms_timestamp TEXT, last_sms_id INTEGER, pending_calls TEXT, pending_sms TEXT);",
            "INSERT OR IGNORE INTO forward_state (id, last_call_timestamp, last_call_id, last_sms_timestamp, last_sms_id, pending_calls, pending_sms) VALUES (1, '0', 0, '0', 0, '[]', '[]');"
        ]
        
        for sql in commands:
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
        if update_type == 'call':
            sql = f"UPDATE forward_state SET last_call_timestamp = '{state['last_call_timestamp']}', last_call_id = {state['last_call_id']}, pending_calls = '{json.dumps(state.get('pending_calls', []))}' WHERE id = 1;"
        elif update_type == 'sms':
            sql = f"UPDATE forward_state SET last_sms_timestamp = '{state['last_sms_timestamp']}', last_sms_id = {state['last_sms_id']}, pending_sms = '{json.dumps(state.get('pending_sms', []))}' WHERE id = 1;"
        else:
            sql = f"UPDATE forward_state SET last_call_timestamp = '{state['last_call_timestamp']}', last_call_id = {state['last_call_id']}, last_sms_timestamp = '{state['last_sms_timestamp']}', last_sms_id = {state['last_sms_id']}, pending_calls = '{json.dumps(state.get('pending_calls', []))}', pending_sms = '{json.dumps(state.get('pending_sms', []))}' WHERE id = 1;"
        
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

    pending = state.get("pending_calls", [])
    if pending:
        logger.info(f"重试转发 {len(pending)} 条待处理的未接来电...")
        still_pending = []
        for call in pending:
            if not forward_call(call):
                still_pending.append(call)
        state["pending_calls"] = still_pending

    for call in new_calls:
        if not forward_call(call):
            state["pending_calls"].append(call)

    if new_calls:
        state["last_call_timestamp"] = new_calls[-1]["call_time"]
        state["last_call_id"] = new_calls[-1]["call_id"]


def poll_new_sms(state):
    """轮询新短信"""
    new_sms_list = query_new_sms(state["last_sms_timestamp"], state.get("last_sms_id", 0))

    pending = state.get("pending_sms", [])
    if pending:
        logger.info(f"重试转发 {len(pending)} 条待处理的短信...")
        still_pending = []
        for sms in pending:
            if not forward_sms(sms):
                still_pending.append(sms)
        state["pending_sms"] = still_pending

    for sms in new_sms_list:
        if not forward_sms(sms):
            state["pending_sms"].append(sms)

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

    if not check_root():
        logger.error("未检测到 Root 权限，服务无法运行")
        return

    logger.info(f"服务器：{SERVER_BASE_URL}")
    logger.info(f"来电 API：{CALL_FORWARD_PATH}")
    logger.info(f"短信 API：{SMS_FORWARD_PATH}")
    logger.info(f"状态数据库：{STATE_DB}")

    call_thread = threading.Thread(target=call_poll_loop, daemon=True)
    sms_thread = threading.Thread(target=sms_poll_loop, daemon=True)

    call_thread.start()
    sms_thread.start()

    logger.info("服务已启动，等待事件...")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("服务已停止")


if __name__ == "__main__":
    main()
```

---

### 配置说明

**核心配置项**：

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| TEST_MODE | 测试模式开关 | `False` = 生产模式 |
| BARK_URL | Bark 推送密钥 | `https://api.day.app/你的密钥` |
| BARK_ENABLED | 是否启用 Bark 推送 | `True` |
| BARK_ICON | Bark 推送自定义图标 | 图片 URL |
| SERVER_BASE_URL | 服务器地址 | `https://yqad.hxfssc.com:8088` |
| API_TOKEN | API 认证 Token | `api_token_xxx` |
| CALL_POLL_INTERVAL | 来电轮询间隔（秒） | `10` |
| SMS_POLL_INTERVAL | 短信轮询间隔（秒） | `5` |

---

### 部署步骤

**前提条件**：
1. ✅ Android 设备已 Root
2. ✅ 已安装 Termux 应用
3. ✅ Termux 已安装 Python 3 和 sqlite3
4. ✅ 手机已授予 Termux Root 权限

**部署命令**：

```bash
# 1. 推送脚本到手机
adb push /Users/mac/Documents/workspace/krio/autosignin/scripts/call_sms_forwarding.py /sdcard/脚本/

# 2. 复制到 Termux 脚本目录
adb shell "su -c 'cp /sdcard/脚本/call_sms_forwarding.py /data/data/com.termux/files/home/scripts/'"

# 3. 赋予执行权限
adb shell "su -c 'chmod +x /data/data/com.termux/files/home/scripts/call_sms_forwarding.py'"

# 4. 启动服务
adb shell "su -c 'nohup /data/data/com.termux/files/usr/bin/python3 /data/data/com.termux/files/home/scripts/call_sms_forwarding.py > /sdcard/脚本/forward.log 2>&1 &'"
```

**检查服务状态**：

```bash
# 查看进程
adb shell "su -c 'ps | grep call_sms_forwarding'"

# 查看日志
adb shell "cat /sdcard/脚本/forward.log"

# 查看数据库状态
adb shell "su -c 'sqlite3 /data/data/com.termux/files/home/scripts/call_sms_forwarding_state.db \"SELECT * FROM forward_state;\"'"
```

---

### Bark 推送配置

**获取 Bark 密钥**：
1. 在 iOS 设备下载 Bark App
2. 打开 App 获取推送密钥（URL 最后一部分）
3. 示例：`https://api.day.app/Asbu4fr2HjGAjKbHANNbLS`

**自定义推送图标**：

在 Bark URL 后添加 `icon` 参数：

```
https://api.day.app/你的密钥/标题/内容？icon=图片 URL
```

**推送格式**：
- **未接来电**：��题=电话号码，内容=`未接来电：YYYY-MM-DD HH:MM:SS`
- **短信**：标题=发送方号码，内容=短信正文

---

### 常见问题

**1. 服务无法启动**
- 检查 Root 权限
- 检查 Python 路径
- 查看错误日志

**2. 重复发送历史记录**
- 检查状态数据库
- 手动设置最新 ID：`UPDATE forward_state SET last_call_id = 26, last_sms_id = 12 WHERE id = 1;`

**3. API Token 无效**
- 确认 Token 格式正确
- 检查服务器端配置

**4. Bark 推送不生效**
- 检查 Bark URL
- 确认 `BARK_ENABLED = True`
- 检查网络连接

---

## 📡 服务端 API 接口（MOBILE_API）

### 系统架构

短信&电话上报系统包含两个组件：

```
┌─────────────────┐      HTTP POST       ┌──────────────────┐
│  Android 手机    │ ──────────────────► │  服务端 (Node.js) │
│  (call_sms_     │   上报未接来电/短信   │  + MySQL 数据库  │
│   forwarding.py)│                      │                  │
└─────────────────┘                      └──────┬───────────┘
                                                │
                                         提供查询 API
                                                │
                                    ┌───────────▼───────────┐
                                    │  客户端 (浏览器/脚本)  │
                                    └───────────────────────┘
```

**组件说明**：

| 组件 | 功能 | 实现 |
|------|------|------|
| **Android 上报端** | 轮询手机数据库，主动推送 | `call_sms_forwarding.py` |
| **服务端 API** | 接收上报，存储到 MySQL | Node.js + Express |
| **查询接口** | 供客户端查询短信/通话记录 | RESTful API |

---

### 服务端 API 文档

**基础路径**: `/api/posts/mobile`

**认证方式**: 混合认证
- **系统内部访问**：Session 会话认证（已登录用户无需 Token）
- **外部设备访问**：API Token 认证（使用发帖 API Token，格式：`Bearer <token>`）

---

### 1. 查询短信列表

**请求**
```http
GET /api/posts/mobile/sms
```

**查询参数**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| limit | number | 否 | 50 | 返回记录数限制 |
| offset | number | 否 | 0 | 偏移量 |
| phone_number | string | 否 | - | 按电话号码筛选 |

**响应示例**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "phoneNumber": "13800138000",
      "content": "您的验证码是 123456",
      "receivedAt": "2024-06-27T10:30:00.000Z",
      "createdAt": "2024-06-27T10:31:00.000Z"
    }
  ]
}
```

**字段说明**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | number | 记录 ID |
| phoneNumber | string | 发送方电话号码 |
| content | string | 短信内容 |
| receivedAt | string (ISO 8601) | 短信接收时间 |
| createdAt | string (ISO 8601) | 记录创建时间 |

---

### 2. 添加短信记录（上报接口）

**请求**
```http
POST /api/posts/mobile/sms
Content-Type: application/json
```

**请求体**
```json
{
  "phone_number": "13800138000",
  "content": "您的验证码是 123456",
  "received_at": "2024-06-27T10:30:00.000Z"
}
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "id": 3
  }
}
```

**说明**：此接口由 `call_sms_forwarding.py` 自动调用，无需手动调用。

---

### 3. 查询未接电话列表

**请求**
```http
GET /api/posts/mobile/missed-calls
```

**查询参数**

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| limit | number | 否 | 50 | 返回记录数限制 |
| offset | number | 否 | 0 | 偏移量 |
| phone_number | string | 否 | - | 按电话号码筛选 |

**响应示例**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "phoneNumber": "13800138000",
      "receivedAt": "2024-06-27T10:30:00.000Z",
      "createdAt": "2024-06-27T10:31:00.000Z"
    }
  ]
}
```

---

### 4. 添加未接电话记录（上报接口）

**请求**
```http
POST /api/posts/mobile/missed-calls
Content-Type: application/json
```

**请求体**
```json
{
  "phone_number": "13800138000",
  "received_at": "2024-06-27T10:30:00.000Z"
}
```

**响应示例**
```json
{
  "success": true,
  "data": {
    "id": 3
  }
}
```

**说明**：此接口由 `call_sms_forwarding.py` 自动调用，无需手动调用。

---

### 5. 数据库表结构

**手机短信表 (mobile_sms)**
```sql
CREATE TABLE mobile_sms (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone_number VARCHAR(50) NOT NULL COMMENT '电话号码',
  content TEXT NOT NULL COMMENT '短信内容',
  received_at DATETIME NOT NULL COMMENT '接收时间',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  INDEX idx_phone_number (phone_number),
  INDEX idx_received_at (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='手机短信记录表';
```

**未接电话表 (missed_calls)**
```sql
CREATE TABLE missed_calls (
  id INT AUTO_INCREMENT PRIMARY KEY,
  phone_number VARCHAR(50) NOT NULL COMMENT '电话号码',
  received_at DATETIME NOT NULL COMMENT '接收时间',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  INDEX idx_phone_number (phone_number),
  INDEX idx_received_at (received_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='未接电话记录表';
```

---

### 6. 使用示例

**Python 查询短信**
```python
import requests

BASE_URL = 'http://localhost:3001'
API_TOKEN = 'your-api-token'

# 查询短信列表
def get_sms_list(limit=50):
    response = requests.get(
        f'{BASE_URL}/api/posts/mobile/sms',
        params={'limit': limit},
        headers={'Authorization': f'Bearer {API_TOKEN}'}
    )
    result = response.json()
    
    if result['success']:
        print(f'共 {len(result["data"])} 条短信')
        for sms in result['data']:
            print(f"{sms['phoneNumber']}: {sms['content']}")

# 使用示例
get_sms_list()
```

**cURL 查询未接电话**
```bash
curl -X GET "http://localhost:3001/api/posts/mobile/missed-calls?limit=50" \
  -H "Authorization: Bearer YOUR_API_TOKEN"
```

---

### 7. 完整工作流程

**步骤 1**: Android 手机收到短信/未接来电

**步骤 2**: `call_sms_forwarding.py` 轮询到事件

**步骤 3**: 调用服务端 API 上报
```python
# call_sms_forwarding.py 自动执行
POST https://yqad.hxfssc.com:8088/api/posts/mobile/sms
{
  "phone_number": "10086",
  "content": "您的话费余额不足...",
  "received_at": "2026-06-28T10:30:00.000Z"
}
```

**步骤 4**: 服务端存储到 MySQL 数据库

**步骤 5**: 客户端查询 API 获取记录
```bash
GET https://yqad.hxfssc.com:8088/api/posts/mobile/sms
```

---

### 8. 注意事项

1. **认证方式**: 
   - 系统内部访问（Web 管理界面）：使用 Session Cookie，无需 Token
   - 外部设备访问：使用发帖 API Token，格式为 `Authorization: Bearer <token>`
2. **时间格式**: 时间字段使用 ISO 8601 格式 (如：`2024-06-27T10:30:00.000Z`)
3. **字符编码**: 请求和响应都使用 UTF-8 编码
4. **分页查询**: 建议使用 `limit` 和 `offset` 参数进行分页查询
5. **数据清理**: 建议定期清理过期数据，避免数据库过大

---

## 🔗 参考链接

- Termux 官方文档：https://wiki.termux.com/
- Flask 官方文档：https://flask.palletsprojects.com/
- Android Telecom API：https://developer.android.com/reference/android/telecom/package-summary
- Bark 推送：https://api.day.app/
- Node.js Express：https://expressjs.com/

---

**文档更新时间**: 2026-06-28  
**服务版本**: 2.0.0（整合短信&电话上报系统 + 服务端 API）
