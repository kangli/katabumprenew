import os
import time
import json
import datetime
import requests
from bs4 import BeautifulSoup

# ==================== 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

# ==================== Cookie 管理 ====================
def parse_cookie_string(cookie_str):
    """解析 cookie 字符串为 requests.Session 可用的格式
    支持格式: "key1=value1; key2=value2"
    """
    session = requests.Session()
    if not cookie_str:
        raise Exception("KB_COOKIE 环境变量未设置")
    
    cookies = {}
    for pair in cookie_str.split(';'):
        pair = pair.strip()
        if '=' in pair:
            key, value = pair.split('=', 1)
            cookies[key.strip()] = value.strip()
    
    if cookies:
        for key, value in cookies.items():
            session.cookies.set(key, value, domain='dashboard.katabump.com')
        log(f"[Cookie] 加载成功，{len(cookies)} 个 cookie: {list(cookies.keys())}")
        return session
    
    raise Exception("无法解析 KB_COOKIE")

def verify_cookie(session):
    """验证 Cookie 是否有效"""
    try:
        resp = session.get('https://dashboard.katabump.com/servers', timeout=15)
        if resp.status_code == 401 or resp.status_code == 403:
            log("[验证] Cookie 已过期或无效")
            return False
        if 'login' in resp.url.lower() or 'auth/login' in resp.url:
            log("[验证] Cookie 已失效，重定向到登录页")
            return False
        log("[验证] Cookie 验证成功")
        return True
    except Exception as e:
        log(f"[验证] Cookie 验证失败: {e}")
        return False

# ==================== 续期核心逻辑 ====================
def renew_server(session, target_url):
    """
    通过 Cookie 访问续期页面并点击续期按钮
    返回 (success: bool, message: str)
    """
    log(f"[续期] 访问页面: {target_url}")
    
    try:
        resp = session.get(target_url, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        
        # 解析 HTML
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 检查是否被重定向到登录页
        if 'login' in resp.url.lower() or 'auth/login' in resp.url:
            return False, "Cookie 已失效，重定向到登录页"
        
        # 检查是否有 "Not yet due" 或类似提示
        page_text = resp.text.lower()
        if "not yet due" in page_text or "cannot renew" in page_text:
            return True, "未到期"
        
        # 检查是否有 "success" 或 "renewed" 提示
        if "success" in page_text or "renewed" in page_text or "renewal" in page_text:
            return True, "续期成功"
        
        # 检查 suspend/expired
        if "suspend" in page_text or "expired" in page_text or "terminated" in page_text:
            return True, "服务器已 suspend/expired（无需续期）"
        
        # 寻找 Renew 按钮
        renew_btn = soup.find('button', class_='btn-outline-primary')
        if not renew_btn:
            renew_btn = soup.find('button', string=lambda s: s and 'renew' in s.lower())
        
        if not renew_btn:
            return False, "未找到续期按钮"
        
        log("[续期] 找到 Renew 按钮")
        
        # 尝试通过表单提交
        form = soup.find('form')
        if form:
            action = form.get('action', '')
            method = form.get('method', 'post').upper()
            
            # 获取所有表单字段
            form_data = {}
            for input_elem in form.find_all('input'):
                name = input_elem.get('name')
                value = input_elem.get('value', '')
                input_type = input_elem.get('type', 'text')
                
                if input_type == 'button':
                    continue
                
                if name:
                    form_data[name] = value
            
            if method == 'POST' and action:
                log("[续期] 提交续期表单...")
                post_url = action if action.startswith('http') else f"{target_url.rsplit('/', 1)[0]}/{action}"
                post_resp = session.post(post_url, data=form_data, timeout=15, allow_redirects=True)
                
                if post_resp.status_code == 200:
                    post_text = post_resp.text.lower()
                    if "success" in post_text or "renewed" in post_text:
                        return True, "续期成功"
                    elif "not yet due" in post_text or "cannot renew" in post_text:
                        return True, "未到期"
                    else:
                        return True, "续期请求已处理"
                else:
                    return False, f"提交失败，HTTP {post_resp.status_code}"
        else:
            # 尝试寻找 API 端点
            onclick = renew_btn.get('onclick', '')
            data_url = renew_btn.get('data-url', '')
            data_method = renew_btn.get('data-method', '')
            
            if data_url:
                log(f"[续期] 找到 data-url: {data_url}")
                method = data_method.upper() if data_method else 'POST'
                api_resp = session.post(data_url, timeout=15, allow_redirects=True)
                if api_resp.status_code == 200:
                    return True, "续期成功"
                else:
                    return False, f"API 请求失败，HTTP {api_resp.status_code}"
            else:
                return False, "未找到续期 API 端点"
    
    except Exception as e:
        return False, f"异常: {e}"

# ==================== 主程序 ====================
def job():
    final_status_message = "任务因未知原因中断"
    success = False
    
    try:
        cookie_str = os.environ.get("KB_COOKIE")
        target_url = os.environ.get("KB_RENEW_URL")
        
        if not cookie_str or not target_url:
            raise Exception("KB_COOKIE 或 KB_RENEW_URL 环境变量未设置")
        
        log(f"[配置] target_url={target_url}")
        
        # 解析 Cookie
        session = parse_cookie_string(cookie_str)
        
        # 验证 Cookie
        if not verify_cookie(session):
            raise Exception("Cookie 验证失败，请重新获取")
        
        # 执行续期
        log("[Step 1] 开始续期...")
        success, message = renew_server(session, target_url)
        final_status_message = message
        
        log(f"[结果] {message}")
    
    except Exception as e:
        final_status_message = f"发生严重异常: {e}"
        log(f"[错误] {final_status_message}")
    
    finally:
        log(f"[结束] 最终状态: {final_status_message}")
        
        if not success and "成功" not in final_status_message and "未到期" not in final_status_message and "suspend" not in final_status_message.lower():
            exit(1)

if __name__ == "__main__":
    job()
