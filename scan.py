import os
import sys
import asyncio
import threading
import re
import time
import random
import string
from datetime import datetime
from urllib.parse import urlparse
import aiohttp
import requests
from dotenv import load_dotenv, set_key
import customtkinter as ctk
from tkinter import messagebox
from playwright.async_api import async_playwright

# Configure Playwright Browser Path for Standalone EXE
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ or not os.environ["PLAYWRIGHT_BROWSERS_PATH"]:
    local_appdata = os.environ.get("LOCALAPPDATA", os.path.expandvars(r"%LOCALAPPDATA%"))
    ms_pw = os.path.join(local_appdata, "ms-playwright")
    if os.path.exists(ms_pw):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = ms_pw

# Setup base directory for .env and resources
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(BASE_DIR, relative_path)

ENV_PATH = os.path.join(BASE_DIR, '.env')
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

# Fixed Hardcoded Tokens & Credentials
DEFAULT_LINK999_API_TOKEN = "c4aa527702c6a8fe6cb1d1427bfbb10dbebfddc2"
DEFAULT_AUTHORIZED_USER_ID = "your_telegram_user_id_here"

# Step Campaign Types
STEP_CAMPAIGNS = {
    "step2": 3,  # Google Search 3 Step
    "step3": 4,  # Google Search 2 Step
    "step4": 5   # Google Search 4 Step
}

# Link999 Domain Configuration
LINK999_DOMAINS = {
    "app": "https://link999.app/api",
    "win": "https://link999.win/api"
}
DEFAULT_LINK999_DOMAIN = "app"


class GUILink999Shortener:
    def __init__(self, api_token, domain=None):
        self.api_token = api_token
        self.domain = (domain or DEFAULT_LINK999_DOMAIN).strip().lower()
        if self.domain not in LINK999_DOMAINS:
            self.domain = DEFAULT_LINK999_DOMAIN
        self.api_url = LINK999_DOMAINS[self.domain]

    async def shorten_url(self, long_url, alias=None, campaign_type=3, max_retries=3):
        params = {
            "api": self.api_token,
            "url": long_url,
            "type": campaign_type
        }
        if alias:
            params["alias"] = alias

        # Build API URL
        from urllib.parse import urlencode
        api_url = f"{self.api_url}?{urlencode(params)}"

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, timeout=10) as response:
                        text = await response.text()
                        if response.status != 200:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(2 ** attempt)
                                continue
                            return None

                        try:
                            result = await response.json()
                            if result.get("status") == "success":
                                short_url = result.get("shortenedUrl")
                                return short_url
                            else:
                                # Log error from API
                                error_msg = result.get("message", "Unknown error")
                                print(f"API Error: {error_msg}")
                        except:
                            if text.strip():
                                return text.strip()
            except Exception as e:
                print(f"Shorten URL Error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
        return None

    def generate_random_url(self):
        domains = ["example.com", "test.com", "demo.org", "sample.net"]
        domain = random.choice(domains)
        random_path = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        return f"https://{domain}/{random_path}"

    def generate_random_alias(self, length=8):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))



# -------------------------------------------------------------
# TELEGRAM SENDER
# -------------------------------------------------------------
class GUITelegramSender:
    def __init__(self, bot_token="", chat_id="", logger=None):
        self.bot_token = (bot_token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else ""
        self.last_message_id = None
        self.log = logger or (lambda msg, lvl="info": None)

    async def send_message(self, text):
        if not self.bot_token or not self.chat_id:
            return None

        # Xóa tin nhắn cũ trước khi gửi tin nhắn mới để giữ kênh luôn sạch
        if self.last_message_id:
            await self.delete_message(self.last_message_id)
            self.last_message_id = None

        url = f"{self.base_url}/sendMessage"
        params = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    result = await response.json()
                    if result.get("ok"):
                        msg_id = result.get("result", {}).get("message_id")
                        self.last_message_id = msg_id
                        self.log(f"✓ Đã gửi thông báo Telegram thành công [Message ID: #{msg_id}]: {text}", "success")
                        return msg_id
                    else:
                        err_desc = result.get("description", "Unknown error")
                        self.log(f"✗ Lỗi gửi Telegram: {err_desc}", "error")
                        return None
        except Exception as e:
            self.log(f"✗ Lỗi kết nối Telegram: {e}", "error")
            return None

    async def delete_message(self, message_id):
        if not self.bot_token or not self.chat_id or not message_id:
            return False
        url = f"{self.base_url}/deleteMessage"
        params = {
            "chat_id": self.chat_id,
            "message_id": message_id
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    result = await response.json()
                    if result.get("ok"):
                        self.log(f"🗑 Đã xóa tin nhắn Telegram cũ [Message ID: #{message_id}] thành công", "info")
                        return True
                    else:
                        err_desc = result.get("description", "Unknown error")
                        self.log(f"⚠️ Xóa tin nhắn Telegram cũ [Message ID: #{message_id}] không thành công ({err_desc})", "warning")
                        return False
        except Exception as e:
            self.log(f"⚠️ Lỗi khi xóa tin nhắn Telegram cũ [Message ID: #{message_id}]: {e}", "warning")
            return False


# -------------------------------------------------------------
# KIOTPROXY MANAGER
# -------------------------------------------------------------
class KiotProxyManager:
    def __init__(self, key="", region="random", logger=None):
        self.key = key.strip()
        self.region = region or "random"
        self.log = logger or (lambda msg, lvl="info": None)
        
        self.current_ip = ""
        self.current_http = ""
        self.current_location = ""
        self.expiration_at = None
        self.cooldown_until = 0
        self.is_connected = False
        self.last_error = ""

    def get_new_proxy(self):
        if not self.key:
            self.log("Lỗi: Chưa nhập KiotProxy Key!", "error")
            return False, "Chưa nhập KiotProxy Key"
        
        now = time.time()
        if now < self.cooldown_until:
            rem = int(self.cooldown_until - now)
            return False, f"Vui lòng đợi {rem}s nữa để đổi proxy"

        url = f"https://api.kiotproxy.com/api/v1/proxies/new?key={self.key}&region={self.region}"
        try:
            res = requests.get(url, timeout=12)
            data = res.json()
            if data.get("success"):
                d = data.get("data", {})
                self.current_http = d.get("http", "")
                self.current_location = d.get("location", "")
                self.current_ip = self.current_http.split(":")[0] if self.current_http else ""
                
                exp_val = d.get("expirationAt")
                if exp_val:
                    try:
                        if isinstance(exp_val, (int, float)):
                            ts = exp_val / 1000.0 if exp_val > 1e11 else float(exp_val)
                            self.expiration_at = datetime.fromtimestamp(ts)
                        elif isinstance(exp_val, str):
                            if exp_val.isdigit():
                                num = float(exp_val)
                                ts = num / 1000.0 if num > 1e11 else num
                                self.expiration_at = datetime.fromtimestamp(ts)
                            else:
                                clean_exp = exp_val.replace("Z", "+00:00")
                                self.expiration_at = datetime.fromisoformat(clean_exp)
                    except Exception:
                        self.expiration_at = None
                
                self.is_connected = True
                
                # Cooldown handling
                next_req = d.get("nextRequestAt")
                if next_req and isinstance(next_req, (int, float)):
                    self.cooldown_until = next_req / 1000.0 if next_req > 1e11 else float(next_req)
                else:
                    ttc = d.get("ttc") or d.get("packageTtc") or 120
                    self.cooldown_until = time.time() + float(ttc)
                
                self.log(f"✓ KiotProxy thành công! IP: {self.current_http} (Vùng: {self.current_location})", "success")
                return True, self.current_http
            else:
                msg = data.get("message") or data.get("error") or "Không lấy được proxy"
                import re
                match = re.search(r'(\d+)\s*giây', msg)
                if match:
                    cd = int(match.group(1))
                    self.cooldown_until = time.time() + cd
                else:
                    self.cooldown_until = time.time() + 10
                self.last_error = msg
                self.log(f"✗ KiotProxy: {msg}", "warning")
                return False, msg
        except Exception as e:
            self.last_error = str(e)
            self.log(f"✗ Lỗi kết nối KiotProxy: {e}", "error")
            return False, str(e)

    def exit_proxy(self):
        if not self.key:
            return False, "Chưa nhập Key"
        url = f"https://api.kiotproxy.com/api/v1/proxies/out?key={self.key}"
        try:
            res = requests.get(url, timeout=10)
            data = res.json()
            self.is_connected = False
            self.current_http = ""
            self.current_ip = ""
            self.current_location = ""
            self.expiration_at = None
            self.cooldown_until = 0
            if data.get("success"):
                self.log("✓ Đã Exit Key proxy thành công trên KiotProxy!", "success")
                return True, "Đã Exit Key thành công"
            else:
                msg = data.get("message") or "Exit thất bại"
                self.log(f"KiotProxy Exit: {msg}", "warning")
                return True, msg
        except Exception as e:
            self.is_connected = False
            self.current_http = ""
            self.log(f"Lỗi khi Exit KiotProxy: {e}", "warning")
            return False, str(e)

    def get_remaining_seconds(self):
        if not self.expiration_at:
            return None
        from datetime import timezone
        try:
            if self.expiration_at.tzinfo is not None:
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            diff = (self.expiration_at - now).total_seconds()
            return max(0, int(diff))
        except Exception:
            return None

    def get_cooldown_remaining(self):
        now = time.time()
        if now < self.cooldown_until:
            return max(0, int(self.cooldown_until - now))
        return 0


class GUITaskScanner:
    def __init__(self, shortener, logger_callback, stats_callback, kiot_mgr=None, telegram_sender=None, log_status_callback=None):
        self.shortener = shortener
        self.log = logger_callback
        self.log_status = log_status_callback or (lambda key, message: self.log(message))
        self.update_stats = stats_callback
        self.kiot_mgr = kiot_mgr
        self.telegram_sender = telegram_sender
        self.use_telegram = True
        self.use_kiotproxy = False
        
        self.task_ids = set()
        self.browser = None
        self.playwright = None
        self.semaphore = asyncio.Semaphore(5)
        
        self.step2_enabled = False
        self.step3_enabled = False
        self.step4_enabled = True
        
        self.paused = False
        self.running = False
        self.refresh_interval = int(os.getenv('REFRESH_INTERVAL', 60))
        self.generated_links_count = int(os.getenv('GENERATED_LINKS', 10))
        self.concurrent_scan = int(os.getenv('CONCURRENT_SCAN_PER_LINK', 5))
        self.next_scan_time = None
        self.total_links_generated = 0
        self.total_tasks_found = 0
        self.cycle_count = 0
        self.latest_tasks_text = ""

    async def init_browser(self):
        if self.browser is None:
            self.playwright = await async_playwright().start()
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-features=site-per-process",
            ]
            
            # 1. Try launching standard Chromium
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    args=browser_args
                )
                self.log("Trình duyệt Chromium đã khởi động thành công.", "success")
                return
            except Exception:
                self.log("Đang tìm kiếm Chromium đã cài trên máy...", "info")
            
            # 2. Try launching with explicit executable_path from %LOCALAPPDATA%\ms-playwright
            try:
                local_appdata = os.environ.get("LOCALAPPDATA", os.path.expandvars(r"%LOCALAPPDATA%"))
                import glob
                chrome_exes = glob.glob(os.path.join(local_appdata, "ms-playwright", "chromium-*", "chrome-win64", "chrome.exe"))
                if chrome_exes and os.path.exists(chrome_exes[0]):
                    self.browser = await self.playwright.chromium.launch(
                        headless=True,
                        executable_path=chrome_exes[0],
                        args=browser_args
                    )
                    self.log("Đã mở Playwright Chromium thành công!", "success")
                    return
            except Exception:
                pass

            # 3. Fallback to system Chrome / Edge
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=True,
                    channel="chrome",
                    args=browser_args
                )
                self.log("Đã kết nối thành công với Google Chrome!", "success")
                return
            except Exception:
                try:
                    self.browser = await self.playwright.chromium.launch(
                        headless=True,
                        channel="msedge",
                        args=browser_args
                    )
                    self.log("Đã kết nối thành công với Microsoft Edge!", "success")
                    return
                except Exception as e3:
                    self.log(f"Lỗi: Không tìm thấy trình duyệt để quét ({e3})", "error")
                    raise e3

    async def close_browser(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        self.log("Đã đóng trình duyệt Playwright.", "info")

    async def scan_link(self, short_url, max_retries=3, run_label=""):
        def st(text):
            self.log_status(short_url, f"{short_url.split('//')[-1]} | {run_label}{text}")

        async with self.semaphore:
            for attempt in range(max_retries):
                if not self.running:
                    return None
                page = None
                context = None
                try:
                    if not self.browser or not self.browser.is_connected():
                        await self.close_browser()
                        await self.init_browser()
                    
                    # Configure proxy if KiotProxy enabled
                    proxy_cfg = None
                    if self.use_kiotproxy and self.kiot_mgr and self.kiot_mgr.current_http:
                        parts = self.kiot_mgr.current_http.split(":")
                        if len(parts) >= 4:
                            proxy_cfg = {
                                "server": f"http://{parts[0]}:{parts[1]}",
                                "username": parts[2],
                                "password": parts[3]
                            }
                        elif len(parts) >= 2:
                            proxy_cfg = {"server": f"http://{parts[0]}:{parts[1]}"}
                        else:
                            proxy_cfg = {"server": f"http://{self.kiot_mgr.current_http}"}

                    context = await self.browser.new_context(
                        proxy=proxy_cfg,
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    t0 = time.time()
                    hops = []
                    page.on("response", lambda r: hops.append((r.status, r.url)) if r.request.is_navigation_request() else None)
                    st(f"🌐 Đang mở link (lần {attempt+1}/{max_retries})...")
                    resp = await page.goto(short_url, timeout=30000, wait_until="domcontentloaded")
                    st(f"Đang chuyển hướng. .. ... . .. ...")
                    await asyncio.sleep(2)

                    final_url = page.url
                    elapsed = time.time() - t0
                    redirected = final_url.rstrip('/') != short_url.rstrip('/')
                    if redirected:
                        st(f"✔ Đã chuyển hướng → {urlparse(final_url).netloc} ({len(hops)} bước, {elapsed:.1f}s)")
                    else:
                        st(f"❌ CHƯA chuyển hướng ({len(hops)} bước, {elapsed:.1f}s)")
                    await page.close()
                    await context.close()
                    page = None
                    context = None

                    if "linkhuongdan.online" in final_url:
                        parsed = urlparse(final_url)
                        path = parsed.path.strip('/')
                        if '/' in path:
                            path = path.split('/')[0]
                        # Keep the full task ID including suffixes like -2, -3, -4
                        # Example: 236-2 should remain 236-2, not 236
                        if path and len(path) <= 15:
                            st(f"✅ Task ID: {path} ({urlparse(final_url).netloc}, {elapsed:.1f}s)")
                            return path
                        else:
                            st(f"⚠️ Path không hợp lệ: {path}")
                    else:
                        if redirected:
                            st(f"⚠️ Chuyển hướng nhưng KHÔNG phải linkhuongdan.online → {urlparse(final_url).netloc}")
                    return None
                except Exception as e:
                    if page:
                        try:
                            await page.close()
                        except:
                            pass
                    if context:
                        try:
                            await context.close()
                        except:
                            pass
                    if attempt < max_retries - 1:
                        st(f"⚠️ Lỗi, thử lại {attempt+1}/{max_retries}: {str(e)[:60]}")
                        await asyncio.sleep(1.5)
                        continue
                    st(f"✗ Quét thất bại: {str(e)[:60]}")
                    return None

    async def scan_link_concurrent(self, short_url):
        task_ids = set()
        for _ in range(self.concurrent_scan):
            if not self.running:
                break
            res = await self.scan_link(short_url, run_label=f"[{_+1}/{self.concurrent_scan}] ")
            if res:
                task_ids.add(res)
        return task_ids

    async def scan_cycle(self):
        self.task_ids.clear()
        self.cycle_count += 1
        
        # Check & rotate KiotProxy if enabled
        if self.use_kiotproxy and self.kiot_mgr:
            rem_sec = self.kiot_mgr.get_remaining_seconds()
            cd_rem = self.kiot_mgr.get_cooldown_remaining()
            if not self.kiot_mgr.is_connected or (rem_sec is not None and rem_sec <= 60) or cd_rem == 0:
                self.log("Đang lấy/xoay IP KiotProxy mới...", "info")
                self.kiot_mgr.get_new_proxy()
        
        enabled_steps = []
        if self.step2_enabled:
            enabled_steps.append("step2")
        if self.step3_enabled:
            enabled_steps.append("step3")
        if self.step4_enabled:
            enabled_steps.append("step4")
        
        if not enabled_steps:
            self.log("Cảnh báo: Không có Step nào được bật. Bỏ qua chu kỳ quét!", "warning")
            return set()
        
        self.log(f"--- BẮT ĐẦU CHU KỲ QUÉT #{self.cycle_count} (Steps: {', '.join(enabled_steps)}) ---", "info")
        
        all_links = []
        for i in range(self.generated_links_count):
            if not self.running:
                self.log("⏹ Đã dừng khi đang tạo link.", "warning")
                return set()
            step = enabled_steps[i % len(enabled_steps)]
            random_url = self.shortener.generate_random_url()
            random_alias = self.shortener.generate_random_alias()
            short_url = await self.shortener.shorten_url(
                long_url=random_url,
                alias=random_alias,
                campaign_type=STEP_CAMPAIGNS[step]
            )
            if short_url:
                self.log_status("gen", f"✓ Link {i+1}/{self.generated_links_count} ({step}): {short_url}")
                all_links.append(short_url)
                self.total_links_generated += 1
            else:
                self.log_status("gen", f"✗ Tạo link thất bại {i+1}/{self.generated_links_count} ({step})")
        
        self.update_stats()
        
        if not all_links:
            self.log("Không có link nào được tạo, chuyển sang lần kế tiếp", "warning")
            return set()

        if not self.running:
            self.log("⏹ Đã dừng trước khi bắt đầu quét.", "warning")
            return set()

        self.log(f"\n{'='*60}", "info")
        self.log(f"🔍 BẮT ĐẦU QUÉT {len(all_links)} LINKS BẰNG BROWSER", "info")
        self.log(f"{'='*60}", "info")
        scan_tasks = [self.scan_link_concurrent(link) for link in all_links]
        results = await asyncio.gather(*scan_tasks, return_exceptions=True)
        
        for r in results:
            if isinstance(r, set):
                self.task_ids.update(r)
        
        count = len(self.task_ids)
        self.total_tasks_found += count
        if self.task_ids:
            shuffled_ids = list(self.task_ids)
            random.shuffle(shuffled_ids)
            self.latest_tasks_text = "; ".join(shuffled_ids)
            self.log(f"🎯 KẾT QUẢ: Tìm thấy {count} mã Task ID: {self.latest_tasks_text}", "success")
            self.log(f"{'='*60}", "info")
            self.log(f"📊 TỔNG KẾT QUÉT:", "info")
            self.log(f"   - Links đã quét: {len(all_links)}", "info")
            self.log(f"   - Tổng lần quét: {len(all_links) * self.concurrent_scan}", "info")
            self.log(f"   - Task IDs tìm thấy: {count}", "info")
            self.log(f"   - Danh sách task IDs: {self.task_ids}", "info")
            self.log(f"{'='*60}\n", "info")
            if self.use_telegram and self.telegram_sender and self.telegram_sender.bot_token and self.telegram_sender.chat_id:
                await self.telegram_sender.send_message(f"<u>{count} Mã</u>: {self.latest_tasks_text}")
        else:
            self.latest_tasks_text = ""
            self.log("⚠️ Không tìm thấy mã nào trong chu kỳ này.", "warning")
            self.log(f"{'='*60}\n", "info")
            if self.use_telegram and self.telegram_sender and self.telegram_sender.bot_token and self.telegram_sender.chat_id:
                await self.telegram_sender.send_message("HẾT MÃ")

        self.update_stats()
        return self.task_ids

    async def run_scan_loop(self):
        self.running = True
        self.log("Vòng lặp Scanner đã bắt đầu hoạt động.", "info")
        
        while self.running:
            if self.paused:
                await asyncio.sleep(2)
                continue
            
            try:
                await self.scan_cycle()
                self.task_ids.clear()
                
                self.next_scan_time = time.time() + self.refresh_interval
                self.log(f"Đợt quét tiếp theo sau {self.refresh_interval} giây...", "info")
                
                start_wait = time.time()
                while time.time() - start_wait < self.refresh_interval:
                    if not self.running or self.paused:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.log(f"Lỗi trong vòng lặp quét: {e}", "error")
                await asyncio.sleep(5)


# -------------------------------------------------------------
# MAIN MODERN COMPACT DESKTOP GUI APPLICATION
# -------------------------------------------------------------
class BotPhuApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Appearance Settings
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("⚡ H.Nam & Phú v2.0")
        
        # Position Window dynamically near Cursor (where user double clicks)
        app_w = 640
        app_h = 440
        self.minsize(560, 380)

        try:
            cur_x = self.winfo_pointerx()
            cur_y = self.winfo_pointery()
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()

            pos_x = max(20, min(cur_x - app_w // 2, screen_w - app_w - 20))
            pos_y = max(20, min(cur_y - app_h // 2, screen_h - app_h - 50))
            self.geometry(f"{app_w}x{app_h}+{pos_x}+{pos_y}")
        except Exception:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            pos_x = max(0, (screen_w - app_w) // 2)
            pos_y = max(0, (screen_h - app_h) // 2)
            self.geometry(f"{app_w}x{app_h}+{pos_x}+{pos_y}")

        # Set App ID for Windows Taskbar Icon
        try:
            import ctypes
            myappid = 'link999.botphu.gui.app.v2'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # Set App Icon (Title bar & Taskbar)
        ico_path = get_resource_path("icon.ico")
        if not os.path.exists(ico_path):
            ico_path = os.path.join(BASE_DIR, "icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
                self.wm_iconbitmap(ico_path)
            except Exception:
                pass

        # Bot State Variables
        self.is_running = False
        self.is_paused = False
        self.bot_thread = None
        self.loop = None
        self.scanner = None
        self.api_visible = False
        self.kiot_mgr = KiotProxyManager(logger=self.log)
        self.link999_domain = os.getenv("LINK999_DOMAIN", DEFAULT_LINK999_DOMAIN).strip().lower()
        if self.link999_domain not in LINK999_DOMAINS:
            self.link999_domain = DEFAULT_LINK999_DOMAIN

        # Build User Interface
        self.create_layout()
        self.load_env_to_inputs()
        
        # Start Countdown Timer Update
        self.update_timer()

    def create_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Left Sidebar (Reduced Width by 2x: 65px)
        self.sidebar_frame = ctk.CTkFrame(self, width=65, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Link999", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.logo_label.grid(row=0, column=0, padx=2, pady=(12, 1))

        self.sub_logo = ctk.CTkLabel(
            self.sidebar_frame, 
            text="v2.0", 
            font=ctk.CTkFont(size=8), 
            text_color="gray"
        )
        self.sub_logo.grid(row=1, column=0, padx=2, pady=(0, 8))

        # Navigation Buttons (Compact icons & text)
        self.btn_nav_dashboard = ctk.CTkButton(
            self.sidebar_frame, text="📊", 
            width=50, height=32, font=ctk.CTkFont(size=16),
            command=lambda: self.switch_tab("dashboard")
        )
        self.btn_nav_dashboard.grid(row=2, column=0, padx=6, pady=4)

        self.btn_nav_settings = ctk.CTkButton(
            self.sidebar_frame, text="⚙️", 
            width=50, height=32, font=ctk.CTkFont(size=16), fg_color="transparent",
            hover_color=("#3B8ED0", "#1F6AA5"),
            command=lambda: self.switch_tab("settings")
        )
        self.btn_nav_settings.grid(row=3, column=0, padx=6, pady=4)

        self.btn_nav_logs = ctk.CTkButton(
            self.sidebar_frame, text="📜", 
            width=50, height=32, font=ctk.CTkFont(size=16), fg_color="transparent",
            hover_color=("#3B8ED0", "#1F6AA5"),
            command=lambda: self.switch_tab("logs")
        )
        self.btn_nav_logs.grid(row=4, column=0, padx=6, pady=4)

        # Status badge in sidebar bottom
        self.status_box = ctk.CTkFrame(self.sidebar_frame, corner_radius=6, fg_color="#1e2229")
        self.status_box.grid(row=7, column=0, padx=4, pady=8, sticky="ew")
        
        self.lbl_status_badge = ctk.CTkLabel(
            self.status_box, text="● DỪNG", 
            font=ctk.CTkFont(size=8, weight="bold"), 
            text_color="#f44336"
        )
        self.lbl_status_badge.pack(padx=2, pady=4)

        # Main Content Container
        self.main_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        # Build 3 Views
        self.tab_dashboard = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.tab_settings = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.tab_logs = ctk.CTkFrame(self.main_container, fg_color="transparent")

        self.build_dashboard_view()
        self.build_settings_view()
        self.build_logs_view()

        self.switch_tab("dashboard")

    def switch_tab(self, tab_name):
        self.btn_nav_dashboard.configure(fg_color="#1F6AA5" if tab_name == "dashboard" else "transparent")
        self.btn_nav_settings.configure(fg_color="#1F6AA5" if tab_name == "settings" else "transparent")
        self.btn_nav_logs.configure(fg_color="#1F6AA5" if tab_name == "logs" else "transparent")

        self.tab_dashboard.grid_forget()
        self.tab_settings.grid_forget()
        self.tab_logs.grid_forget()

        if tab_name == "dashboard":
            self.tab_dashboard.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "settings":
            self.tab_settings.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "logs":
            self.tab_logs.grid(row=0, column=0, sticky="nsew")

    # ---------------- DASHBOARD VIEW ----------------
    def build_dashboard_view(self):
        self.tab_dashboard.grid_columnconfigure((0, 1), weight=1)

        # 2 Metric Cards (Link & Timer) - 2x Font Sizes
        self.card_links = self.create_metric_card(self.tab_dashboard, "🔗 TỔNG LINK", "0", 0, 0, "#2b5c8f")
        self.card_timer = self.create_metric_card(self.tab_dashboard, "⏳ KẾ TIẾP", "--", 0, 1, "#d84315")

        # Control Panel Frame (2 Buttons: Start & Stop) - 2x Font Sizes
        control_frame = ctk.CTkFrame(self.tab_dashboard, corner_radius=8)
        control_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 6), padx=2)
        control_frame.grid_columnconfigure((0, 1), weight=1)

        self.btn_start = ctk.CTkButton(
            control_frame, text="▶ BẮT ĐẦU CHẠY", 
            height=36, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=self.start_bot
        )
        self.btn_start.grid(row=0, column=0, padx=6, pady=6, sticky="ew")

        self.btn_stop = ctk.CTkButton(
            control_frame, text="⏹ DỪNG BOT", 
            height=36, font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c62828", hover_color="#8e0000",
            state="disabled",
            command=self.stop_bot
        )
        self.btn_stop.grid(row=0, column=1, padx=6, pady=6, sticky="ew")

        # Proxy Key Input & Action Panel on Dashboard (Replaces Step switches)
        proxy_ctrl_frame = ctk.CTkFrame(self.tab_dashboard, corner_radius=8)
        proxy_ctrl_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=2)
        proxy_ctrl_frame.grid_columnconfigure(0, weight=1)
        proxy_ctrl_frame.grid_columnconfigure((1, 2), weight=0)

        # Input + Eye button container on Dashboard
        dash_key_box = ctk.CTkFrame(proxy_ctrl_frame, fg_color="transparent")
        dash_key_box.grid(row=0, column=0, padx=(6, 2), pady=4, sticky="ew")
        dash_key_box.grid_columnconfigure(0, weight=1)
        dash_key_box.grid_columnconfigure(1, weight=0)

        self.dash_key_visible = True
        self.entry_dash_proxy_key = ctk.CTkEntry(
            dash_key_box, 
            height=34, 
            font=ctk.CTkFont(size=12),
            placeholder_text="Nhập KiotProxy Key..."
        )
        self.entry_dash_proxy_key.grid(row=0, column=0, sticky="ew")

        self.btn_dash_toggle_key = ctk.CTkButton(
            dash_key_box,
            text="👁️‍🗨️",
            width=30,
            height=34,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color="#37474f",
            command=self.toggle_dash_key_visibility
        )
        self.btn_dash_toggle_key.grid(row=0, column=1, padx=(2, 0))

        self.btn_dash_proxy_action = ctk.CTkButton(
            proxy_ctrl_frame,
            text="🔗 KẾT NỐI",
            height=34,
            width=115,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0288d1",
            hover_color="#01579b",
            command=self.dashboard_proxy_action
        )
        self.btn_dash_proxy_action.grid(row=0, column=1, padx=2, pady=4)

        self.btn_dash_proxy_exit = ctk.CTkButton(
            proxy_ctrl_frame,
            text="🚪 EXIT",
            height=34,
            width=65,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e65100",
            hover_color="#bf360c",
            command=self.manual_exit_proxy
        )
        self.btn_dash_proxy_exit.grid(row=0, column=2, padx=(2, 6), pady=4)

        # Proxy Status Box on Dashboard (Styled like extension cryptobig_nokey)
        self.proxy_info_card = ctk.CTkFrame(
            self.tab_dashboard, corner_radius=8,
            fg_color="#0e1726", border_width=1, border_color="#00e5ff"
        )
        self.proxy_info_card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 6), padx=2)
        self.proxy_info_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.lbl_proxy_ip = ctk.CTkLabel(
            self.proxy_info_card,
            text="🌐 IP: --",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#00e5ff"
        )
        self.lbl_proxy_ip.grid(row=0, column=0, padx=8, pady=5, sticky="w")

        self.lbl_proxy_region = ctk.CTkLabel(
            self.proxy_info_card,
            text="📍 Vùng: --",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ff5252"
        )
        self.lbl_proxy_region.grid(row=0, column=1, padx=4, pady=5, sticky="ew")

        self.lbl_proxy_time = ctk.CTkLabel(
            self.proxy_info_card,
            text="⏳ Hạn: --",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#ffb300"
        )
        self.lbl_proxy_time.grid(row=0, column=2, padx=8, pady=5, sticky="e")

        # 3 Quick Logs (Real-time output stream)
        log_frame = ctk.CTkFrame(self.tab_dashboard, corner_radius=8)
        log_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 2), padx=2)
        self.tab_dashboard.grid_rowconfigure(4, weight=1)

        tasks_box = ctk.CTkFrame(log_frame, fg_color="transparent")
        tasks_box.pack(fill="x", padx=6, pady=(4, 2))

        self.btn_copy_tasks = ctk.CTkButton(
            tasks_box,
            text="📋",
            width=32,
            height=26,
            font=ctk.CTkFont(size=13),
            fg_color="#1F6AA5",
            hover_color="#144870",
            command=self.copy_latest_tasks
        )
        self.btn_copy_tasks.pack(side="left", padx=(0, 6))

        self.lbl_latest_tasks = ctk.CTkLabel(
            tasks_box,
            text="Mã: --",
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
            text_color="#00e5ff",
            anchor="w"
        )
        self.lbl_latest_tasks.pack(side="left", fill="x", expand=True)

        self.lbl_tg_msg_id = ctk.CTkLabel(
            tasks_box,
            text="Tele ID: --",
            font=ctk.CTkFont(family="Consolas", size=12, weight="bold"),
            text_color="#ffb300",
            anchor="e"
        )
        self.lbl_tg_msg_id.pack(side="right", padx=(4, 0))

        self.txt_quick_log = ctk.CTkTextbox(
            log_frame, 
            height=140, 
            font=ctk.CTkFont(family="Consolas", size=13),
            activate_scrollbars=True
        )
        self.txt_quick_log.pack(fill="both", expand=True, padx=6, pady=(0, 6))

    def copy_latest_tasks(self):
        tasks_str = ""
        if self.scanner and hasattr(self.scanner, 'latest_tasks_text') and self.scanner.latest_tasks_text:
            tasks_str = self.scanner.latest_tasks_text
        else:
            raw = self.lbl_latest_tasks.cget("text")
            if "Mã:" in raw:
                tasks_str = raw.replace("Mã:", "").strip()
                if tasks_str == "--":
                    tasks_str = ""
            else:
                tasks_str = raw.strip()
        
        if tasks_str:
            self.clipboard_clear()
            self.clipboard_append(tasks_str)
            self.log(f"📋 Đã sao chép danh sách mã: {tasks_str}", "info")
            self.btn_copy_tasks.configure(text="✓", fg_color="#2e7d32")
            self.after(1500, lambda: self.btn_copy_tasks.configure(text="📋", fg_color="#1F6AA5"))
        else:
            self.log("⚠️ Chưa có mã nào để sao chép.", "warning")

    def create_metric_card(self, parent, title, value, row, col, color):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color=color)
        card.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
        
        lbl_title = ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color="#cfd8dc")
        lbl_title.pack(padx=8, pady=(4, 1), anchor="w")
        
        lbl_value = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold"), text_color="#ffffff")
        lbl_value.pack(padx=8, pady=(0, 4), anchor="w")
        
        return lbl_value

    def toggle_dash_key_visibility(self):
        self.dash_key_visible = not self.dash_key_visible
        if self.dash_key_visible:
            self.entry_dash_proxy_key.configure(show="")
            self.btn_dash_toggle_key.configure(text="👁️‍🗨️")
        else:
            self.entry_dash_proxy_key.configure(show="*")
            self.btn_dash_toggle_key.configure(text="👁")

    def toggle_settings_key_visibility(self):
        self.settings_key_visible = not self.settings_key_visible
        if self.settings_key_visible:
            self.entry_kiot_key.configure(show="")
            self.btn_settings_toggle_key.configure(text="👁️‍🗨️")
        else:
            self.entry_kiot_key.configure(show="*")
            self.btn_settings_toggle_key.configure(text="👁")

    def toggle_domain_switch(self):
        is_win = bool(self.switch_domain.get())
        self.link999_domain = "win" if is_win else "app"
        self.switch_domain.configure(text="Win" if is_win else "App")
        if self.scanner and hasattr(self.scanner, "shortener") and self.scanner.shortener:
            self.scanner.shortener.domain = self.link999_domain
            self.scanner.shortener.api_url = LINK999_DOMAINS[self.link999_domain]
        self.log(f"🔀 Đã chuyển domain Link999 sang: {self.link999_domain} ({LINK999_DOMAINS[self.link999_domain]})", "info")

    # ---------------- SETTINGS VIEW ----------------
    def build_settings_view(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)
        self.tab_settings.grid_rowconfigure(0, weight=1)

        scroll_settings = ctk.CTkScrollableFrame(self.tab_settings, corner_radius=8)
        scroll_settings.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        scroll_settings.grid_columnconfigure((0, 1), weight=1)

        # Section 1: Scanning Config
        sec1 = ctk.CTkLabel(
            scroll_settings, 
            text="⚙️ CẤU HÌNH QUÉT LINK", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        sec1.grid(row=0, column=0, columnspan=2, padx=8, pady=(4, 4), sticky="w")

        lbl_gen = ctk.CTkLabel(scroll_settings, text="Số link mỗi đợt:", font=ctk.CTkFont(size=12))
        lbl_gen.grid(row=1, column=0, padx=8, pady=1, sticky="w")
        self.entry_gen_links = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="10")
        self.entry_gen_links.grid(row=2, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")

        lbl_con = ctk.CTkLabel(scroll_settings, text="Số luồng scan/link:", font=ctk.CTkFont(size=12))
        lbl_con.grid(row=1, column=1, padx=8, pady=1, sticky="w")
        self.entry_concurrent = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="5")
        self.entry_concurrent.grid(row=2, column=1, padx=(4, 8), pady=(0, 6), sticky="ew")

        lbl_ref = ctk.CTkLabel(scroll_settings, text="Thời gian lặp lại (giây):", font=ctk.CTkFont(size=12))
        lbl_ref.grid(row=3, column=0, padx=8, pady=1, sticky="w")
        self.entry_refresh = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="60")
        self.entry_refresh.grid(row=4, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")

        lbl_port = ctk.CTkLabel(scroll_settings, text="Cổng Flask Health Check:", font=ctk.CTkFont(size=12))
        lbl_port.grid(row=3, column=1, padx=8, pady=1, sticky="w")
        self.entry_port = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="5000")
        self.entry_port.grid(row=4, column=1, padx=(4, 8), pady=(0, 6), sticky="ew")

        # Domain Switch (App / Win)
        lbl_domain = ctk.CTkLabel(scroll_settings, text="🔀 Link999:", font=ctk.CTkFont(size=12))
        lbl_domain.grid(row=5, column=0, padx=8, pady=1, sticky="w")
        self.switch_domain = ctk.CTkSwitch(
            scroll_settings, text="App",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_domain_switch
        )
        self.switch_domain.grid(row=5, column=1, padx=(4, 8), pady=1, sticky="w")

        # Section 2: KiotProxy Config
        sec2 = ctk.CTkLabel(
            scroll_settings, 
            text="🌐 CẤU HÌNH KIOTPROXY.VN", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        sec2.grid(row=6, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        self.switch_kiotproxy = ctk.CTkSwitch(
            scroll_settings, text="Bật KiotProxy",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.toggle_kiotproxy_switch
        )
        self.switch_kiotproxy.grid(row=7, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")

        lbl_kkey = ctk.CTkLabel(scroll_settings, text="KiotProxy Key:", font=ctk.CTkFont(size=12))
        lbl_kkey.grid(row=8, column=0, padx=8, pady=1, sticky="w")
        
        settings_key_box = ctk.CTkFrame(scroll_settings, fg_color="transparent")
        settings_key_box.grid(row=9, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")
        settings_key_box.grid_columnconfigure(0, weight=1)
        settings_key_box.grid_columnconfigure(1, weight=0)

        self.settings_key_visible = True
        self.entry_kiot_key = ctk.CTkEntry(settings_key_box, height=28, font=ctk.CTkFont(size=12), placeholder_text="Nhập API key KiotProxy")
        self.entry_kiot_key.grid(row=0, column=0, sticky="ew")

        self.btn_settings_toggle_key = ctk.CTkButton(
            settings_key_box, text="👁️‍🗨️", width=28, height=28, font=ctk.CTkFont(size=12),
            fg_color="transparent", hover_color="#37474f",
            command=self.toggle_settings_key_visibility
        )
        self.btn_settings_toggle_key.grid(row=0, column=1, padx=(2, 0))

        lbl_kreg = ctk.CTkLabel(scroll_settings, text="Vùng (Region):", font=ctk.CTkFont(size=12))
        lbl_kreg.grid(row=8, column=1, padx=8, pady=1, sticky="w")
        self.opt_kiot_region = ctk.CTkOptionMenu(
            scroll_settings, height=28, font=ctk.CTkFont(size=12),
            values=["random", "hanoi", "hochiminh"]
        )
        self.opt_kiot_region.grid(row=9, column=1, padx=(4, 8), pady=(0, 6), sticky="ew")

        # Proxy Action Buttons
        proxy_btn_box = ctk.CTkFrame(scroll_settings, fg_color="transparent")
        proxy_btn_box.grid(row=10, column=0, columnspan=2, padx=4, pady=(4, 8), sticky="ew")
        proxy_btn_box.grid_columnconfigure((0, 1), weight=1)

        self.btn_kiot_new = ctk.CTkButton(
            proxy_btn_box, text="🔄 ĐỔI PROXY (120s)",
            height=30, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#0288d1", hover_color="#01579b",
            command=self.manual_get_new_proxy
        )
        self.btn_kiot_new.grid(row=0, column=0, padx=4, pady=2, sticky="ew")

        self.btn_kiot_out = ctk.CTkButton(
            proxy_btn_box, text="🚪 EXIT KEY PROXY",
            height=30, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#e65100", hover_color="#bf360c",
            command=self.manual_exit_proxy
        )
        self.btn_kiot_out.grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        # Section 3: Telegram Config
        sec3 = ctk.CTkLabel(
            scroll_settings, 
            text="📢 CẤU HÌNH TELEGRAM CHANNEL", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        sec3.grid(row=11, column=0, columnspan=2, padx=8, pady=(10, 4), sticky="w")

        self.switch_telegram = ctk.CTkSwitch(
            scroll_settings, text="Bật gửi thông báo Telegram (Turn On/Off)",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.switch_telegram.grid(row=12, column=0, columnspan=2, padx=8, pady=(0, 6), sticky="w")

        lbl_tg_token = ctk.CTkLabel(scroll_settings, text="Telegram Bot Token:", font=ctk.CTkFont(size=12))
        lbl_tg_token.grid(row=13, column=0, padx=8, pady=1, sticky="w")
        self.entry_tg_token = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="Ví dụ: 123456789:ABCDefgh...")
        self.entry_tg_token.grid(row=14, column=0, padx=(8, 4), pady=(0, 6), sticky="ew")

        lbl_tg_chat = ctk.CTkLabel(scroll_settings, text="Telegram Chat ID / Channel ID:", font=ctk.CTkFont(size=12))
        lbl_tg_chat.grid(row=13, column=1, padx=8, pady=1, sticky="w")
        self.entry_tg_chat = ctk.CTkEntry(scroll_settings, height=28, font=ctk.CTkFont(size=12), placeholder_text="Ví dụ: -100xxxxxxxxxx")
        self.entry_tg_chat.grid(row=14, column=1, padx=(4, 8), pady=(0, 6), sticky="ew")

        # Action Button: Save only
        self.btn_save_env = ctk.CTkButton(
            scroll_settings, text="💾 LƯU CẤU HÌNH VÀO .ENV", 
            height=34, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2e7d32", hover_color="#1b5e20",
            command=lambda: self.save_settings_to_env(show_dialog=True)
        )
        self.btn_save_env.grid(row=15, column=0, columnspan=2, padx=12, pady=(10, 12), sticky="ew")

    # ---------------- LOGS VIEW ----------------
    def build_logs_view(self):
        self.tab_logs.grid_rowconfigure(1, weight=1)
        self.tab_logs.grid_columnconfigure(0, weight=1)

        log_tools = ctk.CTkFrame(self.tab_logs, corner_radius=8)
        log_tools.grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
        log_tools.grid_columnconfigure(0, weight=1)

        lbl_log_title = ctk.CTkLabel(
            log_tools, 
            text="📜 Chi Tiết Console Log:", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_log_title.grid(row=0, column=0, padx=8, pady=4, sticky="w")

        btn_copy = ctk.CTkButton(
            log_tools, text="📋 Sao Chép", width=90, height=28, font=ctk.CTkFont(size=12),
            command=self.copy_logs
        )
        btn_copy.grid(row=0, column=1, padx=4, pady=4)

        btn_clear = ctk.CTkButton(
            log_tools, text="🗑 Xóa", width=70, height=28, font=ctk.CTkFont(size=12),
            fg_color="#c62828", hover_color="#8e0000",
            command=self.clear_logs
        )
        btn_clear.grid(row=0, column=2, padx=(0, 8), pady=4)

        self.txt_full_log = ctk.CTkTextbox(
            self.tab_logs, 
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#101216", 
            text_color="#e0e0e0"
        )
        self.txt_full_log.grid(row=1, column=0, sticky="nsew", padx=2, pady=0)

    # ---------------- HELPER & LOGIC METHODS ----------------
    def load_env_to_inputs(self):
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH, override=True)

        self.entry_gen_links.delete(0, "end")
        self.entry_gen_links.insert(0, os.getenv("GENERATED_LINKS", "10"))

        self.entry_concurrent.delete(0, "end")
        self.entry_concurrent.insert(0, os.getenv("CONCURRENT_SCAN_PER_LINK", "5"))

        self.entry_refresh.delete(0, "end")
        self.entry_refresh.insert(0, os.getenv("REFRESH_INTERVAL", "60"))

        self.entry_port.delete(0, "end")
        self.entry_port.insert(0, os.getenv("PORT", "5000"))

        # KiotProxy env
        use_kp = os.getenv("USE_KIOTPROXY", "0").lower() in ("1", "true", "yes")
        if use_kp:
            self.switch_kiotproxy.select()
        else:
            self.switch_kiotproxy.deselect()

        kp_key = os.getenv("KIOTPROXY_KEY", "")
        self.entry_kiot_key.delete(0, "end")
        self.entry_kiot_key.insert(0, kp_key)
        self.entry_dash_proxy_key.delete(0, "end")
        self.entry_dash_proxy_key.insert(0, kp_key)
        self.kiot_mgr.key = kp_key

        kp_region = os.getenv("KIOTPROXY_REGION", "random")
        self.opt_kiot_region.set(kp_region)
        self.kiot_mgr.region = kp_region

        # Telegram env
        use_tg = os.getenv("USE_TELEGRAM", "1").lower() in ("1", "true", "yes")
        if use_tg:
            self.switch_telegram.select()
        else:
            self.switch_telegram.deselect()

        tg_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.entry_tg_token.delete(0, "end")
        self.entry_tg_token.insert(0, tg_token)

        tg_chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.entry_tg_chat.delete(0, "end")
        self.entry_tg_chat.insert(0, tg_chat)

        # Domain Link999
        domain = os.getenv("LINK999_DOMAIN", DEFAULT_LINK999_DOMAIN).strip().lower()
        if domain not in LINK999_DOMAINS:
            domain = DEFAULT_LINK999_DOMAIN
        self.link999_domain = domain
        if domain == "win":
            self.switch_domain.select()
            self.switch_domain.configure(text="Win")
        else:
            self.switch_domain.deselect()
            self.switch_domain.configure(text="App")

    def save_settings_to_env(self, show_dialog=False):
        try:
            if not os.path.exists(ENV_PATH):
                with open(ENV_PATH, 'w') as f:
                    pass

            set_key(ENV_PATH, "GENERATED_LINKS", self.entry_gen_links.get().strip())
            set_key(ENV_PATH, "CONCURRENT_SCAN_PER_LINK", self.entry_concurrent.get().strip())
            set_key(ENV_PATH, "REFRESH_INTERVAL", self.entry_refresh.get().strip())
            set_key(ENV_PATH, "PORT", self.entry_port.get().strip())

            # Sync KiotProxy key
            dash_key = self.entry_dash_proxy_key.get().strip()
            settings_key = self.entry_kiot_key.get().strip()
            final_key = dash_key if dash_key else settings_key

            is_use_kp = "1" if self.switch_kiotproxy.get() else "0"
            set_key(ENV_PATH, "USE_KIOTPROXY", is_use_kp)
            set_key(ENV_PATH, "KIOTPROXY_KEY", final_key)
            set_key(ENV_PATH, "KIOTPROXY_REGION", self.opt_kiot_region.get().strip())

            # Telegram env
            is_use_tg = "1" if self.switch_telegram.get() else "0"
            set_key(ENV_PATH, "USE_TELEGRAM", is_use_tg)
            final_tg_token = self.entry_tg_token.get().strip()
            final_tg_chat = self.entry_tg_chat.get().strip()
            set_key(ENV_PATH, "TELEGRAM_BOT_TOKEN", final_tg_token)
            set_key(ENV_PATH, "TELEGRAM_CHAT_ID", final_tg_chat)

            # Domain Link999
            set_key(ENV_PATH, "LINK999_DOMAIN", self.link999_domain)

            self.kiot_mgr.key = final_key
            self.kiot_mgr.region = self.opt_kiot_region.get().strip()

            load_dotenv(ENV_PATH, override=True)
            if show_dialog:
                self.log("Đã lưu cấu hình vào file .env.", "info")
                messagebox.showinfo("Thành Công", "Đã lưu cài đặt vào file .env!")
        except Exception as e:
            self.log(f"Lỗi khi lưu cấu hình vào .env: {e}", "error")
            if show_dialog:
                messagebox.showerror("Lỗi", f"Không thể lưu file .env: {e}")

    def toggle_kiotproxy_switch(self):
        is_on = bool(self.switch_kiotproxy.get())
        if self.scanner:
            self.scanner.use_kiotproxy = is_on
        self.update_proxy_ui()

    def dashboard_proxy_action(self):
        key = self.entry_dash_proxy_key.get().strip()
        if not key:
            key = self.entry_kiot_key.get().strip()
        if not key:
            self.log("⚠️ Vui lòng nhập KiotProxy Key trước khi kết nối!", "warning")
            return
        
        self.entry_kiot_key.delete(0, "end")
        self.entry_kiot_key.insert(0, key)
        self.manual_get_new_proxy()

    def manual_get_new_proxy(self):
        key = self.entry_dash_proxy_key.get().strip() or self.entry_kiot_key.get().strip()
        region = self.opt_kiot_region.get()
        if not key:
            self.log("⚠️ Vui lòng nhập KiotProxy Key trước khi kết nối!", "warning")
            return

        # Enable proxy switch automatically
        self.switch_kiotproxy.select()
        if self.scanner:
            self.scanner.use_kiotproxy = True

        self.entry_dash_proxy_key.delete(0, "end")
        self.entry_dash_proxy_key.insert(0, key)
        self.entry_kiot_key.delete(0, "end")
        self.entry_kiot_key.insert(0, key)

        self.kiot_mgr.key = key
        self.kiot_mgr.region = region
        self.save_settings_to_env()

        self.lbl_proxy_ip.configure(text="🌐 Đang kết nối...", text_color="#ffb300")
        self.lbl_proxy_region.configure(text="📍 Đang kiểm tra...", text_color="#ffb300")
        self.lbl_proxy_time.configure(text="⏳ --:--", text_color="#ffb300")
        self.btn_dash_proxy_action.configure(text="⏳ ĐANG KẾT NỐI...", fg_color="#37474f", state="disabled")
        self.btn_kiot_new.configure(text="🔄 ĐANG KẾT NỐI...", state="disabled")

        def _run():
            success, msg = self.kiot_mgr.get_new_proxy()
            self.after(0, self.update_proxy_ui)

        threading.Thread(target=_run, daemon=True).start()

    def manual_exit_proxy(self):
        key = self.entry_dash_proxy_key.get().strip() or self.entry_kiot_key.get().strip()
        if not key:
            key = self.kiot_mgr.key
        if not key:
            self.log("⚠️ Chưa có Key để Exit!", "warning")
            return
        self.kiot_mgr.key = key
        self.log("Đang ngắt kết nối và Exit Key proxy...", "info")

        def _run():
            success, msg = self.kiot_mgr.exit_proxy()
            self.after(0, self.update_proxy_ui)

        threading.Thread(target=_run, daemon=True).start()

    def update_proxy_ui(self):
        cd_rem = self.kiot_mgr.get_cooldown_remaining()

        # 1. Update action button state & text
        if cd_rem > 0:
            self.btn_dash_proxy_action.configure(
                text=f"⏳ {cd_rem}s", fg_color="#37474f", state="disabled"
            )
            self.btn_kiot_new.configure(text=f"⏳ {cd_rem}s", state="disabled")
        else:
            if self.kiot_mgr.is_connected:
                self.btn_dash_proxy_action.configure(
                    text="🔄 ĐỔI PROXY", fg_color="#2e7d32", hover_color="#1b5e20", state="normal"
                )
                self.btn_kiot_new.configure(text="🔄 ĐỔI PROXY", state="normal")
            else:
                self.btn_dash_proxy_action.configure(
                    text="🔗 KẾT NỐI", fg_color="#0288d1", hover_color="#01579b", state="normal"
                )
                self.btn_kiot_new.configure(text="🔗 KẾT NỐI", state="normal")

        # 2. Update EXIT button visibility
        if self.kiot_mgr.is_connected:
            self.btn_dash_proxy_exit.grid(row=0, column=2, padx=(2, 6), pady=4)
        else:
            self.btn_dash_proxy_exit.grid_remove()

        # 3. Update info display
        if self.kiot_mgr.is_connected and self.kiot_mgr.current_http:
            rem_sec = self.kiot_mgr.get_remaining_seconds()
            time_str = "--:--"
            if rem_sec is not None:
                m = rem_sec // 60
                s = rem_sec % 60
                time_str = f"{m:02d}:{s:02d}"

            ip_display = self.kiot_mgr.current_http
            loc_display = self.kiot_mgr.current_location or "Ngẫu nhiên"

            self.lbl_proxy_ip.configure(text=f"🌐 {ip_display}", text_color="#00e5ff")
            self.lbl_proxy_region.configure(text=f"📍 {loc_display}", text_color="#ff5252")
            self.lbl_proxy_time.configure(text=f"⏳ {time_str}", text_color="#ffb300")
        else:
            self.lbl_proxy_ip.configure(text="🌐 Chưa kết nối", text_color="#90a4ae")
            self.lbl_proxy_region.configure(text="📍 IP Trực Tiếp", text_color="#90a4ae")
            self.lbl_proxy_time.configure(text="⏳ --:--", text_color="#90a4ae")

    def log(self, message, msg_type="info"):
        now_str = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{now_str}] {message}\n"

        def _append():
            self.txt_quick_log.insert("end", formatted_msg)
            self.txt_quick_log.see("end")
            self.txt_full_log.insert("end", formatted_msg)
            self.txt_full_log.see("end")

        self.after(0, _append)

    def log_status(self, key, message):
        """Ghi 1 dòng log gắn với `key`; gọi lại cùng key sẽ cập nhật đúng dòng đó."""
        now_str = datetime.now().strftime("%H:%M:%S")
        line = f"[{now_str}] {message}\n"
        tag = "st_" + re.sub(r"\W", "_", str(key))

        def _apply():
            for t in (self.txt_quick_log, self.txt_full_log):
                rng = t.tag_ranges(tag)
                if rng:
                    start = rng[0]
                    t.delete(rng[0], rng[1])
                    t.insert(start, line, tag)
                else:
                    t.insert("end", line, tag)
                t.see("end")

        self.after(0, _apply)

    def clear_logs(self):
        self.txt_quick_log.delete("1.0", "end")
        self.txt_full_log.delete("1.0", "end")

    def copy_logs(self):
        text = self.txt_full_log.get("1.0", "end")
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Thông Báo", "Đã sao chép toàn bộ nhật ký vào Clipboard!")

    def update_stats(self):
        if self.scanner:
            def _update():
                self.card_links.configure(text=str(self.scanner.total_links_generated))
                if hasattr(self.scanner, 'latest_tasks_text') and self.scanner.latest_tasks_text:
                    self.lbl_latest_tasks.configure(text=f"Mã: {self.scanner.latest_tasks_text}")
                else:
                    self.lbl_latest_tasks.configure(text="Mã: --")

                if self.scanner.telegram_sender and self.scanner.telegram_sender.last_message_id:
                    self.lbl_tg_msg_id.configure(text=f"Tele ID: #{self.scanner.telegram_sender.last_message_id}")
                else:
                    self.lbl_tg_msg_id.configure(text="Tele ID: --")
            self.after(0, _update)

    def update_timer(self):
        if self.is_running and self.scanner and self.scanner.next_scan_time:
            rem = int(self.scanner.next_scan_time - time.time())
            if rem > 0:
                self.card_timer.configure(text=f"{rem}s")
            else:
                self.card_timer.configure(text="Đang quét...")
        elif not self.is_running:
            self.card_timer.configure(text="--")

        self.update_proxy_ui()
        self.after(1000, self.update_timer)

    # ---------------- BOT EXECUTION THREAD ----------------
    def start_bot(self):
        self.save_settings_to_env()
        self.is_running = True
        
        self.lbl_status_badge.configure(text="● ĐANG CHẠY", text_color="#4caf50")
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")

        self.bot_thread = threading.Thread(target=self.bot_worker, daemon=True)
        self.bot_thread.start()

    def bot_worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        link999_token = os.getenv('LINK999_API_TOKEN', '').strip() or DEFAULT_LINK999_API_TOKEN
        shortener = GUILink999Shortener(link999_token, domain=self.link999_domain)
        
        tg_token = self.entry_tg_token.get().strip() or os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
        tg_chat = self.entry_tg_chat.get().strip() or os.getenv('TELEGRAM_CHAT_ID', '').strip()
        telegram_sender = GUITelegramSender(tg_token, tg_chat, logger=self.log)

        self.scanner = GUITaskScanner(shortener, self.log, self.update_stats, kiot_mgr=self.kiot_mgr, telegram_sender=telegram_sender, log_status_callback=self.log_status)
        self.scanner.use_telegram = bool(self.switch_telegram.get())
        self.scanner.use_kiotproxy = bool(self.switch_kiotproxy.get())
        self.scanner.step2_enabled = False
        self.scanner.step3_enabled = False
        self.scanner.step4_enabled = True
        self.scanner.refresh_interval = int(os.getenv('REFRESH_INTERVAL', 60))
        self.scanner.generated_links_count = int(os.getenv('GENERATED_LINKS', 10))
        self.scanner.concurrent_scan = int(os.getenv('CONCURRENT_SCAN_PER_LINK', 5))

        async def _main():
            await self.scanner.init_browser()
            await self.scanner.run_scan_loop()

        try:
            self.loop.run_until_complete(_main())
        except Exception as e:
            self.log(f"Worker kết thúc: {e}", "info")
        finally:
            if self.scanner:
                self.loop.run_until_complete(self.scanner.close_browser())
            self.loop.close()

    def stop_bot(self):
        self.is_running = False

        if self.scanner:
            self.scanner.running = False
            
        self.lbl_status_badge.configure(text="● ĐÃ DỪNG", text_color="#f44336")
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.log("Đã yêu cầu DỪNG BOT.", "warning")


if __name__ == "__main__":
    app = BotPhuApp()
    app.mainloop()
