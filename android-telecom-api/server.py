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
            # 解析 SQLite 输出 (默认用|分隔)
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
        logger.error(f"获取通话记录异常：{str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/v1/audi/token', methods=['GET'])
@require_auth
def get_audi_token():
    """
    获取一汽奥迪 APP Token
    GET /api/v1/audi/token
    从 APP WebView Cookies 数据库中提取有效的 Access Token
    """
    try:
        cookies_db = '/data/data/com.timanetworks.android.frame.audisuper.release/app_webview/Default/Cookies'
        sqlite3_path = '/data/data/com.termux/files/usr/bin/sqlite3'

        # 查询 WebView Cookies 中的 token
        sql = "SELECT value FROM cookies WHERE name='token' AND host_key LIKE '%faw-vw.com' ORDER BY last_access_utc DESC LIMIT 1;"

        try:
            proc = subprocess.run(
                ['su', '--mount-master', '-c', f'{sqlite3_path} {cookies_db} "{sql}"'],
                capture_output=True, text=True, timeout=10
            )
            token = proc.stdout.strip() if proc.returncode == 0 else ''
        except Exception as e:
            token = ''
            logger.error(f"主查询异常: {e}")

        if not token:
            # 备用查询
            sql2 = "SELECT value FROM cookies WHERE value LIKE 'eyJ%' AND host_key LIKE '%faw-vw.com' ORDER BY last_access_utc DESC LIMIT 1;"
            try:
                proc2 = subprocess.run(
                    ['su', '--mount-master', '-c', f'{sqlite3_path} {cookies_db} "{sql2}"'],
                    capture_output=True, text=True, timeout=10
                )
                token = proc2.stdout.strip() if proc2.returncode == 0 else ''
            except Exception as e:
                logger.error(f"备用查询异常: {e}")

            if not token:
                return jsonify({
                    'success': False,
                    'error': 'Failed to extract token from APP cookies'
                }), 502

        if not token.startswith('eyJ'):
            return jsonify({
                'success': False,
                'error': 'Extracted value is not a valid JWT token',
                'details': token[:100]
            }), 502

        logger.info(f"一汽奥迪 Token 提取成功，长度: {len(token)}")
        return jsonify({
            'success': True,
            'data': {
                'token': token,
                'source': 'app_webview/Cookies (faw-vw.com)',
                'token_length': len(token)
            }
        })

    except Exception as e:
        logger.error(f"获取奥迪 Token 异常：{str(e)}")
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
