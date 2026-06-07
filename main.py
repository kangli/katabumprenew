import os
import time
import requests
import zipfile
import io
import datetime
import re
from DrissionPage import ChromiumPage, ChromiumOptions

# ==================== 基础工具 ====================
def log(message):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] {message}", flush=True)

def download_silk():
    extract_dir = "extensions/silk_ext"
    if os.path.exists(extract_dir): return os.path.abspath(extract_dir)
    log("[插件1] 正在下载 Silk Privacy Pass...")
    try:
        url="https://clients2.google.com/service/update2/crx?response=redirect&prodversion=122.0&acceptformat=crx2,crx3&x=id%3Dajhmfdgkijocedmfjonnpjfojldioehi%26uc"
        resp=requests.get(url,stream=True,timeout=30)
        if resp.status_code==200:
            os.makedirs("extensions",exist_ok=True)
            zipfile.ZipFile(io.BytesIO(resp.content)).extractall(extract_dir)
            return os.path.abspath(extract_dir)
    except Exception as e:
        log(f"[插件1] 下载异常: {e}")
        return None

def download_cf_autoclick():
    extract_root="extensions/cf_autoclick_root"
    if not os.path.exists(extract_root):
        log("[插件2] 正在下载 CF-AutoClick...")
        try:
            url="https://codeload.github.com/tenacious6/cf-autoclick/zip/refs/heads/master"
            resp=requests.get(url,stream=True,timeout=30)
            if resp.status_code==200:
                os.makedirs("extensions",exist_ok=True)
                zipfile.ZipFile(io.BytesIO(resp.content)).extractall(extract_root)
            else:
                log(f"[插件2] 下载失败: {resp.status_code}")
                return None
        except Exception as e:
            log(f"[插件2] 异常: {e}")
            return None
    for r,_,f in os.walk(extract_root):
        if "manifest.json" in f:
            log(f"[插件2] 路径锁定: {os.path.basename(r)}")
            return os.path.abspath(r)
    return None

def save_debug_html(page, filename):
    """保存页面 HTML 用于调试 - 使用 DrissionPage 正确 API"""
    try:
        html = page.html
        if len(html) > 50000:
            html = html[:20000] + "\n<!-- truncated -->\n" + html[-20000:]
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        log(f"[调试] HTML 已保存到 {filename}")
    except Exception as e:
        log(f"[调试] 保存 HTML 失败: {e}")

def find_renew_buttons(page):
    """寻找所有可能的续期按钮"""
    buttons = []
    selectors = [
        'css:button[data-bs-target="#renew-modal"]',
        'css:button[data-target="#renew-modal"]',
        'css:button:has-text("Renew")',
        'css:button:has-text("续费")',
        'css:button.btn-primary:has-text("Renew")',
        'css:a:has-text("Renew")',
        'css:.btn:has-text("Renew")',
        'css:button[id*="renew"]',
        'css:button[class*="renew"]',
        'css:input[value*="renew"]',
    ]
    
    for sel in selectors:
        try:
            btns = page.nodes(sel)
            for btn in btns:
                if btn and btn.states.is_displayed:
                    text = btn.text if hasattr(btn, 'text') else ''
                    buttons.append({'selector': sel, 'text': text, 'el': btn})
        except Exception as e:
            pass
    
    log(f"[调试] 找到 {len(buttons)} 个可能的续期按钮")
    for i, b in enumerate(buttons):
        log(f"  [{i}] selector={b['selector']}, text={b['text']}")
    
    return buttons

def execute_js(page, js_code):
    """执行 JavaScript 代码 - 使用正确的 API"""
    try:
        return page.run_js(js_code)
    except Exception as e:
        log(f"[JS] 执行失败: {e}")
        return []

def wait_for_login(page):
    """等待登录成功，检查是否跳转到 dashboard"""
    log("[登录] 等待登录完成...")
    # 最多等待 30 秒
    for i in range(30):
        url = page.url
        if 'login' not in url or 'dashboard' in url:
            log(f"[登录] 已跳转到: {url}")
            return True
        time.sleep(1)
    
    log("[登录] 登录超时，当前 URL: " + page.url)
    return False

def check_if_logged_in(page):
    """检查是否已登录"""
    url = page.url
    title = page.title
    log(f"[登录] 检查登录状态 - URL: {url}, 标题: {title}")
    
    # 如果 URL 包含 dashboard 或者不包含 login，说明已登录
    if 'dashboard' in url or (url != 'https://dashboard.katabump.com/auth/login' and 'login' not in url):
        log("[登录] 已登录！")
        return True
    
    # 检查页面内容是否包含登出或用户信息
    try:
        body_text = page.ele('css:body').text.lower() if hasattr(page.ele('css:body'), 'text') else ''
        if 'logout' in body_text or 'dashboard' in body_text or 'sign out' in body_text:
            log("[登录] 检测到登出/仪表板元素，已登录")
            return True
    except:
        pass
    
    log("[登录] 未检测到登录成功")
    return False

# ==================== 截图上传与通知 ====================
class Reporter:
    def __init__(self):
        self.screenshots = []
        self.session = requests.Session()

    def add_screenshot(self, page, name):
        try:
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            filename = f"{timestamp}_{name}.png"
            page.get_screenshot(path=filename, full_page=True)
            self.screenshots.append(filename)
            log(f"[截图] 已保存: {filename}")
        except Exception as e:
            log(f"[截图] 失败: {e}")

    def upload_to_telegraph(self) -> str:
        if not self.screenshots: return "没有可上传的截图。"
        log("[上传] 正在上传截图到 Telegra.ph...")
        try:
            valid_screenshots = [f for f in self.screenshots if os.path.exists(f)]
            if not valid_screensshots: return "没有有效的截图文件可上传。"
            files_to_upload = [('file', (os.path.basename(f), open(f, 'rb'), 'image/png')) for f in valid_screenshots]
            upload_resp = self.session.post('https://telegra.ph/upload', files=files_to_upload, timeout=45)
            if upload_resp.status_code != 200: return f"上传失败: {upload_resp.text}"
            content_nodes = []
            for i, item in enumerate(upload_resp.json()):
                src = item.get('src')
                if src: content_nodes.append({"tag": "figure", "children": [{"tag": "img", "attrs": {"src": src}}, {"tag": "figcaption", "children": [os.path.basename(valid_screenshots[i])]}]})
            create_page_resp = self.session.post('https://api.telegra.ph/createPage', data={'access_token': 'd525af2963a7633918569c76192a83e0c03423b98471415053f40f0653d9', 'title': f'Katabump 续期调试报告 - {datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}', 'author_name': 'Auto-Renew Script', 'content': str(content_nodes).replace("'", '"')}, timeout=20)
            if create_page_resp.status_code == 200 and create_page_resp.json().get('ok'):
                page_url = create_page_resp.json()['result']['url']
                log(f"[报告] 截图报告已生成: {page_url}")
                return page_url
            else: return f"创建页面失败: {create_page_resp.text}"
        except Exception as e:
            log(f"[上传] 异常: {e}")
            return f"上传截图时发生异常: {e}"
        finally:
            for f in self.screenshots:
                try: os.remove(f)
                except: pass

    def send_telegram_notification(self, message: str):
        token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if not all([token, chat_id]):
            log("[通知] Telegram Token 或 Chat ID 未设置，跳过通知。")
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": False}
        try:
            requests.post(url, json=data, timeout=20)
            log("[通知] Telegram 通知已发送。")
        except Exception as e:
            log(f"[通知] 发送异常: {e}")

# ==================== 核心逻辑 ====================
def pass_full_page_shield(page):
    for _ in range(3):
        if "just a moment" in page.title.lower():
            log("[门神] 全屏盾出现，等待...")
            time.sleep(3)
        else: return True
    return False

def analyze_page_alert(page):
    """分析页面，返回状态"""
    log("[系统] 检查页面状态...")
    
    url = page.url
    title = page.title
    log(f"[系统] URL: {url}")
    log(f"[系统] 标题: {title}")
    
    # 检查是否已经跳转到 dashboard（说明登录成功）
    if 'dashboard.katabump.com' in url and 'servers' in url:
        log("[系统] 已到达服务器管理页面")
    
    alert_selectors = [
        'css:.alert.alert-danger',
        'css:.alert-danger',
        'css:.alert',
        'css:div.alert',
        'css:span.error',
        'css:div.error',
        'css:div.text-danger',
    ]
    
    for sel in alert_selectors:
        try:
            alert = page.ele(sel, timeout=2)
            if alert and alert.states.is_displayed:
                text = alert.text
                log(f"[系统] 找到 alert ({sel}): {text}")
                if "can't renew" in text.lower() or "cannot renew" in text.lower():
                    log("[结果] 未到期")
                    return "SUCCESS_TOO_EARLY"
                elif "captcha" in text.lower() or "verify" in text.lower():
                    return "FAIL_CAPTCHA"
                else:
                    return "FAIL_OTHER"
        except:
            pass
    
    for sel in alert_selectors:
        try:
            alert = page.ele(sel, timeout=2)
            if alert and alert.states.is_displayed:
                text = alert.text
                if "success" in text.lower() or "renewed" in text.lower() or "renewal" in text.lower():
                    log(f"[结果] 续期成功: {text}")
                    return "SUCCESS"
        except:
            pass
    
    # 检查是否有 "server is suspended" 或 "expired" 提示
    try:
        body = page.ele('css:body', timeout=2)
        if body:
            body_text = body.text.lower()
            if "suspend" in body_text or "expired" in body_text or "terminated" in body_text:
                log(f"[系统] 检测到 suspend/expired 提示")
                return "SERVER_SUSPENDED"
    except:
        pass
    
    log("[系统] 未检测到已知页面状态")
    return "UNKNOWN"

def find_renew_button_js(page):
    """使用 JS 寻找续期按钮"""
    try:
        buttons = page.run_js('''
            () => {
                const results = [];
                const allButtons = document.querySelectorAll('button, a, span, div');
                allButtons.forEach(btn => {
                    const text = btn.textContent || btn.innerText || '';
                    if (text.toLowerCase().includes('renew')) {
                        results.push({
                            tag: btn.tagName,
                            text: text.trim().substring(0, 100),
                            class: btn.className,
                            id: btn.id,
                            href: btn.href
                        });
                    }
                });
                return results;
            }
        ''')
        if buttons and len(buttons) > 0:
            log(f"[JS] 找到 {len(buttons)} 个按钮:")
            for i, b in enumerate(buttons):
                log(f"  [{i}] tag={b['tag']}, text={b['text'][:50]}, class={b['class']}")
            return buttons
    except Exception as e:
        log(f"[JS] 执行失败: {e}")
    return []

# ==================== 主程序 ====================
def job():
    reporter = Reporter()
    page = None
    final_status_message = "任务因未知原因中断"
    
    try:
        reporter.send_telegram_notification("🚀 **Katabump 自动续期任务开始...**")
        
        path_silk = download_silk()
        path_cf = download_cf_autoclick()
        
        co = ChromiumOptions()
        co.set_argument('--headless=new')
        co.set_argument('--no-sandbox')
        co.set_argument('--disable-gpu')
        co.set_argument('--disable-dev-shm-usage')
        co.set_argument('--window-size=1920,1080')
        co.set_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
        plugin_count = 0
        if path_silk:
            co.add_extension(path_silk)
            plugin_count += 1
        if path_cf:
            co.add_extension(path_cf)
            plugin_count += 1
        log(f"[浏览器] 已挂载插件数量: {plugin_count}")
        
        co.auto_port()
        page = ChromiumPage(co)
        page.set.timeouts(20)
        
        email = os.environ.get("KB_EMAIL")
        password = os.environ.get("KB_PASSWORD")
        target_url = os.environ.get("KB_RENEW_URL")
        
        if not all([email, password, target_url]):
            raise Exception("环境变量 KB_EMAIL, KB_PASSWORD, KB_RENEW_URL 未设置")
        log(f"[配置] email={email[:10]}*** url={target_url}")
        
        # ===== Step 1: 登录 =====
        log("[Step 1] 登录...")
        page.get('https://dashboard.katabump.com/auth/login')
        pass_full_page_shield(page)
        reporter.add_screenshot(page, "01_login_page")
        
        if page.ele('css:input[name="email"]'):
            log("[登录] 输入邮箱...")
            page.ele('css:input[name="email"]').input(email)
            log("[登录] 输入密码...")
            page.ele('css:input[name="password"]').input(password)
            log("[登录] 点击提交...")
            page.ele('css:button#submit').click()
            
            # 等待登录完成
            if wait_for_login(page):
                check_if_logged_in(page)
            else:
                log("[登录] 登录未成功，保存调试信息...")
                save_debug_html(page, "debug_login_failed.html")
                reporter.add_screenshot(page, "01_login_failed")
                raise Exception("登录失败")
        else:
            log("[登录] 未找到登录表单，当前页面:")
            save_debug_html(page, "debug_login_form.html")
            reporter.add_screenshot(page, "01_no_form")
        
        # ===== Step 2: 续期 =====
        max_retries = 3
        success = False
        
        for attempt in range(1, max_retries + 1):
            log(f"\n[Step 2] 尝试续期 (第 {attempt} 次)...")
            page.get(target_url)
            pass_full_page_shield(page)
            reporter.add_screenshot(page, f"02_attempt_{attempt}_main_page")
            log(f"[页面] URL: {page.url}")
            log(f"[页面] 标题: {page.title}")
            
            try:
                # 先检查是否有 alert
                result = analyze_page_alert(page)
                if result == "SUCCESS_TOO_EARLY":
                    success = True
                    final_status_message = "任务成功完成！状态: 未到期"
                    log(f"[结果] {final_status_message}")
                    break
                elif result == "SERVER_SUSPENDED":
                    success = True
                    final_status_message = "任务完成！状态: 服务器已 suspend（无需续期）"
                    log(f"[结果] {final_status_message}")
                    break
                elif result == "SUCCESS":
                    success = True
                    final_status_message = "任务成功完成！状态: 续期成功"
                    log(f"[结果] {final_status_message}")
                    break
                
                # 寻找续期按钮
                log("[按钮] 寻找续期按钮...")
                buttons = find_renew_buttons(page)
                
                if not buttons:
                    # 使用 JS 再次查找
                    log("[按钮] 使用 JS 查找...")
                    js_buttons = find_renew_button_js(page)
                    if js_buttons:
                        buttons = [{'selector': f'js:{i}', 'text': b['text'], 'index': i} for i, b in enumerate(js_buttons)]
                    else:
                        log("[按钮] 未找到任何续期按钮")
                        save_debug_html(page, f"debug_attempt_{attempt}_no_button.html")
                        continue
                
                # 点击第一个找到的按钮
                btn_info = buttons[0]
                log(f"[按钮] 点击第一个按钮: selector={btn_info['selector']}, text={btn_info['text'][:50]}")
                
                if 'el' in btn_info:
                    btn_info['el'].click(by_js=True)
                elif 'index' in btn_info:
                    # JS 查找的按钮
                    try:
                        target = page.run_js(f"() => document.querySelectorAll('button, a, span, div')[{btn_info['index']}]")
                        if target:
                            page.run_js('target.click();')
                    except Exception as e:
                        log(f"[按钮] JS 点击失败: {e}")
                        continue
                else:
                    continue
                
                # 等待弹窗或页面变化
                log("[按钮] 等待弹窗...")
                time.sleep(5)
                reporter.add_screenshot(page, f"03_attempt_{attempt}_after_click")
                
                # 检查是否弹出了 modal
                modal = page.ele('css:.modal-content', timeout=5)
                if modal:
                    log("[弹窗] 找到 modal")
                    reporter.add_screenshot(page, f"03_attempt_{attempt}_modal_opened")
                    
                    # 黑盒等待
                    log("[操作] 弹窗出现，等待 20 秒...")
                    time.sleep(20)
                    log("[黑盒等待] 等待结束")
                    reporter.add_screenshot(page, f"04_attempt_{attempt}_after_wait")
                    
                    # 寻找 Renew 按钮
                    final_renew_btn = modal.ele('css:button[type="submit"].btn-primary', timeout=5)
                    if final_renew_btn and final_renew_btn.states.is_enabled:
                        log("[按钮] Renew 按钮已激活，点击...")
                        final_renew_btn.click(by_js=True)
                        log("[等待] 等待响应 (8s)...")
                        time.sleep(8)
                        reporter.add_screenshot(page, f"05_attempt_{attempt}_after_submit")
                        
                        result = analyze_page_alert(page)
                        if result in ["SUCCESS", "SUCCESS_TOO_EARLY"]:
                            final_status_message = f"任务成功完成！状态: {result}"
                            log(f"[结果] {final_status_message}")
                            success = True
                            break
                        elif result == "FAIL_CAPTCHA":
                            log("[结果] 提交后服务器返回验证失败，刷新重试...")
                            time.sleep(3)
                            continue
                        else:
                            log(f"[结果] 未知错误: {result}，重试...")
                            continue
                    else:
                        log("[按钮] Renew 按钮未激活或未找到")
                        # 尝试寻找其他可能的按钮
                        all_btns = modal.nodes('css:button, css:input[type="submit"]')
                        for btn in all_btns:
                            if btn and btn.states.is_displayed:
                                txt = btn.text if hasattr(btn, 'text') else ''
                                log(f"  找到按钮: {txt[:50]}")
                                if 'renew' in txt.lower():
                                    btn.click(by_js=True)
                                    log("[等待] 等待响应 (8s)...")
                                    time.sleep(8)
                                    result = analyze_page_alert(page)
                                    if result in ["SUCCESS", "SUCCESS_TOO_EARLY"]:
                                        final_status_message = f"任务成功完成！状态: {result}"
                                        log(f"[结果] {final_status_message}")
                                        success = True
                                        break
                else:
                    log("[弹窗] 未找到 modal，页面可能已跳转")
                    # 检查是否已经跳转到结果页
                    result = analyze_page_alert(page)
                    if result in ["SUCCESS", "SUCCESS_TOO_EARLY"]:
                        final_status_message = f"任务成功完成！状态: {result}"
                        log(f"[结果] {final_status_message}")
                        success = True
                        break
            
            except Exception as e_inner:
                log(f"[错误] 第 {attempt} 次尝试异常: {e_inner}")
                save_debug_html(page, f"debug_attempt_{attempt}_error.html")
                reporter.add_screenshot(page, f"06_attempt_{attempt}_error")
                continue
        
        if not success:
            final_status_message = "所有重试均失败"
            raise Exception(final_status_message)
    
    except Exception as e_outer:
        final_status_message = f"发生严重异常: {e_outer}"
        log(f"[错误] {final_status_message}")
        if page:
            save_debug_html(page, "debug_critical_error.html")
            reporter.add_screenshot(page, "99_CRITICAL_ERROR")
    
    finally:
        log(f"[结束] 最终状态: {final_status_message}")
        report_url = reporter.upload_to_telegraph()
        
        if "成功" in final_status_message or "未到期" in final_status_message or "suspend" in final_status_message.lower():
            notification_message = f"✅ **Katabump 续期任务完成！**\n\n<b>状态:</b>\n<code>{final_status_message}</code>\n\n<b>调试报告:</b>\n{report_url}"
        else:
            notification_message = f"❌ **Katabump 续期任务失败**\n\n<b>错误:</b>\n<code>{final_status_message}</code>\n\n<b>调试报告:</b>\n{report_url}"
            
        reporter.send_telegram_notification(notification_message)
        
        if page: page.quit()
        
        if "成功" not in final_status_message and "未到期" not in final_status_message and "suspend" not in final_status_message.lower():
            exit(1)

if __name__ == "__main__":
    job()
