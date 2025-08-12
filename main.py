#!/usr/bin/env python3
"""
超简单的文件下载服务 - 基于用户名密码认证
使用方法：
1. pip install flask
2. python3 main.py
3. 客户端直接用用户名密码下载文件
"""

import os
import re
import subprocess
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

# 配置
OVPN_DATA = os.getenv('OVPN_DATA')
CLIENTS_DIR = os.path.join(OVPN_DATA, 'clients')
DOWNLOAD_USERNAME = os.getenv('DOWNLOAD_USERNAME')
DOWNLOAD_PASSWORD = os.getenv('DOWNLOAD_PASSWORD')
VPN_SERVER_ADDR = os.getenv('VPN_SERVER_ADDR')

SCRIPTS_DIR = "/usr/bin/"
SCRIPT_FILENAME = "docker-entrypoint.sh"
SCRIPT_PATH = os.path.join(SCRIPTS_DIR, SCRIPT_FILENAME)

# 用户数据 (可以轻松修改添加更多用户)
USERS = {
    DOWNLOAD_USERNAME: DOWNLOAD_PASSWORD,
}

def validate_mac_address(mac):
    """验证并标准化MAC地址"""
    if not mac:
        return None, "MAC地址不能为空"
    
    # 移除所有非十六进制字符
    clean_mac = re.sub(r'[^0-9A-Fa-f]', '', mac)
    
    if len(clean_mac) != 12:
        return None, "MAC地址长度不正确"
    
    # 转换为标准格式
    normalized = ':'.join(clean_mac[i:i+2] for i in range(0, 12, 2)).upper()
    return normalized, None

def check_auth():
    """检查HTTP Basic认证"""
    auth = request.authorization
    
    if not auth or not auth.username or not auth.password:
        return None, "需要用户名和密码"
    
    username = auth.username
    password = auth.password
    
    if username not in USERS or USERS[username] != password:
        return None, "用户名或密码错误"
    
    return username, None

@app.route('/download')
def download_file():
    """下载文件 - 使用HTTP Basic认证"""
    
    # 检查认证
    username, error = check_auth()
    if error:
        return jsonify({'error': error}), 401
    
    # 获取MAC地址参数
    mac_address = request.args.get('mac')
    if not mac_address:
        return jsonify({'error': 'MAC地址参数缺失'}), 400
    
    # 验证MAC地址
    normalized_mac, mac_error = validate_mac_address(mac_address)
    if mac_error:
        return jsonify({'error': mac_error}), 400
    
    # 安全检查文件名
    # if '..' in filename or '/' in filename or '\\' in filename:
    #     return jsonify({'error': '非法文件名'}), 400
    
    # 构建文件路径
    mac_clean = normalized_mac.replace(':', '-')
    filename = f"{mac_clean}.ovpn"
    file_path = os.path.join(CLIENTS_DIR, filename)
    
    print(f"用户 {username} 请求文件: {filename}, MAC: {normalized_mac}")
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"文件不存在，正在生成: {file_path}")
        
        # 调用生成脚本
        script_path = os.path.join(SCRIPTS_DIR, SCRIPT_FILENAME)
        try:
            result = subprocess.run([
                'bash', script_path, "genclient", mac_clean, VPN_SERVER_ADDR], capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                print(f"文件生成失败: {result.stderr}")
                return jsonify({'error': '文件生成失败'}), 500
            
            print(f"文件生成成功: {result.stdout}")
                
        except subprocess.TimeoutExpired:
            return jsonify({'error': '文件生成超时'}), 500
        except Exception as e:
            print(f"执行脚本出错: {e}")
            return jsonify({'error': '文件生成错误'}), 500
    
    # 再次检查文件是否存在
    if not os.path.exists(file_path):
        return jsonify({'error': '文件生成失败或不存在'}), 404
    
    print(f"发送文件: {file_path}")
    
    # 发送文件
    try:
        return send_file(file_path, as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"发送文件出错: {e}")
        return jsonify({'error': '文件发送失败'}), 500

@app.route('/health')
def health():
    """健康检查"""
    return {'status': 'ok', 'users': len(USERS)}

@app.route('/info')
def info():
    """服务信息"""
    return {
        'service': 'Simple File Download Service',
        'auth_method': 'HTTP Basic Auth',
        'users_count': len(USERS),
        'usage': 'curl -u username:password "http://server/download/filename?mac=AA:BB:CC:DD:EE:FF"'
    }

@app.errorhandler(401)
def unauthorized(error):
    """处理401错误，返回WWW-Authenticate头"""
    response = jsonify({'error': '需要认证'})
    response.headers['WWW-Authenticate'] = 'Basic realm="File Download Service"'
    response.status_code = 401
    return response

if __name__ == '__main__':
    # 创建必要的目录
    os.makedirs(FILES_DIR, exist_ok=True)
    # os.makedirs(SCRIPTS_DIR, exist_ok=True)
    
    print("========================================")
    print("简单文件下载服务启动")
    print("========================================")
    print("服务地址: http://localhost:5000")
    print("认证方式: HTTP Basic Auth")
    print()
    print("可用用户:")
    for username, password in USERS.items():
        print(f"  用户名: {username}, 密码: {password}")
    print()
    print("使用示例:")
    print('  curl -u admin:admin123 "http://localhost:5000/download/config.txt?mac=AA:BB:CC:DD:EE:FF"')
    print("========================================")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
