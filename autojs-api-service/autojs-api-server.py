#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
AutoJS API Service - Python HTTP Server
通过 HTTP 接口远程调用 AutoJS 脚本
"""

import json
import subprocess
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import logging

# 配置
API_PORT = 8899
SCRIPTS_DIR = "/sdcard/脚本"
AUTOJS_PACKAGE = "org.autojs.autojs6"
AUTOJS_ACTIVITY = f"{AUTOJS_PACKAGE}/org.autojs.autojs.external.open.RunIntentActivity"
API_TOKEN = "api_token_2ad316f6d071285a1929c9417db4ccc7b23133f96a960adf18534cb1f4380fa2"

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AutoJSAPIHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""
    
    def log_message(self, format, *args):
        """重定向日志到 Android logcat"""
        logger.info(f"{self.address_string()} - {format % args}")
    
    def send_json_response(self, status_code, data):
        """发送 JSON 响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def check_auth(self):
        """检查认证"""
        auth_header = self.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            return token == API_TOKEN
        return False
    
    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/api/health':
            # 健康检查（不需要认证）
            self.send_json_response(200, {
                'success': True,
                'message': 'Service is running',
                'service': 'AutoJS API'
            })
        
        elif path == '/api/scripts':
            # 获取脚本列表（需要认证）
            if not self.check_auth():
                self.send_json_response(401, {
                    'success': False,
                    'error': 'Unauthorized'
                })
                return
            
            scripts = list_scripts()
            self.send_json_response(200, {
                'success': True,
                'message': '获取脚本列表成功',
                'data': {'scripts': scripts}
            })
        
        else:
            self.send_json_response(404, {
                'success': False,
                'error': 'Not Found'
            })
    
    def do_POST(self):
        """处理 POST 请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        if path == '/api/execute':
            # 执行脚本（需要认证）
            if not self.check_auth():
                self.send_json_response(401, {
                    'success': False,
                    'error': 'Unauthorized'
                })
                return
            
            # 读取请求体
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body)
                script_name = data.get('script')
                sync_mode = data.get('sync', False)
                
                if not script_name:
                    self.send_json_response(400, {
                        'success': False,
                        'error': '缺少必要参数：script'
                    })
                    return
                
                # 执行脚本
                result = execute_script(script_name, sync_mode)
                
                if result['success']:
                    self.send_json_response(200, {
                        'success': True,
                        'message': '脚本执行成功',
                        'data': {
                            'script': script_name,
                            'sync': sync_mode
                        }
                    })
                else:
                    self.send_json_response(500, {
                        'success': False,
                        'message': '脚本执行失败',
                        'error': result.get('error', 'Unknown error')
                    })
            
            except json.JSONDecodeError:
                self.send_json_response(400, {
                    'success': False,
                    'error': '无效的 JSON 格式'
                })
        
        else:
            self.send_json_response(404, {
                'success': False,
                'error': 'Not Found'
            })


def list_scripts():
    """列出脚本目录中的所有 JS 文件"""
    scripts = []
    if os.path.isdir(SCRIPTS_DIR):
        for filename in os.listdir(SCRIPTS_DIR):
            if filename.endswith('.js'):
                scripts.append(filename)
    return sorted(scripts)


def execute_script(script_name, sync=False):
    """执行 AutoJS 脚本"""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    
    # 检查脚本是否存在
    if not os.path.isfile(script_path):
        logger.error(f"脚本不存在：{script_path}")
        return {
            'success': False,
            'error': f'脚本不存在：{script_name}'
        }
    
    try:
        # 使用 am start 命令启动 AutoJS 脚本
        cmd = [
            'am', 'start', '-n', AUTOJS_ACTIVITY,
            '-a', 'android.intent.action.VIEW',
            '-d', f'file://{script_path}',
            '-t', 'application/x-javascript'
        ]
        
        logger.info(f"执行脚本：{script_name}")
        subprocess.run(cmd, check=True, capture_output=True)
        
        if sync:
            logger.info("同步模式，等待 5 秒...")
            subprocess.run(['sleep', '5'])
        
        return {'success': True}
    
    except subprocess.CalledProcessError as e:
        logger.error(f"执行脚本失败：{e}")
        return {
            'success': False,
            'error': f'am start 命令执行失败：{str(e)}'
        }
    except Exception as e:
        logger.error(f"执行脚本异常：{e}")
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("AutoJS API Service 启动")
    logger.info(f"API 端口：{API_PORT}")
    logger.info(f"脚本目录：{SCRIPTS_DIR}")
    logger.info(f"AutoJS 包名：{AUTOJS_PACKAGE}")
    logger.info("=" * 50)
    
    server = HTTPServer(('0.0.0.0', API_PORT), AutoJSAPIHandler)
    logger.info(f"服务器已启动，监听端口 {API_PORT}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务器...")
        server.shutdown()
        logger.info("服务器已关闭")


if __name__ == '__main__':
    main()
