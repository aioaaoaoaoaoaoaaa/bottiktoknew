import re
import requests
import telebot
import threading
import time
import os
import json
import sys

# Cấu hình UTF-8 cho console Windows để hiển thị tiếng Việt và emoji không bị lỗi
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from datetime import datetime, date
from dotenv import load_dotenv
from flask import Flask, request

# Load biến môi trường từ file .env
load_dotenv()

# Tạo Flask app cho health check và webhook
app = Flask(__name__)

@app.route('/')
def home():
    return "TikTok Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint để nhận webhook từ Telegram"""
    if request.method == 'POST':
        json_str = request.get_data().decode('UTF-8')
        print(f"[WEBHOOK] Nhận request: {json_str[:200]}...")  # Log request
        update = telebot.types.Update.de_json(json_str)
        if update.message:
            user_id = update.message.from_user.id
            print(f"[WEBHOOK] User ID: {user_id}, Text: {update.message.text[:50] if update.message.text else 'N/A'}")
        bot.process_new_updates([update])
        return "OK", 200
    return "OK", 200

# =======================================================
# CẤU HÌNH GITHUB ĐỂ ĐỌC DANH SÁCH USER CÓ QUYỀN
# =======================================================
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GIST_ID = os.getenv("GIST_ID")
TIKTOK_ALLOWED_FILE = "tiktok_allowed_users.json"
NOTIFICATION_BLOCKLIST_FILE = "notification_blocklist.json"

# =======================================================
# HỆ THỐNG GIỚI HẠN SỬ DỤNG
# =======================================================
ADMIN_ID = 6762189023
USAGE_FILE = "usage_data.json"
DAILY_LIMIT = 5

def load_usage_data():
    """Đọc dữ liệu sử dụng từ file JSON"""
    try:
        if os.path.exists(USAGE_FILE):
            with open(USAGE_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_usage_data(data):
    """Lưu dữ liệu sử dụng vào file JSON"""
    try:
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        print(f"[-] Lỗi khi lưu dữ liệu sử dụng: {e}")

def get_tiktok_allowed_users():
    """Đọc danh sách user có quyền từ Gist (để tương thích ngược)"""
    if not GITHUB_TOKEN or not GIST_ID:
        print("[-] Thiếu GITHUB_TOKEN hoặc GIST_ID trong biến môi trường")
        return []
    
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        res = requests.get(f'https://api.github.com/gists/{GIST_ID}', headers=headers)
        if res.status_code == 200:
            gist_data = res.json()
            files = gist_data.get('files', {})
            if TIKTOK_ALLOWED_FILE in files:
                content = files[TIKTOK_ALLOWED_FILE]['content']
                data = json.loads(content)
                allowed_users = data.get('allowed_users', [])
                print(f"[+] Đã tải {len(allowed_users)} user có quyền từ Gist")
                return allowed_users
        print(f"[-] Lỗi tải Gist: {res.status_code}")
        return []
    except Exception as e:
        print(f"[-] Lỗi khi đọc danh sách user có quyền từ Gist: {e}")
        return []

def get_notification_allowed_users():
    """Đọc danh sách user có quyền từ bot thông báo (notification_allowed_users.json)"""
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        res = requests.get(f'https://api.github.com/gists/{GIST_ID}', headers=headers)
        if res.status_code == 200:
            gist_data = res.json()
            files = gist_data.get('files', {})
            print(f"[DEBUG] Files trong Gist: {list(files.keys())}")
            
            if 'notification_allowed_users.json' in files:
                content = files['notification_allowed_users.json']['content']
                print(f"[DEBUG] Content notification_allowed_users.json: {content[:200]}...")
                data = json.loads(content)
                # notification_allowed_users.json là mảng trực tiếp
                if isinstance(data, list):
                    print(f"[+] Đã tải {len(data)} user có quyền từ bot thông báo: {data}")
                    return data
                else:
                    print(f"[-] notification_allowed_users.json không phải list, type: {type(data)}, data: {data}")
            else:
                print(f"[-] Không tìm thấy file notification_allowed_users.json trong Gist")
        else:
            print(f"[-] Lỗi tải Gist: {res.status_code}")
        return []
    except Exception as e:
        print(f"[-] Lỗi khi đọc danh sách user có quyền từ bot thông báo: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_notification_public_users():
    """Đọc danh sách user public mode từ bot thông báo"""
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        res = requests.get(f'https://api.github.com/gists/{GIST_ID}', headers=headers)
        if res.status_code == 200:
            gist_data = res.json()
            files = gist_data.get('files', {})
            if 'notification_public_users.json' in files:
                content = files['notification_public_users.json']['content']
                data = json.loads(content)
                if isinstance(data, dict):
                    public_user_ids = [int(k) for k in data.keys()]
                    print(f"[+] Đã tải {len(public_user_ids)} user public mode từ bot thông báo")
                    return public_user_ids
        return []
    except Exception as e:
        print(f"[-] Lỗi khi đọc danh sách user public mode: {e}")
        return []

def get_notification_public_mode():
    """Kiểm tra xem public mode có đang bật không"""
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        res = requests.get(f'https://api.github.com/gists/{GIST_ID}', headers=headers)
        if res.status_code == 200:
            gist_data = res.json()
            files = gist_data.get('files', {})
            if 'notification_public_mode.json' in files:
                content = files['notification_public_mode.json']['content']
                data = json.loads(content)
                is_public = data.get('is_public', False)
                print(f"[+] Public mode status: {is_public}")
                return is_public
        return False
    except Exception as e:
        print(f"[-] Lỗi khi kiểm tra public mode: {e}")
        return False

def get_notification_blocklist():
    """Đọc danh sách user bị block từ Gist"""
    if not GITHUB_TOKEN or not GIST_ID:
        print("[-] Thiếu GITHUB_TOKEN hoặc GIST_ID trong biến môi trường")
        return []
    
    try:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        res = requests.get(f'https://api.github.com/gists/{GIST_ID}', headers=headers)
        if res.status_code == 200:
            gist_data = res.json()
            files = gist_data.get('files', {})
            if NOTIFICATION_BLOCKLIST_FILE in files:
                content = files[NOTIFICATION_BLOCKLIST_FILE]['content']
                data = json.loads(content)
                blocklist = data.get('blocklist', [])
                print(f"[+] Đã tải {len(blocklist)} user bị block từ Gist")
                return blocklist
        print(f"[-] Lỗi tải Gist: {res.status_code}")
        return []
    except Exception as e:
        print(f"[-] Lỗi khi đọc danh sách user bị block từ Gist: {e}")
        return []

def get_notification_credentials_from_gist():
    """Đọc notification_credentials từ Gist raw URL để kiểm tra pass riêng theo ID"""
    try:
        raw_url = "https://gist.githubusercontent.com/namgayysetxii/ac49baab1110415336c250be03a91861/raw/0fc39bff0df8d14cb408f338cc5ec53d2eac3754/notification_credentials.json"
        res = requests.get(raw_url)
        if res.status_code == 200:
            data = json.loads(res.text)
            # Đảm bảo cấu trúc đúng
            if 'tele' not in data:
                data['tele'] = {}
            if 'hwid' not in data:
                data['hwid'] = {}
            print(f"[+] Đã tải notification_credentials từ Gist raw: {len(data.get('tele', {}))} tele, {len(data.get('hwid', {}))} hwid")
            return data
        print(f"[-] Lỗi tải Gist raw: {res.status_code}")
        return {"tele": {}, "hwid": {}}
    except Exception as e:
        print(f"[-] Lỗi khi đọc notification_credentials từ Gist raw: {e}")
        return {"tele": {}, "hwid": {}}

def check_telegram_password(user_id, password):
    """Kiểm tra password riêng theo ID Telegram từ Gist"""
    try:
        credentials = get_notification_credentials_from_gist()
        tele_cred = credentials.get('tele', {}).get(str(user_id))
        
        if tele_cred and tele_cred.get('password') == password:
            # Kiểm tra hạn sử dụng nếu có
            expires_at_str = tele_cred.get('expires_at')
            if expires_at_str:
                try:
                    from datetime import datetime
                    expires_at = datetime.fromisoformat(expires_at_str)
                    if expires_at < datetime.now():
                        return False, "❌ Mật khẩu của bạn đã hết hạn."
                except ValueError:
                    pass
            return True, f"✅ Đăng nhập bằng ID Telegram {user_id} thành công!"
        
        return False, None
    except Exception as e:
        print(f"[-] Lỗi khi kiểm tra password từ Gist: {e}")
        return False, None

def is_user_authorized(user_id):
    """Kiểm tra xem user có quyền sử dụng bot TikTok không (chỉ check từ notification_credentials.json trong Gist)"""
    # Admin luôn có quyền
    if user_id == ADMIN_ID:
        return True
    
    # Chỉ kiểm tra user có pass riêng trong notification_credentials.json
    credentials = get_notification_credentials_from_gist()
    tele_cred = credentials.get('tele', {}).get(str(user_id))
    
    if tele_cred:
        # Kiểm tra hạn sử dụng nếu có
        expires_at_str = tele_cred.get('expires_at')
        if expires_at_str:
            try:
                from datetime import datetime
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at < datetime.now():
                    print(f"[DEBUG] is_user_authorized({user_id}): False (pass hết hạn)")
                    return False
            except ValueError:
                pass
        print(f"[DEBUG] is_user_authorized({user_id}): True (có pass riêng trong credentials)")
        return True
    
    print(f"[DEBUG] is_user_authorized({user_id}): False (không có quyền)")
    return False

def is_user_public(user_id):
    """Kiểm tra xem user có đang ở public mode không (user lạ tạm thời)"""
    # Admin không phải public user
    if user_id == ADMIN_ID:
        return False
    
    # Nếu đã có quyền đầy đủ, không phải public user
    if is_user_authorized(user_id):
        return False
    
    # Kiểm tra public mode và danh sách public users
    is_public_mode = get_notification_public_mode()
    if not is_public_mode:
        return False
    
    public_users = get_notification_public_users()
    return user_id in public_users

def is_user_blocked(user_id):
    """Kiểm tra xem user có bị block từ bot thông báo không"""
    # Admin không bao giờ bị block
    if user_id == ADMIN_ID:
        return False
    
    # Đọc danh sách user bị block từ Gist
    blocklist = get_notification_blocklist()
    return user_id in blocklist

def check_daily_limit(user_id, platform='tiktok'):
    """Kiểm tra user đã vượt giới hạn ngày chưa (phân biệt TikTok và Facebook)"""
    # Admin không bị giới hạn
    if user_id == ADMIN_ID:
        return True, 0
    
    # Xác định giới hạn dựa trên quyền của user và nền tảng
    if is_user_authorized(user_id):
        # User đã có pass trong notification_credentials.json (đọc từ Gist)
        if platform == 'tiktok':
            daily_limit = 4  # TikTok: 4 video/ngày
        elif platform == 'facebook':
            daily_limit = 2  # Facebook: 2 video/ngày
        elif platform == 'youtube':
            daily_limit = 5  # YouTube: 5 video/ngày
        else:
            daily_limit = 4  # Mặc định
    elif is_user_public(user_id):
        # User public mode (user lạ tạm thời)
        daily_limit = 1  # Cả TikTok, Facebook, YouTube: 1 video/ngày
    else:
        # User hoàn toàn lạ (không có trong Gist)
        if platform == 'tiktok':
            daily_limit = 1  # TikTok: 1 video/ngày
        elif platform == 'youtube':
            daily_limit = 1  # YouTube: 1 video/ngày
        else:
            daily_limit = 1  # Mặc định
    
    user_id_str = str(user_id)
    today = str(date.today())
    
    data = load_usage_data()
    
    # Reset count nếu ngày mới
    if user_id_str not in data or data[user_id_str].get('date') != today:
        data[user_id_str] = {'date': today, 'tiktok_count': 0, 'facebook_count': 0, 'youtube_count': 0}
        save_usage_data(data)
    
    # Lấy count theo nền tảng
    if platform == 'tiktok':
        count = data[user_id_str].get('tiktok_count', 0)
    elif platform == 'facebook':
        count = data[user_id_str].get('facebook_count', 0)
    elif platform == 'youtube':
        count = data[user_id_str].get('youtube_count', 0)
    else:
        count = data[user_id_str].get('tiktok_count', 0) + data[user_id_str].get('facebook_count', 0)
    
    if count >= daily_limit:
        return False, count
    
    return True, count

def increment_usage(user_id, platform='tiktok'):
    """Tăng count sử dụng cho user (phân biệt TikTok và Facebook)"""
    if user_id == ADMIN_ID:
        return
    
    user_id_str = str(user_id)
    today = str(date.today())
    
    data = load_usage_data()
    
    if user_id_str not in data or data[user_id_str].get('date') != today:
        data[user_id_str] = {'date': today, 'tiktok_count': 0, 'facebook_count': 0, 'youtube_count': 0}
    
    # Tăng count theo nền tảng
    if platform == 'tiktok':
        data[user_id_str]['tiktok_count'] = data[user_id_str].get('tiktok_count', 0) + 1
    elif platform == 'facebook':
        data[user_id_str]['facebook_count'] = data[user_id_str].get('facebook_count', 0) + 1
    elif platform == 'youtube':
        data[user_id_str]['youtube_count'] = data[user_id_str].get('youtube_count', 0) + 1
    
    save_usage_data(data)

# =======================================================
# CẤU HÌNH THÔNG TIN BOT VÀ TOKEN CHUNG
# =======================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
# Dùng dummy token nếu chưa cấu hình BOT_TOKEN để vẫn chạy được chế độ test API
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else telebot.TeleBot("123456:dummy_token_for_testing")

# Key tài khoản RapidAPI dùng chung của bạn
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    raise ValueError("RAPIDAPI_KEY không được tìm thấy trong biến môi trường!")

# Biến toàn cầu để kiểm soát progress bar
progress_running = False


def progress_bar(chat_id, message_id):
    """Chạy progress bar từ 0% đến 100% từng số một"""
    global progress_running
    for i in range(101):
        if not progress_running:
            break
        try:
            bot.edit_message_text(f"Process: {i}%", chat_id=chat_id, message_id=message_id)
            time.sleep(0.05)  # Delay nhỏ để tạo hiệu ứng mượt
        except Exception:
            break


# =======================================================
# LÕI CÁC HÀM GỌI API (4 MÁY CHỦ XOAY TUA)
# =======================================================

def call_api_1_scrapper(tiktok_url):
    """Máy chủ 1: TikTok Scrapper (Yêu cầu trích xuất ID)"""
    match = re.search(r"video/(\d+)", tiktok_url)
    video_id = match.group(1) if match else None
    if not video_id:
        return None, None
        
    host = "tiktok-scrapper-videos-music-challenges-downloader.p.rapidapi.com"
    url = f"https://{host}/video/{video_id}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            data_block = res_json.get('data', {})
            aweme_detail = data_block.get('aweme_detail', {})
            caption = aweme_detail.get('desc', '')
            url_list = aweme_detail.get('video', {}).get('play_addr', {}).get('url_list', [])
            if url_list:
                print("[+] API 1 bóc link thành công!")
                return url_list[0], caption
    except Exception as e:
        print(f"[-] API 1 gặp sự cố: {e}")
    return None, None


def call_api_2_social_media(tiktok_url):
    """Máy chủ 2: Social Media Video Downloader (Truyền thẳng link)"""
    host = "social-media-video-downloader.p.rapidapi.com"
    url = f"https://{host}/tiktok/v3/post/details"
    querystring = {"url": tiktok_url}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            contents = res_json.get('contents', [])
            if contents:
                videos = contents[0].get('videos', [])
                if videos:
                    video_url = videos[0].get('url')
                    print("[+] API 2 bóc link thành công!")
                    return video_url, "Video tải từ Máy chủ dự phòng 2 🚀"
    except Exception as e:
        print(f"[-] API 2 gặp sự cố: {e}")
    return None, None


def call_api_3_tiktok_api23(tiktok_url):
    """Máy chủ 3: Tiktok API (Đọc từ trường 'play' lớp ngoài cùng)"""
    host = "tiktok-api23.p.rapidapi.com"
    url = f"https://{host}/api/download/video"
    querystring = {"url": tiktok_url}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            video_url = res_json.get('play') 
            if video_url:
                print("[+] API 3 bóc link thành công!")
                return video_url, "Video tải từ Máy chủ dự phòng 3 💎"
    except Exception as e:
        print(f"[-] API 3 gặp sự cố: {e}")
    return None, None


def call_api_4_no_watermark2(tiktok_url):
    """Máy chủ 4 (MỚI): Tiktok Video No Watermark (Đọc từ data.hdplay hoặc data.play)"""
    host = "tiktok-video-no-watermark2.p.rapidapi.com"
    url = f"https://{host}/"
    
    # Cấu hình tham số hd=1 giống như trên playground bạn test thành công
    querystring = {"url": tiktok_url, "hd": "1"}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            data_block = res_json.get('data', {})
            
            # Ưu tiên bản HD chất lượng cao không logo theo cấu trúc hệ thống
            video_url = data_block.get('hdplay') or data_block.get('play')
            caption = data_block.get('title') or "Video tải từ Máy chủ dự phòng 4 🔥"
            
            if video_url:
                print("[+] API 4 bóc link không logo thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] API 4 gặp sự cố: {e}")
    return None, None


def call_api_5_7scorp(tiktok_url):
    """Máy chủ 5: TikTok Downloader by 7scorp (Gói Free 400 req/tháng)"""
    host = "tiktok-downloader-download-tiktok-videos-without-watermark.p.rapidapi.com"
    
    # Endpoint số 2 chính xác của bạn
    url = f"https://{host}/vid/index" 
    
    querystring = {"url": tiktok_url}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Bóc tách chuẩn theo Response body trên ảnh của bạn
            video_url = res_json.get('video')
            # Nếu API trả về dạng danh sách (list), lấy phần tử link đầu tiên
            if isinstance(video_url, list) and video_url:
                if isinstance(video_url[0], dict):
                    video_url = video_url[0].get('url') or video_url[0].get('play_url')
                else:
                    video_url = str(video_url[0])
            elif isinstance(video_url, str):
                video_url = video_url.strip()

            caption = res_json.get('title') or res_json.get('desc') or "Video tải từ Máy chủ dự phòng 5 ✨"
            
            if video_url:
                print("[+] API 5 (7scorp) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] API 5 gặp sự cố: {e}")
    return None, None


def call_fb_api_mahmudul(fb_url):
    """FB Máy chủ: Facebook Video Downloader by mahmudulhasan62894 (Cấu trúc chuẩn theo ảnh)"""
    host = "facebook-video-downloader9.p.rapidapi.com"
    url = f"https://{host}/api/v1/videos/download"
    
    querystring = {"url": fb_url}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Đi sâu vào cụm dữ liệu theo đúng ảnh chụp
            data_block = res_json.get('data', {})
            video_info = data_block.get('video', {})
            download_block = data_block.get('download', {})
            
            # Lấy caption (tiêu đề video)
            caption = video_info.get('title') or "Video tải từ Facebook Server 🎬"
            
            # Bóc tách link tải: Ưu tiên bản HD chất lượng cao, nếu không có thì lấy bản SD chất lượng thường
            hd_block = download_block.get('hd', {})
            sd_block = download_block.get('sd', {})
            
            video_url = hd_block.get('url') or sd_block.get('url')
            
            if video_url:
                print("[+] FB API (mahmudul) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API (mahmudul) gặp sự cố: {e}")
    return None, None


def call_fb_api_full_downloader(fb_url):
    """FB Máy chủ 2: Full Downloader Social Media (Cấu trúc phẳng, siêu nhanh)"""
    host = "full-downloader-social-media.p.rapidapi.com"
    url = f"https://{host}/"
    
    querystring = {"url": fb_url}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Bóc tách trực tiếp lớp ngoài cùng theo đúng Response body trong ảnh
            video_url = res_json.get('download_url')
            caption = res_json.get('caption') or "Video tải từ Facebook Server 2 🚀"
            
            if video_url:
                print("[+] FB API 2 (Full Downloader) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API 2 gặp sự cố: {e}")
    return None, None


def call_fb_api_social_media_v3(fb_url):
    """FB Máy chủ 3: Social Media Video Downloader V3 (Có ép độ phân giải HD)"""
    host = "social-media-video-downloader.p.rapidapi.com"
    url = f"https://{host}/facebook/v3/post/details"
    
    # Thêm cấu hình renderableFormats để lấy video sắc nét nhất như Nam test trên web
    querystring = {
        "url": fb_url,
        "renderableFormats": "720p,highres"
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Cấu trúc bóc tách JSON đặc trưng của nhà phát triển này
            contents = res_json.get('contents', [])
            if contents:
                videos = contents[0].get('videos', [])
                if videos:
                    # Lấy link video trực tiếp lớp ngoài cùng
                    video_url = videos[0].get('url')
                    return video_url, "Video tải từ Facebook Server 3 💎"
    except Exception as e:
        print(f"[-] FB API 3 gặp sự cố: {e}")
    return None, None


def call_fb_api_social_download_all_in_one(fb_url):
    """FB Máy chủ 4: Social Download All In One (Lệnh POST - JSON Body)"""
    host = "social-download-all-in-one.p.rapidapi.com"
    url = f"https://{host}/v1/social/autolink"
    
    # Header bắt buộc có Content-Type JSON cho lệnh POST
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json"
    }
    
    # Định dạng dữ liệu dạng dict để requests tự ép sang JSON string
    payload = {
        "url": fb_url
    }
    
    try:
        # BÍ QUYẾT: Dùng requests.post và truyền json=payload
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Cấu trúc phổ biến của hệ sinh thái All In One này:
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('links', [{}])[0].get('url')
            caption = res_json.get('title') or "Video tải từ Facebook Server 4 💎"
            
            if video_url:
                print("[+] FB API 4 (All In One POST) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API 4 gặp sự cố: {e}")
    return None, None


def call_fb_api_media_download_url(fb_url):
    """FB Máy chủ 5: Facebook Media API (Lệnh POST - JSON Body cực xịn)"""
    host = "facebook-media-api.p.rapidapi.com"
    url = f"https://{host}/media/html"
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json"
    }
    
    # Cấu trúc payload chứa url và cookie trống theo đúng ảnh test của bạn
    payload = {
        "url": fb_url,
        "cookie": ""
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            
            # Cào dữ liệu từ kết quả trả về
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('data', {}).get('url')
            caption = res_json.get('title') or "Video tải từ Facebook Server 5 💎"
            
            if video_url:
                print("[+] FB API 5 (Media API) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API 5 gặp sự cố: {e}")
    return None, None


def extract_youtube_id(url):
    """Hàm phụ tách lấy ID video từ link YouTube hoặc Shorts bất kỳ"""
    pattern = r"(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=)([^#\&\?]*)"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def call_yt_api_datafanatic_details(yt_url):
    """YT Máy chủ 1: YouTube Media Downloader by DataFanatic (100 req/tháng)"""
    # 1. Tách lấy ID video từ URL người dùng nhập
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        print("[-] Không tìm thấy ID video YouTube hợp lệ.")
        return None, None
        
    host = "youtube-media-downloader.p.rapidapi.com"
    url = f"https://{host}/v2/video/details"
    
    # Cấu hình các tham số chuẩn theo đúng giao diện web bạn đã test
    querystring = {
        "videoId": video_id,
        "urlAccess": "direct", # Dùng link trực tiếp để Telegram có thể tải được
        "videos": "auto",
        "audios": "auto"
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        print(f"[*] YT API 1 Response status: {response.status_code}")
        if response.status_code == 200:
            res_json = response.json()
            print(f"[*] YT API 1 Response JSON: {res_json}")
            
            # Tiêu đề video làm Caption
            caption = res_json.get('title') or "Video tải từ YouTube Server 1 🎥"
            
            # Đi sâu vào cấu trúc JSON để tìm link video .mp4
            videos_block = res_json.get('videos', {})
            items = videos_block.get('items', [])
            
            video_url = None
            
            # VÒNG QUÉT 1: Tìm bản Full HD (1080p) hoặc HD (720p) đã được gộp sẵn tiếng (hasAudio=True)
            for item in items:
                quality = str(item.get('quality', ''))
                if ('1080p' in quality or '720p' in quality) and item.get('hasAudio') == True:
                    video_url = item.get('url')
                    print(f"[+] Tìm thấy bản video gộp sẵn tiếng chất lượng: {quality}")
                    break
            
            # VÒNG QUÉT 2: Nếu không thấy bản HD/Full HD gộp sẵn tiếng, lấy đại link video đầu tiên trong danh sách có tiếng
            if not video_url:
                for item in items:
                    if item.get('hasAudio') == True:
                        video_url = item.get('url')
                        break
            
            # VÒNG QUÉT 3: Phương án cuối cùng, lấy link bất kỳ có sẵn
            if not video_url and items:
                video_url = items[0].get('url')
                
            if video_url:
                print("[+] YT API 1 (DataFanatic Details) bóc link thành công!")
                return video_url, caption
                
    except Exception as e:
        print(f"[-] YT API 1 gặp sự cố: {e}")
    return None, None


def call_yt_api_fast_downloader_v2(yt_url):
    """YT Máy chủ 2: YouTube Video FAST Downloader 24/7 (Cấu trúc chuẩn theo ảnh)"""
    # 1. Sử dụng hàm extract_youtube_id có sẵn để lấy ID
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        return None, None
        
    host = "youtube-video-fast-downloader-24-7.p.rapidapi.com"
    
    # Ép cấu trúc đường dẫn chứa videoId ở cuối giống hệt trong cURL Code Snippet của bạn
    url = f"https://{host}/download_video/{video_id}"
    
    # Để quality mặc định là 247 hoặc bạn có thể đổi theo tài liệu test của API
    querystring = {"quality": "247"}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        print(f"[*] YT API 2 Response status: {response.status_code}")
        if response.status_code == 200:
            res_json = response.json()
            print(f"[*] YT API 2 Response JSON: {res_json}")
            
            # Phân tách kết quả trả về từ API
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('video_url')
            caption = res_json.get('title') or "Video tải từ YouTube FAST Server ⚡"
            
            if video_url:
                print("[+] YT API 2 (FAST Downloader) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] YT API 2 gặp sự cố: {e}")
    return None, None


def call_yt_api_shorts_downloader_v3(yt_url):
    """YT Máy chủ 3: YouTube Video And Shorts Downloader (Cấu trúc chuẩn theo ảnh)"""
    # 1. Sử dụng hàm extract_youtube_id có sẵn để lấy ID video
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        return None, None
        
    host = "youtube-video-and-shorts-downloader1.p.rapidapi.com"
    url = f"https://youtube-video-and-shorts-downloader1.p.rapidapi.com/youtube/v3/video/details"
    
    # Cấu hình các tham số Query Params chuẩn chỉ theo đúng ảnh test của bạn
    querystring = {
        "videoId": video_id,
        "urlAccess": "normal", # Dùng link trực tiếp để Telegram có thể tải được
        "renderableFormats": "720p,highres", # Ép API gộp sẵn tiếng chất lượng cao
        "getTranscript": "false"
    }
    
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        print(f"[*] YT API 3 Response status: {response.status_code}")
        if response.status_code == 200:
            res_json = response.json()
            print(f"[*] YT API 3 Response JSON: {res_json}")
            
            # Cấu trúc JSON đặc trưng của nhà phát triển này (Bọc trong mảng contents)
            contents = res_json.get('contents', [])
            if contents:
                videos = contents[0].get('videos', [])
                print(f"[*] YT API 3 Videos block: {videos}")
                if videos:
                    # Tìm link không phải tunnel/redirector
                    video_url = None
                    for video in videos:
                        url = video.get('url')
                        if url and 'tunnel' not in url and 'redirector' not in url:
                            video_url = url
                            print(f"[+] Tìm thấy link trực tiếp: {video_url}")
                            break
                    
                    # Nếu không tìm thấy link trực tiếp, lấy link đầu tiên
                    if not video_url:
                        video_url = videos[0].get('url')
                        print(f"[-] Chỉ tìm thấy link tunnel: {video_url}")
                    
                    caption = contents[0].get('title') or "Video tải từ YouTube Server 3 💎"
                    print("[+] YT API 3 (Shorts Downloader) bóc link thành công!")
                    return video_url, caption
                    
    except Exception as e:
        print(f"[-] YT API 3 gặp sự cố: {e}")
    return None, None


# =======================================================
# LOGIC ĐIỀU KHIỂN CHÍNH CỦA BOT TELEGRAM
# =======================================================

def is_valid_tiktok_url(url):
    """Kiểm tra xem link có phải là TikTok hợp lệ không"""
    tiktok_patterns = [
        r'https?://(www\.)?tiktok\.com/@[\w\.-]+/video/\d+',
        r'https?://(www\.)?tiktok\.com/t/[\w-]+',
        r'https?://(vm|vt)\.tiktok\.com/[\w-]+',
        r'https?://(www\.)?tiktok\.com/[\w\.-]+/video/\d+'
    ]
    for pattern in tiktok_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True
    return False


def is_valid_facebook_url(url):
    """Kiểm tra xem link có phải là Facebook hợp lệ không"""
    fb_patterns = [
        r'https?://(www\.|web\.|m\.)?facebook\.com/',
        r'https?://(www\.)?fb\.watch/',
        r'https?://(www\.)?fb\.com/'
    ]
    for pattern in fb_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


def is_valid_youtube_url(url):
    """Kiểm tra xem link có phải là YouTube hợp lệ không"""
    yt_patterns = [
        r'https?://(www\.)?youtube\.com/watch\?v=',
        r'https?://(www\.)?youtube\.com/shorts/',
        r'https?://(www\.)?youtube\.com/embed/',
        r'https?://(www\.)?youtu\.be/',
        r'https?://(www\.)?youtube\.com/v/'
    ]
    for pattern in yt_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            return True
    return False


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    user_id = message.from_user.id
    
    # Kiểm tra xem user có bị block từ bot thông báo không
    if is_user_blocked(user_id):
        bot.reply_to(message, "🚫 Bạn đã bị chặn bởi Admin.\n\n"
                              "💬 Ib @itisnotmyfault0 để mở khóa\n\n"
                              "💎 Mua pass bot 15k/10d\n"
                              "📞 Ib saler: @itisnotmyfault0\n\n"
                              "🖥️ Muốn sử dụng app tb trên máy mình\n"
                              "📞 Ib admin @hfnam04 (300k/nửa năm)", parse_mode="HTML")
        return
    
    # Kiểm tra quyền từ bot thông báo
    if is_user_authorized(user_id):
        # User đã có pass bot thông báo (đọc từ Gist)
        bot.reply_to(message, "👋 Xin chào! Hệ thống tải TikTok, Facebook & YouTube Siêu Cấp đã sẵn sàng.\n\n"
                              "👉 Gửi link TikTok, Facebook hoặc YouTube vào đây bot sẽ gửi bạn lại video không logo!\n\n"
                              "📊 Limit:\n"
                              "• TikTok: 4 video/ngày\n"
                              "• Facebook: 2 video/ngày\n\n"
                              "✅ Bạn đã có pass bot thông báo!")
    elif is_user_public(user_id):
        # User public mode (user lạ tạm thời)
        bot.reply_to(message, "👋 Xin chào! Hệ thống tải TikTok, Facebook & YouTube Siêu Cấp đã sẵn sàng.\n\n"
                              "👉 Gửi link TikTok, Facebook hoặc YouTube vào đây bot sẽ gửi bạn lại video không logo!\n\n"
                              "📊 Limit: 1 video/ngày (Dùng thử - Public Mode)\n\n"
                              "💎 Mua pass bot 15k/10d để nâng giới hạn lên TikTok 4, Facebook 2 video/ngày\n"
                              "📞 Ib saler: @itisnotmyfault0\n\n"
                              "🖥️ Muốn sử dụng app tb trên máy mình\n"
                              "📞 Ib admin @hfnam04 (300k/nửa năm)", parse_mode="HTML")
    else:
        # User hoàn toàn lạ
        bot.reply_to(message, "👋 Xin chào! Hệ thống tải TikTok, Facebook & YouTube Siêu Cấp đã sẵn sàng.\n\n"
                              "👉 Gửi link TikTok, Facebook hoặc YouTube vào đây bot sẽ gửi bạn lại video không logo!\n\n"
                              "📊 Limit: 1 video/ngày (Dùng thử)\n\n"
                              "💎 Mua pass bot 15k/10d để nâng giới hạn lên TikTok 4, Facebook 2 video/ngày\n"
                              "📞 Ib saler: @itisnotmyfault0\n\n"
                              "🖥️ Muốn sử dụng app tb trên máy mình\n"
                              "📞 Ib admin @hfnam04 (300k/nửa năm)", parse_mode="HTML")


@bot.message_handler(func=lambda message: not message.text.startswith('http') and not message.text.startswith('/'))
def handle_password(message):
    """Xử lý password riêng theo ID Telegram để đăng nhập"""
    # Chỉ xử lý mật khẩu trong chat riêng tư (tránh spam trong nhóm/kênh)
    if message.chat.type != 'private':
        return
    user_id = message.from_user.id
    password = message.text.strip()
    
    # Nếu user đã có quyền, không cần xử lý password
    if is_user_authorized(user_id):
        return
    
    # Kiểm tra password từ Gist
    success, result = check_telegram_password(user_id, password)
    if success:
        bot.reply_to(message, result, parse_mode="HTML")
    else:
        # Nếu password sai, hiển thị thông báo hướng dẫn
        msg = (
            "❌ Mật khẩu không đúng hoặc bạn chưa được cấp quyền.\n\n"
            f"🆔 ID của bạn: <code>{user_id}</code>\n\n"
            "💎 Mua pass bot 15k/10d\n"
            "📞 Ib saler: @itisnotmyfault0\n\n"
            "🖥️ Muốn sử dụng app tb trên máy mình\n"
            "📞 Ib admin @hfnam04 (300k/nửa năm)"
        )
        bot.reply_to(message, msg, parse_mode="HTML")

@bot.message_handler(func=lambda message: message.text.startswith('http'))
def handle_message(message):
    user_id = message.from_user.id
    raw_url = message.text.strip()
    
    # Kiểm tra xem user có bị block từ bot thông báo không
    if is_user_blocked(user_id):
        bot.reply_to(message, "🚫 Bạn đã bị chặn bởi Admin.\n\n"
                              "💬 Ib @itisnotmyfault0 để mở khóa\n\n"
                              "💎 Mua pass bot 15k/10d\n"
                              "📞 Ib saler: @itisnotmyfault0\n\n"
                              "🖥️ Muốn sử dụng app tb trên máy mình\n"
                              "📞 Ib admin @hfnam04 (300k/nửa năm)", parse_mode="HTML")
        return
    
    # Kiểm tra link có phải TikTok, Facebook hay YouTube hợp lệ không
    is_tiktok = is_valid_tiktok_url(raw_url)
    is_facebook = is_valid_facebook_url(raw_url)
    is_youtube = is_valid_youtube_url(raw_url)
    
    print(f"[*] Debug: is_tiktok={is_tiktok}, is_facebook={is_facebook}, is_youtube={is_youtube}")
    print(f"[*] Debug: URL={raw_url}")
    
    # Nếu là YouTube, thông báo tính năng đang phát triển
    if is_youtube:
        bot.reply_to(message, "🚧 Tính năng tải video YouTube đang được phát triển!\n\n"
                              "🔧 Chúng tôi đang hoàn thiện để mang lại trải nghiệm tốt nhất.\n"
                              "📢 Theo dõi để nhận thông báo khi tính năng sẵn sàng!\n\n"
                              "👉 Hiện tại bạn có thể tải video TikTok và Facebook.")
        return
    
    if not is_tiktok and not is_facebook:
        error_message = (
            "❌ Link không hợp lệ! Vui lòng nhập lại link TikTok hoặc Facebook đúng.\n\n"
            "📱 **Mẫu link TikTok trên điện thoại:**\n"
            "• https://vm.tiktok.com/ZM6abc123/\n"
            "• https://vt.tiktok.com/ZM6abc123/\n\n"
            "💻 **Mẫu link TikTok trên máy tính:**\n"
            "• https://www.tiktok.com/@username/video/1234567890\n\n"
            "📘 **Mẫu link Facebook:**\n"
            "• https://www.facebook.com/username/videos/1234567890\n"
            "• https://fb.watch/abc123/\n"
            "• https://fb.com/username/videos/1234567890\n\n"
            "👉 Hãy copy link từ TikTok hoặc Facebook và gửi lại cho bot!"
        )
        bot.reply_to(message, error_message)
        return
    
    # Không chặn user không có quyền - cho phép dùng thử với giới hạn 1 video/ngày
    
    # Kiểm tra giới hạn sử dụng hàng ngày (phân biệt TikTok và Facebook)
    platform = 'tiktok' if is_tiktok else 'facebook'
    can_use, current_count = check_daily_limit(user_id, platform)
    if not can_use:
        # Xác định giới hạn dựa trên quyền của user và nền tảng
        if is_user_authorized(user_id):
            daily_limit = 3 if platform == 'tiktok' else 2
        else:
            daily_limit = 1
        
        platform_name = 'TikTok' if platform == 'tiktok' else 'Facebook'
        limit_message = (
            f"⚠️ Bạn đã dùng hết {daily_limit} lượt tải video {platform_name} hôm nay!\n\n"
            f"📊 Số lượt đã dùng: {current_count}/{daily_limit}\n"
            f"🔄 Hãy quay lại vào ngày mai để tiếp tục sử dụng!"
        )
        bot.reply_to(message, limit_message)
        return
    
    # Tăng count sử dụng theo nền tảng
    increment_usage(user_id, platform)
    
    status_msg = bot.send_message(message.chat.id, "Process: 0%")
    # Tự động xóa link video của người dùng khi bắt đầu gọi API xử lý
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass
    
    # Bắt đầu chạy progress bar trong thread riêng biệt
    global progress_running
    progress_running = True
    progress_thread = threading.Thread(target=progress_bar, args=(message.chat.id, status_msg.message_id))
    progress_thread.start()

    # Giải mã nhanh nếu là link rút gọn trên điện thoại (vt.tiktok hoặc vm.tiktok)
    if "vt.tiktok.com" in raw_url or "vm.tiktok.com" in raw_url:
        try:
            response = requests.head(raw_url, allow_redirects=True, timeout=6)
            raw_url = response.url
        except Exception:
            pass

    # DANH SÁCH MẠNG LƯỚI API THEO LOẠI LINK
    if is_tiktok:
        # 5 máy chủ TikTok xoay tua
        api_servers = [
            {"name": "Máy chủ Chính (API 1)", "func": call_api_1_scrapper},
            {"name": "Máy chủ Dự phòng 2 (API 2)", "func": call_api_2_social_media},
            {"name": "Máy chủ Dự phòng 3 (API 3)", "func": call_api_3_tiktok_api23},
            {"name": "Máy chủ Không Logo (API 4)", "func": call_api_4_no_watermark2},
            {"name": "Máy chủ 7scorp (API 5)", "func": call_api_5_7scorp}
        ]
    elif is_facebook:
        # 5 máy chủ Facebook xoay tua
        api_servers = [
            {"name": "Facebook Server (mahmudul)", "func": call_fb_api_mahmudul},
            {"name": "Facebook Server 2 (Full Downloader)", "func": call_fb_api_full_downloader},
            {"name": "Facebook Server 3 (Social Media V3 HD)", "func": call_fb_api_social_media_v3},
            {"name": "Facebook Server 4 (All In One POST)", "func": call_fb_api_social_download_all_in_one},
            {"name": "Facebook Server 5 (Media API)", "func": call_fb_api_media_download_url}
        ]
    else:
        # 3 máy chủ YouTube xoay tua
        api_servers = [
            {"name": "YouTube Server (DataFanatic)", "func": call_yt_api_datafanatic_details},
            {"name": "YouTube FAST Server (24/7)", "func": call_yt_api_fast_downloader_v2},
            {"name": "YouTube Shorts Server (V3)", "func": call_yt_api_shorts_downloader_v3}
        ]

    video_link, caption = None, None

    # Vòng lặp duyệt tự động qua từng máy chủ gánh lỗi cho nhau
    for index, server in enumerate(api_servers):
        print(f"[*] Đang thử thách qua: {server['name']}...")

        # Thực thi gọi hàm bóc tách link video
        video_link, caption = server["func"](raw_url)

        # Nếu lấy được link thành công, dừng ngay và không thử API khác
        if video_link:
            print(f"[+] Thành công tại {server['name']}.")
            break
        
        # Nếu API này fail, tiếp tục thử API tiếp theo
        print(f"[-] {server['name']} thất bại, chuyển sang máy chủ tiếp theo...")

    # TIẾN HÀNH GỬI TRẢ FILE VIDEO SẠCH CHO USER
    # Dừng progress bar
    progress_running = False
    
    if video_link:
        try:
            bot.edit_message_text("Process: 100%", chat_id=message.chat.id, message_id=status_msg.message_id)
            bot.send_video(chat_id=message.chat.id, video=video_link, caption=caption if caption else "🎬")
            bot.delete_message(message.chat.id, status_msg.message_id)
            print("[+] Đã gửi thành công video!")
        except Exception as e:
            print(f"[-] Lỗi chi tiết khi tải video lên Telegram: {e}")
            print(f"[-] Video link: {video_link}")
            bot.edit_message_text(f"❌ Lỗi khi tải video lên Telegram: {e}", chat_id=message.chat.id, message_id=status_msg.message_id)
    else:
        if is_tiktok:
            error_msg = "💥 Toàn bộ hệ thống 5 máy chủ TikTok đều không phản hồi link này hoặc cụm tài khoản đã cạn kiệt quota tháng. Hãy thử lại sau!"
        elif is_facebook:
            error_msg = "💥 Toàn bộ hệ thống 5 máy chủ Facebook đều không phản hồi link này. Hãy thử lại sau!"
        else:
            error_msg = "💥 Toàn bộ hệ thống 3 máy chủ YouTube đều không phản hồi link này. Hãy thử lại sau!"
        bot.edit_message_text(error_msg, chat_id=message.chat.id, message_id=status_msg.message_id)




def keep_alive_ping(url):
    """Tự động gửi request ping đến /health mỗi 10 phút để Render không bị tắt (Sleep mode)"""
    while True:
        time.sleep(600)  # 10 phút
        try:
            requests.get(url, timeout=10)
            print(f"[Keep-Alive] Ping thành công tới {url}")
        except Exception as e:
            print(f"[Keep-Alive] Lỗi ping: {e}")


def test_tiktok_apis(raw_url):
    """Hàm kiểm tra chi tiết từng máy chủ API TikTok và thử tải file thực tế về máy"""
    raw_url = raw_url.strip()
    if not raw_url:
        return

    print("\n" + "="*60)
    print(f"🔍 BẮT ĐẦU KIỂM TRA LINK: {raw_url}")
    print("="*60)

    # Giải mã link rút gọn nếu là vt.tiktok.com hoặc vm.tiktok.com
    actual_url = raw_url
    if "vt.tiktok.com" in raw_url or "vm.tiktok.com" in raw_url:
        try:
            print("[*] Phát hiện link rút gọn, đang giải mã sang link gốc...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.get(raw_url, headers=headers, allow_redirects=True, stream=True, timeout=8)
            actual_url = res.url
            print(f"[+] Link sau giải mã: {actual_url}")
        except Exception as e:
            print(f"[-] Không thể mở link rút gọn: {e}")

    api_servers = [
        {"name": "Máy chủ 1: TikTok Scrapper", "func": call_api_1_scrapper},
        {"name": "Máy chủ 2: Social Media Downloader", "func": call_api_2_social_media},
        {"name": "Máy chủ 3: Tiktok API23", "func": call_api_3_tiktok_api23},
        {"name": "Máy chủ 4: No Watermark 2", "func": call_api_4_no_watermark2},
        {"name": "Máy chủ 5: 7scorp Downloader", "func": call_api_5_7scorp}
    ]

    working_apis = []

    for idx, server in enumerate(api_servers, 1):
        print(f"\n👉 [TEST {idx}/5] {server['name']}...")
        try:
            start_time = time.time()
            video_url, caption = server["func"](actual_url)
            elapsed = time.time() - start_time

            if video_url:
                print(f"   ✅ Bóc link thành công ({elapsed:.2f}s)!")
                print(f"   📌 Tiêu đề: {caption[:70] if caption else 'Không có'}")
                print(f"   🔗 Link video: {video_url[:80]}...")
                
                # Tiến hành kiểm tra tải file về máy
                print(f"   ⬇️ Đang thử tải video về đĩa...")
                dl_headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.tiktok.com/"
                }
                v_res = requests.get(video_url, headers=dl_headers, stream=True, timeout=15)
                if v_res.status_code == 200:
                    output_file = f"test_tiktok_server_{idx}.mp4"
                    downloaded_size = 0
                    with open(output_file, 'wb') as f:
                        for chunk in v_res.iter_content(chunk_size=1024 * 64):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                    
                    size_mb = downloaded_size / (1024 * 1024)
                    print(f"   🎉 TẢI THÀNH CÔNG! Đã lưu: {output_file} ({size_mb:.2f} MB)")
                    working_apis.append({
                        "name": server['name'],
                        "speed": f"{elapsed:.2f}s",
                        "size": f"{size_mb:.2f} MB",
                        "file": output_file
                    })
                else:
                    print(f"   ⚠️ Link không tải được: HTTP Status {v_res.status_code}")
            else:
                print(f"   ❌ Thất bại: Không lấy được link từ API này.")
        except Exception as e:
            print(f"   ❌ Lỗi ngoại lệ: {e}")

    print("\n" + "="*60)
    print(f"📊 BÁO CÁO TỔNG KẾT ({len(working_apis)}/{len(api_servers)} API hoạt động tốt):")
    if working_apis:
        for item in working_apis:
            print(f"   ✔️ {item['name']} | Tốc độ: {item['speed']} | Dung lượng: {item['size']} -> {item['file']}")
    else:
        print("   ❌ Không có API nào tải được video. Kiểm tra lại RAPIDAPI_KEY hoặc quota tài khoản.")
    print("="*60 + "\n")

if __name__ == "__main__":
    # Hỗ trợ cờ dòng lệnh: python bot.py --test [link]
    if len(sys.argv) > 1 and sys.argv[1] in ['--test', 'test', '-t']:
        if len(sys.argv) > 2:
            test_tiktok_apis(sys.argv[2])
        else:
            while True:
                try:
                    url_input = input("\n👉 Nhập link video TikTok để test (gõ 'q' để dừng): ").strip()
                    if not url_input or url_input.lower() == 'q':
                        print("[*] Kết thúc kiểm tra.")
                        break
                    test_tiktok_apis(url_input)
                except (EOFError, KeyboardInterrupt):
                    break
        sys.exit(0)

    port = int(os.environ.get('PORT', 5000))
    
    # Kiểm tra xem có URL Render không để quyết định dùng webhook hay polling
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    
    if render_url:
        # Chạy trên Render - sử dụng webhook
                # Kiểm tra BOT_TOKEN trước khi chạy bot
        if not BOT_TOKEN:
            print("\n❌ LỖI: BOT_TOKEN chưa được cấu hình trong file .env!")
            print("👉 Để chạy Bot Telegram, vui lòng điền BOT_TOKEN vào file .env.")
            sys.exit(1)
        print("[*] Bot Telegram Tải TikTok 5 Máy Chủ Xoay Tua Đang Hoạt Động...")
        webhook_url = f"{render_url}/webhook"
        print(f"[*] Đang chạy trên Render: {render_url}")
        print(f"[*] Setting webhook: {webhook_url}")
        
        # Xóa webhook cũ nếu có
        bot.remove_webhook()
        
        # Set webhook mới
        bot.set_webhook(url=webhook_url)
        
        # Khởi động thread tự ping giữ bot thức 24/7 trên Render Free Tier
        ping_thread = threading.Thread(target=keep_alive_ping, args=(f"{render_url}/health",))
        ping_thread.daemon = True
        ping_thread.start()
        print(f"[*] Đã kích hoạt cơ chế giữ bot online 24/7 (Anti-Sleep)")
        
        # Chạy Flask app (webhook sẽ tự xử lý)
        app.run(host='0.0.0.0', port=port)
    else:
        # Chạy local
        print("\n" + "="*50)
        print("🤖 CHỌN CHẾ ĐỘ CHẠY TRÊN MÁY (LOCAL):")
        print("1. Chạy Bot Telegram (Mặc định)")
        print("2. Test các API tải video TikTok trong Terminal")
        print("="*50)
        
        choice = "1"
        try:
            choice = input("👉 Nhập lựa chọn (1 hoặc 2, Enter để chạy Bot): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = "1"
            
        if choice == "2":
            while True:
                try:
                    url_input = input("\n👉 Nhập link TikTok cần test (gõ 'q' để thoát): ").strip()
                    if not url_input or url_input.lower() == 'q':
                        print("[*] Kết thúc kiểm tra.")
                        break
                    test_tiktok_apis(url_input)
                except (EOFError, KeyboardInterrupt):
                    break
            sys.exit(0)

        # Chạy local - sử dụng polling
                # Kiểm tra BOT_TOKEN trước khi chạy bot
        if not BOT_TOKEN:
            print("\n❌ LỖI: BOT_TOKEN chưa được cấu hình trong file .env!")
            print("👉 Để chạy Bot Telegram, vui lòng điền BOT_TOKEN vào file .env.")
            sys.exit(1)
        print("[*] Bot Telegram Tải TikTok 5 Máy Chủ Xoay Tua Đang Hoạt Động...")
        print(f"[*] Chạy local với polling")
        
        # Xóa webhook để dùng polling
        bot.delete_webhook()
        print("[*] Đã xóa webhook để chạy polling")
        
        # Chạy Flask server trong thread riêng biệt
        flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port})
        flask_thread.daemon = True
        flask_thread.start()
        
        print(f"[*] Flask server đang chạy trên port {port}")
        print(f"[*] Health check: http://0.0.0.0:{port}/health")
        
        # Chạy Telegram bot với polling
        bot.infinity_polling()
