import os
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def renew_server(email, password):
    target_url = os.environ.get("KB_RENEW_URL")
    if not target_url:
        log("[错误] KB_RENEW_URL 未设置")
        return False
    
    log(f"[目标] {target_url}")
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'linux', 'desktop': True})
    scraper.verify = False
    
    # Step 1: 访问登录页，获取 CSRF token
    login_url = "https://dashboard.katabump.com/auth/login"
    log("[登录] 访问登录页...")
    resp = scraper.get(login_url, timeout=15)
    if resp.status_code != 200:
        log(f"[错误] 登录页 HTTP {resp.status_code}")
        return False
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    csrf_input = soup.find('input', {'name': '_csrf_token'}) or soup.find('input', {'name': 'csrf_token'}) or soup.find('input', {'name': '_csrf'})
    if csrf_input and csrf_input.get('value'):
        login_data = {
            'email': email,
            'password': password,
            csrf_input['name']: csrf_input['value']
        }
        log("[登录] 发现 CSRF token")
    else:
        login_data = {'email': email, 'password': password}
    
    # Step 2: 提交登录
    log(f"[登录] POST {login_url}...")
    resp = scraper.post(login_url, data=login_data, timeout=15, allow_redirects=True)
    
    log(f"[登录] 跳转: {resp.url}")
    if 'login' in resp.url.lower():
        log("[错误] 登录失败，仍停留在登录页")
        log(f"[调试] 状态码: {resp.status_code}, 标题: {BeautifulSoup(resp.text, 'html.parser').title.string if BeautifulSoup(resp.text, 'html.parser').title else 'None'}")
        return False
    
    log("[登录] 成功")
    
    # Step 3: 访问续期页面
    log(f"[续期] 访问 {target_url}")
    resp = scraper.get(target_url, timeout=15)
    if resp.status_code != 200:
        log(f"[错误] 续期页 HTTP {resp.status_code}")
        return False
    
    if 'login' in resp.url.lower():
        log("[错误] Cookie 已失效")
        return False
    
    soup = BeautifulSoup(resp.text, 'html.parser')
    page_text = resp.text.lower()
    
    # 检查状态
    if "not yet due" in page_text or "cannot renew" in page_text:
        log("[成功] 未到期")
        return True
    if "success" in page_text or "renewed" in page_text:
        log("[成功] 续期成功")
        return True
    if "suspend" in page_text or "expired" in page_text:
        log("[完成] 服务器已 suspend/expired")
        return True
    
    # 找 Renew 按钮
    btn = soup.find('button', class_='btn-outline-primary')
    if not btn:
        btn = soup.find('button', string=lambda s: s and 'renew' in s.lower())
    
    if not btn:
        log("[错误] 未找到 Renew 按钮")
        return False
    
    log("[续期] 找到 Renew 按钮")
    
    # 尝试表单提交
    form = soup.find('form')
    if form and form.get('action'):
        action = form['action']
        post_url = action if action.startswith('http') else f"{target_url.rsplit('/', 1)[0]}/{action}"
        log(f"[续期] POST {post_url}")
        resp = scraper.post(post_url, data={}, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            log("[成功] 续期请求已发送")
            return True
    
    # 尝试 data-url
    data_url = btn.get('data-url', '')
    if data_url:
        log(f"[续期] POST {data_url}")
        resp = scraper.post(data_url, timeout=15, allow_redirects=True)
        if resp.status_code == 200:
            log("[成功] 续期请求已发送")
            return True
    
    log("[警告] 未找到续期 API 端点")
    return False

if __name__ == "__main__":
    email = os.environ.get("KB_EMAIL")
    password = os.environ.get("KB_PASSWORD")
    if not email or not password:
        log("[错误] 需要 KB_EMAIL 和 KB_PASSWORD")
        exit(1)
    success = renew_server(email, password)
    exit(0 if success else 1)
