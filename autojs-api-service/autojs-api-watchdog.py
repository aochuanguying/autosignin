#!/data/data/com.termux/files/usr/bin/python3
# -*- coding: utf-8 -*-
"""
AutoJS API Service 看门狗监控脚本
监控主服务进程，确保服务始终可用
"""

import subprocess
import time
import os
import sys
import logging
from datetime import datetime

# 配置
API_PORT = 8899
SERVER_SCRIPT = "/sdcard/autojs-api-server.py"
PID_FILE = "/sdcard/autojs-api.pid"
LOG_FILE = "/sdcard/autojs-api-watchdog.log"
MAX_RESTART_COUNT = 5
RESTART_INTERVAL = 60  # 秒
CHECK_INTERVAL = 30  # 秒

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def check_port_listening():
    """检查端口是否被监听"""
    try:
        result = subprocess.run(
            ['netstat', '-tlnp'],
            capture_output=True,
            text=True
        )
        return f':{API_PORT}' in result.stdout
    except Exception as e:
        logger.error(f"检查端口失败：{e}")
        return False


def check_process_running():
    """检查主服务进程是否运行"""
    try:
        result = subprocess.run(
            ['ps', '-A'],
            capture_output=True,
            text=True
        )
        return 'autojs-api-server.py' in result.stdout
    except Exception as e:
        logger.error(f"检查进程失败：{e}")
        return False


def get_server_pid():
    """获取服务器 PID"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                return int(f.read().strip())
        except:
            pass
    return None


def start_service():
    """启动主服务"""
    try:
        logger.info("启动 AutoJS API 服务...")
        
        # 使用 nohup 启动 Python 服务
        cmd = [
            'nohup', 'python3', SERVER_SCRIPT,
            '>', '/sdcard/autojs-api.log', '2>&1', '&'
        ]
        
        subprocess.run(' '.join(cmd), shell=True)
        
        # 等待启动
        time.sleep(3)
        
        # 检查是否启动成功
        if check_port_listening():
            pid = get_server_pid()
            logger.info(f"✓ 服务启动成功 (PID: {pid})")
            return True
        else:
            logger.error("✗ 服务启动失败")
            return False
            
    except Exception as e:
        logger.error(f"启动服务异常：{e}")
        return False


def stop_service():
    """停止主服务"""
    try:
        pid = get_server_pid()
        if pid:
            subprocess.run(['kill', str(pid)], check=True)
            logger.info(f"✓ 服务已停止 (PID: {pid})")
            
            # 清理 PID 文件
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
            return True
        else:
            logger.warning("服务未运行")
            return False
    except Exception as e:
        logger.error(f"停止服务失败：{e}")
        return False


def restart_service(restart_count):
    """重启服务"""
    if restart_count >= MAX_RESTART_COUNT:
        logger.error(f"错误：达到最大重启次数 ({MAX_RESTART_COUNT})，停止重启")
        return False
    
    logger.info(f"正在重启服务 (第 {restart_count+1}/{MAX_RESTART_COUNT} 次)...")
    
    # 停止旧服务
    stop_service()
    time.sleep(2)
    
    # 启动新服务
    if start_service():
        logger.info("✓ 服务重启成功")
        return True
    else:
        logger.error("✗ 服务重启失败")
        return False


def main():
    """主循环"""
    logger.info("=" * 50)
    logger.info("AutoJS API 看门狗启动")
    logger.info(f"监控端口：{API_PORT}")
    logger.info(f"检查间隔：{CHECK_INTERVAL}秒")
    logger.info(f"最大重启次数：{MAX_RESTART_COUNT}")
    logger.info("=" * 50)
    
    restart_count = 0
    last_restart_time = 0
    
    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            
            # 检查服务状态
            port_ok = check_port_listening()
            process_ok = check_process_running()
            
            if not port_ok or not process_ok:
                current_time = time.time()
                
                # 检查重启间隔
                if (current_time - last_restart_time) < RESTART_INTERVAL:
                    logger.warning("服务异常，但重启间隔过短，等待中...")
                    continue
                
                logger.error(f"检测到服务异常 (端口监听：{port_ok}, 进程运行：{process_ok})")
                
                # 重启服务
                if restart_service(restart_count):
                    restart_count = 0
                    last_restart_time = current_time
                else:
                    restart_count += 1
                    last_restart_time = current_time
            else:
                # 服务正常
                logger.info("服务运行正常")
                
        except KeyboardInterrupt:
            logger.info("看门狗被手动停止")
            break
        except Exception as e:
            logger.error(f"看门狗循环异常：{e}")
            time.sleep(5)


if __name__ == '__main__':
    main()
