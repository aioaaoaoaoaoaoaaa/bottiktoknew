import re
import requests
import telebot
import threading
import time
import os
import sys
import json
import uuid

# Cấu hình UTF-8 cho console Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        sys.stdin.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
from dotenv import load_dotenv
from flask import Flask, request

# =======================================================
# 1. TẢI BIẾN MÔI TRƯỜNG & KHỞI TẠO FLASK (CHO CLOUD 24/7)
# =======================================================
load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    return "TikTok Downloader Bot is running 24/7!", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint nhận webhook từ Telegram khi chạy trên Cloud (Render, Railway...)"""
    if request.method == 'POST':
        json_str = request.get_data().decode('UTF-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return "OK", 200
    return "OK", 200


# =======================================================
# HỆ THỐNG QUẢN TRỊ VIÊN (ADMIN), NHẬT KÝ & KHÓA NGƯỜI DÙNG
# =======================================================
ADMIN_IDS = [8581799806, 8774243619]
env_admins = os.getenv("ADMIN_IDS")
if env_admins:
    try:
        ADMIN_IDS.extend([int(x.strip()) for x in env_admins.split(',') if x.strip()])
        ADMIN_IDS = list(set(ADMIN_IDS))
    except Exception:
        pass

BLOCKED_USERS_FILE = "blocked_users.json"
HISTORY_LOGS_FILE = "download_history.json"
MAX_HISTORY_ITEMS = 200

def is_admin(user_id):
    """Kiểm tra xem user_id có thuộc danh sách admin không"""
    if not user_id:
        return False
    return user_id in ADMIN_IDS

def load_blocked_users():
    """Tải danh sách ID người dùng bị khóa"""
    try:
        if os.path.exists(BLOCKED_USERS_FILE):
            with open(BLOCKED_USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[-] Lỗi đọc file blocked_users.json: {e}")
    return {}

def save_blocked_users(data):
    """Lưu danh sách ID người dùng bị khóa"""
    try:
        with open(BLOCKED_USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[-] Lỗi lưu file blocked_users.json: {e}")

def is_user_blocked(user_id):
    """Kiểm tra xem người dùng có bị khóa quyền tải không"""
    if not user_id:
        return False
    if is_admin(user_id):
        return False
    blocked = load_blocked_users()
    return str(user_id) in blocked

def block_user(user_id, reason="Chặn bởi Admin", admin_id=None):
    """Khóa quyền tải của 1 ID Telegram"""
    blocked = load_blocked_users()
    from datetime import datetime, timezone, timedelta
    tz_vn = timezone(timedelta(hours=7))
    time_str = datetime.now(tz_vn).strftime("%H:%M:%S %d/%m/%Y")
    
    blocked[str(user_id)] = {
        "user_id": user_id,
        "reason": reason,
        "blocked_at": time_str,
        "blocked_by": admin_id
    }
    save_blocked_users(blocked)
    return True

def unblock_user(user_id):
    """Mở khóa cho 1 ID Telegram"""
    blocked = load_blocked_users()
    if str(user_id) in blocked:
        del blocked[str(user_id)]
        save_blocked_users(blocked)
        return True
    return False

def load_history_logs():
    """Tải danh sách nhật ký tải video"""
    try:
        if os.path.exists(HISTORY_LOGS_FILE):
            with open(HISTORY_LOGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"[-] Lỗi đọc file download_history.json: {e}")
    return []

def save_history_logs(logs):
    """Lưu danh sách nhật ký tải video"""
    try:
        with open(HISTORY_LOGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[-] Lỗi lưu file download_history.json: {e}")

def record_download_log(user, chat, raw_url, platform, server_name, success, error_msg=""):
    """Ghi nhận chi tiết từng lượt tải video"""
    from datetime import datetime, timezone, timedelta
    tz_vn = timezone(timedelta(hours=7))
    time_str = datetime.now(tz_vn).strftime("%H:%M:%S %d/%m/%Y")

    user_id = user.id if user else "N/A"
    user_name = (user.first_name if user else None) or "Người dùng"
    if user and user.last_name:
        user_name += f" {user.last_name}"
    username = user.username if user else None

    chat_id = chat.id if chat else "N/A"
    chat_title = chat.title if (chat and chat.title) else "Chat riêng"

    log_item = {
        "time": time_str,
        "user_id": user_id,
        "user_name": user_name,
        "username": username,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "platform": platform,
        "url": raw_url,
        "server": server_name,
        "status": "Thành công" if success else "Thất bại",
        "error": error_msg
    }

    logs = load_history_logs()
    logs.insert(0, log_item)
    if len(logs) > MAX_HISTORY_ITEMS:
        logs = logs[:MAX_HISTORY_ITEMS]
    save_history_logs(logs)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN không được tìm thấy trong biến môi trường!")
bot = telebot.TeleBot(BOT_TOKEN)

# Key tài khoản RapidAPI dùng chung
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
if not RAPIDAPI_KEY:
    raise ValueError("RAPIDAPI_KEY không được tìm thấy trong biến môi trường!")

# Biến toàn cầu kiểm soát progress bar
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
# 2. CÁC HÀM BÓC TÁCH LINK TIKTOK (MÁY CHỦ XOAY TUA NÂNG CẤP)
# =======================================================

def call_api_tikwm_direct(tiktok_url):
    """Máy chủ Siêu Cấp: TikWM Direct (Miễn phí, tốc độ cao, hỗ trợ HD không logo 2024-2026)"""
    url = "https://www.tikwm.com/api/"
    params = {"url": tiktok_url, "hd": 1}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=12)
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 0:
                data = res_json.get("data", {})
                # Ưu tiên link hdplay, nếu không có lấy play (không logo)
                play_url = data.get("hdplay") or data.get("play")
                if play_url:
                    if not play_url.startswith("http"):
                        play_url = "https://www.tikwm.com" + play_url
                    caption = data.get("title") or "Video tải từ TikWM Siêu Tốc ⚡"
                    print("[+] TikWM bóc link HD thành công!")
                    return play_url, caption
    except Exception as e:
        print(f"[-] TikWM gặp sự cố: {e}")
    return None, None


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


# =======================================================
# 3. CÁC HÀM BÓC TÁCH LINK FACEBOOK (5 MÁY CHỦ XOAY TUA)
# =======================================================

def call_fb_api_mahmudul(fb_url):
    """FB Máy chủ 1: Facebook Video Downloader by mahmudulhasan62894"""
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
            data_block = res_json.get('data', {})
            video_info = data_block.get('video', {})
            download_block = data_block.get('download', {})
            caption = video_info.get('title') or "Video tải từ Facebook Server 🎬"
            
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
            contents = res_json.get('contents', [])
            if contents:
                videos = contents[0].get('videos', [])
                if videos:
                    video_url = videos[0].get('url')
                    return video_url, "Video tải từ Facebook Server 3 💎"
    except Exception as e:
        print(f"[-] FB API 3 gặp sự cố: {e}")
    return None, None


def call_fb_api_social_download_all_in_one(fb_url):
    """FB Máy chủ 4: Social Download All In One (Lệnh POST - JSON Body)"""
    host = "social-download-all-in-one.p.rapidapi.com"
    url = f"https://{host}/v1/social/autolink"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json"
    }
    payload = {"url": fb_url}
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('links', [{}])[0].get('url')
            caption = res_json.get('title') or "Video tải từ Facebook Server 4 💎"
            if video_url:
                print("[+] FB API 4 (All In One POST) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API 4 gặp sự cố: {e}")
    return None, None


def call_fb_api_media_download_url(fb_url):
    """FB Máy chủ 5: Facebook Media API (Lệnh POST - JSON Body)"""
    host = "facebook-media-api.p.rapidapi.com"
    url = f"https://{host}/media/html"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
        "Content-Type": "application/json"
    }
    payload = {
        "url": fb_url,
        "cookie": ""
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('data', {}).get('url')
            caption = res_json.get('title') or "Video tải từ Facebook Server 5 💎"
            if video_url:
                print("[+] FB API 5 (Media API) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] FB API 5 gặp sự cố: {e}")
    return None, None


# =======================================================
# 4. CÁC HÀM BÓC TÁCH LINK YOUTUBE (3 MÁY CHỦ XOAY TUA)
# =======================================================

def extract_youtube_id(url):
    """Hàm phụ tách lấy ID video từ link YouTube hoặc Shorts bất kỳ"""
    pattern = r"(?:v=|\/shorts\/|\/embed\/|\/v\/|youtu\.be\/|\/watch\?v=)([^#\&\?]*)"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def call_yt_api_datafanatic_details(yt_url):
    """YT Máy chủ 1: YouTube Media Downloader by DataFanatic"""
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        print("[-] Không tìm thấy ID video YouTube hợp lệ.")
        return None, None
        
    host = "youtube-media-downloader.p.rapidapi.com"
    url = f"https://{host}/v2/video/details"
    querystring = {
        "videoId": video_id,
        "urlAccess": "direct",
        "videos": "auto",
        "audios": "auto"
    }
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            caption = res_json.get('title') or "Video tải từ YouTube Server 1 🎥"
            videos_block = res_json.get('videos', {})
            items = videos_block.get('items', [])
            video_url = None
            
            # Vòng 1: Tìm bản Full HD (1080p) hoặc HD (720p) có sẵn tiếng
            for item in items:
                quality = str(item.get('quality', ''))
                if ('1080p' in quality or '720p' in quality) and item.get('hasAudio') is True:
                    video_url = item.get('url')
                    break
            
            # Vòng 2: Bản bất kỳ có sẵn tiếng
            if not video_url:
                for item in items:
                    if item.get('hasAudio') is True:
                        video_url = item.get('url')
                        break
            
            # Vòng 3: Link đầu tiên có sẵn
            if not video_url and items:
                video_url = items[0].get('url')
                
            if video_url:
                print("[+] YT API 1 (DataFanatic Details) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] YT API 1 gặp sự cố: {e}")
    return None, None


def call_yt_api_fast_downloader_v2(yt_url):
    """YT Máy chủ 2: YouTube Video FAST Downloader 24/7"""
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        return None, None
        
    host = "youtube-video-fast-downloader-24-7.p.rapidapi.com"
    url = f"https://{host}/download_video/{video_id}"
    querystring = {"quality": "247"}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host
    }
    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=10)
        if response.status_code == 200:
            res_json = response.json()
            video_url = res_json.get('url') or res_json.get('download_url') or res_json.get('video_url')
            caption = res_json.get('title') or "Video tải từ YouTube FAST Server ⚡"
            if video_url:
                print("[+] YT API 2 (FAST Downloader) bóc link thành công!")
                return video_url, caption
    except Exception as e:
        print(f"[-] YT API 2 gặp sự cố: {e}")
    return None, None


def call_yt_api_shorts_downloader_v3(yt_url):
    """YT Máy chủ 3: YouTube Video And Shorts Downloader"""
    video_id = extract_youtube_id(yt_url)
    if not video_id:
        return None, None
        
    host = "youtube-video-and-shorts-downloader1.p.rapidapi.com"
    url = f"https://{host}/youtube/v3/video/details"
    querystring = {
        "videoId": video_id,
        "urlAccess": "normal",
        "renderableFormats": "720p,highres",
        "getTranscript": "false"
    }
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
                    video_url = None
                    for video in videos:
                        url_item = video.get('url')
                        if url_item and 'tunnel' not in url_item and 'redirector' not in url_item:
                            video_url = url_item
                            break
                    if not video_url:
                        video_url = videos[0].get('url')
                    
                    caption = contents[0].get('title') or "Video tải từ YouTube Server 3 💎"
                    print("[+] YT API 3 (Shorts Downloader) bóc link thành công!")
                    return video_url, caption
    except Exception as e:
        print(f"[-] YT API 3 gặp sự cố: {e}")
    return None, None


# =======================================================
# 5. BỘ TRÍCH XUẤT VÀ KIỂM TRA ĐỊNH DẠNG LINK
# =======================================================


# =======================================================
# CẤU HÌNH & XỬ LÝ RÚT GỌN LINK (LINK999 WIN / APP)
# =======================================================
LINK999_API_TOKEN = os.getenv("LINK999_API_TOKEN", "c4aa527702c6a8fe6cb1d1427bfbb10dbebfddc2")
pending_shorten_links = {}


def format_user_identity(user=None, user_name=None, user_id=None, username=None):
    """Định dạng chuỗi hiển thị: [Tên người gửi] - @username (hoặc None) / [ID tele]"""
    if user:
        name = (user.first_name if user.first_name else None) or "Người dùng"
        if user.last_name:
            name += f" {user.last_name}"
        uname = f"@{user.username}" if user.username else "None"
        uid = str(user.id)
        return f"{name} - {uname} / {uid}"
    else:
        name = user_name or "Người dùng"
        uname = f"@{username}" if (username and username != "None") else "None"
        uid = str(user_id) if user_id else "None"
        return f"{name} - {uname} / {uid}"

def cleanup_pending_links():
    """Dọn dẹp các link tạm quá 1 tiếng để tránh chiếm bộ nhớ"""
    now = time.time()
    expired = [k for k, v in pending_shorten_links.items() if now - v.get("created_at", 0) > 3600]
    for k in expired:
        pending_shorten_links.pop(k, None)

def call_shorten_link999(long_url, domain="app"):
    """
    Rút gọn link qua API link999.app hoặc link999.win
    """
    domain_clean = "win" if domain.lower() == "win" else "app"
    api_url = f"https://link999.{domain_clean}/api"
    params = {
        "api": LINK999_API_TOKEN,
        "url": long_url
    }
    try:
        res = requests.get(api_url, params=params, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success" and data.get("shortenedUrl"):
                return data.get("shortenedUrl"), None
            else:
                return None, data.get("message", "API trả về không thành công")
        return None, f"HTTP Status {res.status_code}"
    except Exception as e:
        return None, str(e)

def prompt_shorten_link(chat_id, user_id, user_name, target_url, original_message_id=None, prefix_text="", username=None, user=None):
    """
    Hiển thị thông báo hỏi người dùng muốn rút gọn với đuôi win hay app
    """
    cleanup_pending_links()
    
    # Tự động xóa tin nhắn gốc chứa link để giữ nhóm sạch sẽ
    if original_message_id:
        try:
            bot.delete_message(chat_id, original_message_id)
        except Exception:
            pass

    link_id = uuid.uuid4().hex[:8]
    pending_shorten_links[link_id] = {
        "url": target_url,
        "user_id": user_id,
        "user_name": user_name,
        "username": username,
        "created_at": time.time()
    }

    # Bàn phím Inline gồm 2 nút: win và app
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn_win = telebot.types.InlineKeyboardButton("🌐 Link999 (.win)", callback_data=f"shorten:win:{link_id}")
    btn_app = telebot.types.InlineKeyboardButton("🌐 Link999 (.app)", callback_data=f"shorten:app:{link_id}")
    markup.add(btn_win, btn_app)

    display_url = target_url
    if len(display_url) > 45:
        display_url = display_url[:42] + "..."

    user_identity = format_user_identity(user=user, user_name=user_name, user_id=user_id, username=username)

    msg_text = (
        f"{prefix_text}"
        f"🔗 <b>Link:</b> <code>{display_url}</code>\n"
        f"👤 <b>Yêu cầu bởi:</b> {user_identity}\n\n"
        f"❓ <b>Bạn muốn rút gọn link với đuôi nào?</b>"
    )
    bot.send_message(chat_id, msg_text, reply_markup=markup, parse_mode="HTML")

TIKTOK_REGEX = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
FACEBOOK_REGEX = r'https?://(?:www\.|web\.|m\.)?(?:facebook\.com|fb\.watch|fb\.com)/[^\s]+'
YOUTUBE_REGEX = r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/|v/)|youtu\.be/)[^\s]+'

GENERAL_URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

def extract_general_url(text):
    """Trích xuất bất kỳ đường link URL nào từ tin nhắn"""
    if not text:
        return None
    match = re.search(GENERAL_URL_REGEX, text, re.IGNORECASE)
    if match:
        url = match.group(0)
        if url.startswith("www."):
            url = "https://" + url
        return url
    return None

def extract_media_url(text):
    """
    Tự động trích xuất link TikTok, Facebook hoặc YouTube từ nội dung tin nhắn.
    Hỗ trợ cả trường hợp gửi link trần hoặc dùng lệnh kèm link: /dl <url>, /down <url>
    """
    if not text:
        return None, None
    
    # 1. Tìm TikTok
    match_tt = re.search(TIKTOK_REGEX, text, re.IGNORECASE)
    if match_tt:
        return match_tt.group(0), 'tiktok'
        
    # 2. Tìm Facebook
    match_fb = re.search(FACEBOOK_REGEX, text, re.IGNORECASE)
    if match_fb:
        return match_fb.group(0), 'facebook'
        
    # 3. Tìm YouTube
    match_yt = re.search(YOUTUBE_REGEX, text, re.IGNORECASE)
    if match_yt:
        return match_yt.group(0), 'youtube'

    return None, None


# =======================================================
# 6. GIAO DIỆN LỆNH & XỬ LÝ TRONG NHÓM CHAT (GROUP & PRIVATE)
# =======================================================

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    help_text = (
        "👋 <b>Chào mừng bạn đến với Bot Tải Video Đa Nền Tảng!</b>\n\n"
        "✨ <b>Cách sử dụng trong Group hoặc Chat riêng:</b>\n"
        "1️⃣ <b>Gửi trực tiếp link:</b> Chỉ cần dán link TikTok, Facebook hoặc YouTube vào khung chat.\n"
        "2️⃣ <b>Dùng lệnh:</b> <code>/dl [link]</code> hoặc <code>/down [link]</code>\n"
        "3️⃣ <b>Reply tin nhắn:</b> Gõ <code>/dl</code> trả lời tin nhắn có chứa link.\n\n"
        "🎬 <i>Bot hỗ trợ bóc tách video HD, không logo, xoay tua nhiều máy chủ tự động!</i>"
    )
    bot.reply_to(message, help_text, parse_mode="HTML")


@bot.message_handler(commands=['dl', 'down', 'tai'])
def handle_download_command(message):
    """
    Xử lý khi thành viên nhóm dùng lệnh:
    - /dl https://vt.tiktok.com/...
    - Hoặc reply vào tin nhắn của người khác rồi gõ /dl
    """
    text = message.text or ""
    # Kiểm tra xem có link sau lệnh không
    parts = text.split(maxsplit=1)
    target_text = parts[1] if len(parts) > 1 else ""

    # Nếu không có link kèm theo lệnh, kiểm tra xem có phải đang reply tin nhắn chứa link không
    if not target_text and message.reply_to_message:
        target_text = message.reply_to_message.text or message.reply_to_message.caption or ""

    url, platform = extract_media_url(target_text)
    if not url:
        bot.reply_to(
            message,
            "⚠️ <b>Cách dùng lệnh tải:</b>\n"
            "• Gõ: <code>/dl [link_video]</code>\n"
            "• Hoặc reply tin nhắn có link rồi gõ <code>/dl</code>",
            parse_mode="HTML"
        )
        return

    process_download_request(message, url, platform)


@bot.message_handler(func=lambda msg: msg.text and extract_media_url(msg.text)[0] is not None)
def handle_direct_url_message(message):
    """
    Tự động bắt link khi thành viên gửi link bất kỳ vào group hoặc chat riêng (không cần gõ lệnh)
    """
    # Nếu tin nhắn là command thì để command handler xử lý
    if message.text.startswith('/'):
        return

    url, platform = extract_media_url(message.text)
    if url:
        process_download_request(message, url, platform)


@bot.channel_post_handler(func=lambda msg: msg.text and extract_media_url(msg.text)[0] is not None)
def handle_channel_post(message):
    """Tự động bắt link khi bài viết được đăng vào Kênh (Channel)"""
    url, platform = extract_media_url(message.text)
    if url:
        process_download_request(message, url, platform)


def process_download_request(message, raw_url, platform):
    """
    Hàm xử lý tải video chung cho cả Chat riêng và Nhóm Chat (Group)
    """
    user_id = message.from_user.id if message.from_user else None
    user_name = (message.from_user.first_name if message.from_user else None) or "bạn"

    # Kiểm tra xem người dùng có bị Admin khóa quyền tải video không
    if user_id and is_user_blocked(user_id):
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass
        blocked_data = load_blocked_users().get(str(user_id), {})
        reason = blocked_data.get("reason", "Chặn bởi Admin")
        bot.send_message(
            message.chat.id,
            f"🚫 <b>{user_name}</b> (ID: <code>{user_id}</code>), bạn đã bị Admin chặn quyền tải video!\n📝 <i>Lý do: {reason}</i>",
            parse_mode="HTML"
        )
        record_download_log(
            user=message.from_user,
            chat=message.chat,
            raw_url=raw_url,
            platform=platform,
            server_name="Bị chặn bởi Admin",
            success=False,
            error_msg=f"User bị khóa: {reason}"
        )
        return

    # Thông báo tiến trình
    status_msg = bot.send_message(
        message.chat.id, 
        f"⏳ Đang xử lý video cho {user_name}...\nTiến trình: 0%"
    )
    
    # Tự động xóa tin nhắn chứa link của người dùng ngay khi bắt đầu gọi API xử lý
    try:
        bot.delete_message(message.chat.id, message.message_id)
        print(f"[+] Đã tự động xóa link video gốc (ID: {message.message_id})")
    except Exception as e:
        print(f"[-] Không thể xóa link video: {e}")
    
    global progress_running
    progress_running = True
    progress_thread = threading.Thread(target=progress_bar, args=(message.chat.id, status_msg.message_id))
    progress_thread.start()

    # Mở link rút gọn điện thoại cho TikTok nếu có
    if "vt.tiktok.com" in raw_url or "vm.tiktok.com" in raw_url:
        try:
            resp = requests.head(raw_url, allow_redirects=True, timeout=6)
            raw_url = resp.url
        except Exception:
            pass

    # Phân nhóm máy chủ theo nền tảng
    if platform == 'tiktok':
        api_servers = [
            {"name": "TikTok VIP 1 (TikWM HD Direct)", "func": call_api_tikwm_direct},
            {"name": "TikTok 2 (No Watermark HD)", "func": call_api_4_no_watermark2},
            {"name": "TikTok 3 (Scrapper)", "func": call_api_1_scrapper},
            {"name": "TikTok 4 (7scorp)", "func": call_api_5_7scorp},
            {"name": "TikTok 5 (Social Media)", "func": call_api_2_social_media},
            {"name": "TikTok 6 (API23)", "func": call_api_3_tiktok_api23}
        ]
    elif platform == 'facebook':
        api_servers = [
            {"name": "FB 1 (Mahmudul HD/SD)", "func": call_fb_api_mahmudul},
            {"name": "FB 2 (Full Downloader)", "func": call_fb_api_full_downloader},
            {"name": "FB 3 (Social Media V3 HD)", "func": call_fb_api_social_media_v3},
            {"name": "FB 4 (All In One POST)", "func": call_fb_api_social_download_all_in_one},
            {"name": "FB 5 (Media API)", "func": call_fb_api_media_download_url}
        ]
    else:
        api_servers = [
            {"name": "YouTube 1 (DataFanatic)", "func": call_yt_api_datafanatic_details},
            {"name": "YouTube 2 (FAST 24/7)", "func": call_yt_api_fast_downloader_v2},
            {"name": "YouTube 3 (Shorts V3)", "func": call_yt_api_shorts_downloader_v3}
        ]

    video_link, caption = None, None
    successful_server = None

    # Cơ chế xoay tua (Fallback)
    for server in api_servers:
        uid = message.from_user.id if message.from_user else "Channel"
        print(f"[*] Group {message.chat.id} | User {uid} -> Thử qua: {server['name']}...")
        video_link, caption = server["func"](raw_url)
        if video_link:
            successful_server = server["name"]
            print(f"[+] Thành công tại {server['name']}.")
            break
        print(f"[-] {server['name']} thất bại, thử tiếp...")

    progress_running = False

    if video_link:
        try:
            bot.edit_message_text("Đợi xíu video sẽ hiện sau ít giây", chat_id=message.chat.id, message_id=status_msg.message_id)
            
            # Gửi video thành phẩm
            final_caption = f"🎬 <b>Video cho {user_name}:</b>\n\n{caption}" if caption else f"🎬 <b>Video cho {user_name}</b>"
            try:
                bot.send_video(
                    chat_id=message.chat.id,
                    video=video_link,
                    caption=final_caption,
                    parse_mode="HTML"
                )
            except Exception:
                bot.send_video(
                    chat_id=message.chat.id,
                    video=video_link,
                    caption=caption if caption else "🎬 Video đã được tải thành công!"
                )
            # Ghi nhận nhật ký tải thành công
            record_download_log(
                user=message.from_user,
                chat=message.chat,
                raw_url=raw_url,
                platform=platform,
                server_name=successful_server,
                success=True
            )
            # Xóa tin nhắn trạng thái cho nhóm đỡ loãng
            bot.delete_message(message.chat.id, status_msg.message_id)
            print(f"[+] Đã gửi video thành công vào group {message.chat.id}!")
        except Exception as e:
            print(f"[-] Lỗi gửi video vào group: {e}")
            bot.edit_message_text(
                f"❌ Lỗi khi gửi video vào nhóm: {e}",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )
    else:
        record_download_log(
            user=message.from_user,
            chat=message.chat,
            raw_url=raw_url,
            platform=platform,
            server_name="Tất cả máy chủ thất bại",
            success=False,
            error_msg="Không máy chủ nào bóc được link (chuyển sang rút gọn)"
        )
        # Xóa tin nhắn trạng thái cũ
        try:
            bot.delete_message(message.chat.id, status_msg.message_id)
        except Exception:
            pass
            
        # Tự động chuyển sang chức năng rút gọn link khi không tải được video
        username = message.from_user.username if (message.from_user and message.from_user.username) else "None"
        prompt_shorten_link(
            chat_id=message.chat.id,
            user_id=user_id,
            user_name=user_name,
            target_url=raw_url,
            prefix_text="⚠️ <b>Không thể tải trực tiếp video từ link này.</b>\n👉 <i>Tự động chuyển sang chức năng rút gọn link:</i>\n\n",
            username=username,
            user=message.from_user
        )



# =======================================================
# BỘ LỆNH ĐIỀU KHIỂN DÀNH CHO ADMIN
# =======================================================


# -------------------------------------------------------
# XỬ LÝ RÚT GỌN LINK THƯỜNG & NÚT BẤM WIN / APP
# -------------------------------------------------------

@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith('/') and extract_media_url(msg.text)[0] is None and extract_general_url(msg.text) is not None)
def handle_general_url_message(message):
    """Tự động bắt link thông thường (không phải TikTok, FB, YT) để hỏi rút gọn link"""
    gen_url = extract_general_url(message.text)
    if gen_url:
        user_id = message.from_user.id if message.from_user else None
        user_name = (message.from_user.first_name if message.from_user else None) or "bạn"
        
        # Kiểm tra người dùng có bị khóa không
        if user_id and is_user_blocked(user_id):
            try:
                bot.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
            return

        username = message.from_user.username if (message.from_user and message.from_user.username) else "None"
        prompt_shorten_link(
            chat_id=message.chat.id,
            user_id=user_id,
            user_name=user_name,
            target_url=gen_url,
            original_message_id=message.message_id,
            username=username,
            user=message.from_user
        )


@bot.channel_post_handler(func=lambda msg: msg.text and extract_media_url(msg.text)[0] is None and extract_general_url(msg.text) is not None)
def handle_general_channel_post(message):
    """Tự động bắt link thông thường trong Kênh để hỏi rút gọn link"""
    gen_url = extract_general_url(message.text)
    if gen_url:
        prompt_shorten_link(
            chat_id=message.chat.id,
            user_id=None,
            user_name="Kênh",
            target_url=gen_url,
            original_message_id=message.message_id
        )


@bot.message_handler(commands=['shorten', 'rutgon'])
def handle_shorten_command(message):
    """Lệnh rút gọn link thủ công: /shorten <link>"""
    text = message.text or ""
    parts = text.split(maxsplit=1)
    target_text = parts[1] if len(parts) > 1 else ""
    if not target_text and message.reply_to_message:
        target_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    gen_url = extract_general_url(target_text)
    if not gen_url:
        bot.reply_to(message, "⚠️ <b>Cách dùng:</b> <code>/shorten [link]</code> hoặc reply tin nhắn chứa link rồi gõ <code>/shorten</code>", parse_mode="HTML")
        return
        
    user_id = message.from_user.id if message.from_user else None
    user_name = (message.from_user.first_name if message.from_user else None) or "bạn"
    username = message.from_user.username if (message.from_user and message.from_user.username) else "None"
    prompt_shorten_link(
        chat_id=message.chat.id,
        user_id=user_id,
        user_name=user_name,
        target_url=gen_url,
        username=username,
        user=message.from_user
    )


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith('shorten:'))
def handle_shorten_callback(call):
    """Xử lý sự kiện khi người dùng bấm nút win hoặc app"""
    parts = call.data.split(':')
    if len(parts) != 3:
        bot.answer_callback_query(call.id, "Dữ liệu không hợp lệ")
        return
        
    domain_choice = parts[1]  # "win" hoặc "app"
    link_id = parts[2]
    
    link_data = pending_shorten_links.get(link_id)
    if not link_data:
        bot.answer_callback_query(call.id, "⚠️ Yêu cầu đã hết hạn! Vui lòng gửi lại link.", show_alert=True)
        try:
            bot.edit_message_text(
                "⚠️ <i>Yêu cầu rút gọn link đã hết hạn. Vui lòng gửi lại link để thực hiện.</i>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML"
            )
        except Exception:
            pass
        return
        
    target_url = link_data["url"]
    clicker_name = (call.from_user.first_name if call.from_user else None) or "Người dùng"
    
    bot.answer_callback_query(call.id, f"Đang rút gọn với Link999 .{domain_choice}...")
    
    try:
        bot.edit_message_text(
            f"⏳ <b>Đang tạo link rút gọn với Link999 (.{domain_choice})...</b>",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )
    except Exception:
        pass
        
    shortened_url, err = call_shorten_link999(target_url, domain=domain_choice)
    
    if shortened_url:
        record_download_log(
            user=call.from_user,
            chat=call.message.chat,
            raw_url=target_url,
            platform=f"shorten_{domain_choice}",
            server_name=f"Link999 (.{domain_choice})",
            success=True
        )
        
        pending_shorten_links.pop(link_id, None)
        
        markup = telebot.types.InlineKeyboardMarkup()
        markup.add(telebot.types.InlineKeyboardButton("🚀 Mở Link Rút Gọn", url=shortened_url))
        
        creator_info = format_user_identity(user=call.from_user)
        result_text = (
            f"✅<b>Success</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Link gốc:</b> {target_url}\n"
            f"🌐 <b>Host:</b> link999.{domain_choice}\n"
            f"👉 <b>Link rút gọn:</b> <code>{shortened_url}</code>\n\n"
            f"👤 <b>Creator:</b> {creator_info}"
        )
        bot.edit_message_text(
            result_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode="HTML"
        )
    else:
        record_download_log(
            user=call.from_user,
            chat=call.message.chat,
            raw_url=target_url,
            platform=f"shorten_{domain_choice}",
            server_name=f"Link999 (.{domain_choice})",
            success=False,
            error_msg=err or "Lỗi rút gọn"
        )
        bot.edit_message_text(
            f"❌ <b>Không thể rút gọn link:</b> {err or 'Lỗi kết nối'}\n"
            f"Vui lòng thử lại sau hoặc thử với tên miền khác!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="HTML"
        )


@bot.message_handler(commands=['admin', 'panel'])
def handle_admin_panel(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    help_admin = (
        "👑 <b>BẢNG ĐIỀU KHIỂN QUẢN TRỊ VIÊN (ADMIN)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>XEM NHẬT KÝ & LỊCH SỬ TẢI:</b>\n"
        "• <code>/history</code> hoặc <code>/log</code> : Xem 5 lượt tải gần nhất\n"
        "• <code>/history [số]</code> : Xem số lượt tải tùy chọn (VD: <code>/history 15</code>)\n"
        "• <code>/history user [id]</code> : Xem lịch sử của 1 người (VD: <code>/history user 8581799806</code>)\n\n"
        "🚫 <b>QUẢN LÝ CHẶN / MỞ KHÓA NGƯỜI DÙNG:</b>\n"
        "• <code>/block [id] [lý do]</code> : Khóa quyền tải video của ID đó\n"
        "  <i>(Hoặc reply tin nhắn bất kỳ của người đó rồi gõ /block)</i>\n"
        "• <code>/unblock [id]</code> : Mở khóa cho ID đó\n"
        "• <code>/blocklist</code> : Xem danh sách người dùng đang bị khóa\n\n"
        "📊 <b>THỐNG KÊ HOẠT ĐỘNG:</b>\n"
        "• <code>/stats</code> hoặc <code>/thongke</code> : Thống kê tổng quan lượt tải & các máy chủ API"
    )
    bot.reply_to(message, help_admin, parse_mode="HTML")


@bot.message_handler(commands=['history', 'log', 'logs', 'lichsu'])
def handle_admin_history(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    text = message.text.strip()
    parts = text.split()
    
    limit = 5
    filter_user_id = None
    
    if len(parts) >= 3 and parts[1].lower() in ['user', 'u']:
        try:
            filter_user_id = int(parts[2])
        except ValueError:
            bot.reply_to(message, "❌ ID không hợp lệ. Ví dụ: <code>/history user 123456789</code>", parse_mode="HTML")
            return
        limit = 10
    elif len(parts) >= 2:
        arg = parts[1]
        try:
            val = int(arg)
            if val > 100000:
                filter_user_id = val
                limit = 10
            else:
                limit = min(val, 20)
        except ValueError:
            pass

    logs = load_history_logs()
    if filter_user_id:
        logs = [x for x in logs if str(x.get("user_id")) == str(filter_user_id)]

    if not logs:
        msg = f"📭 Chưa có nhật ký nào" + (f" cho user ID: <code>{filter_user_id}</code>." if filter_user_id else ".")
        bot.reply_to(message, msg, parse_mode="HTML")
        return

    target_logs = logs[:limit]
    total_found = len(logs)
    
    title = f"📜 <b>NHẬT KÝ TẢI VIDEO ({len(target_logs)}/{total_found} lượt):</b>\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    items_text = []

    for idx, item in enumerate(target_logs, 1):
        status_icon = "✅" if item.get("status") == "Thành công" else "❌"
        u_info = f"{item.get('user_name')} (ID: <code>{item.get('user_id')}</code>)"
        if item.get("username"):
            u_info += f" [@{item.get('username')}]"
            
        chat_info = f"{item.get('chat_title')} (ID: <code>{item.get('chat_id')}</code>)"
        url_short = item.get('url', '')
        if len(url_short) > 42:
            url_short = url_short[:39] + "..."

        block = (
            f"<b>{idx}. {status_icon} [{item.get('time')}]</b>\n"
            f"👤 <b>Người tải:</b> {u_info}\n"
            f"🏠 <b>Nhóm chat:</b> {chat_info}\n"
            f"⚙️ <b>Server API:</b> <code>{item.get('server')}</code>\n"
            f"🔗 <b>Link:</b> {url_short}\n"
            f"📊 <b>Trạng thái:</b> <b>{item.get('status')}</b>"
        )
        if item.get("error"):
            block += f"\n⚠️ <i>Lỗi: {item.get('error')}</i>"
        items_text.append(block)

    full_response = title + "\n\n────────────────\n\n".join(items_text)
    if len(full_response) > 4000:
        bot.reply_to(message, full_response[:4000], parse_mode="HTML")
    else:
        bot.reply_to(message, full_response, parse_mode="HTML")


@bot.message_handler(commands=['block', 'khoa', 'ban'])
def handle_admin_block(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    target_id = None
    reason = "Chặn bởi Admin"

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            reason = parts[1]
    else:
        parts = message.text.split(maxsplit=2)
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
                if len(parts) > 2:
                    reason = parts[2]
            except ValueError:
                bot.reply_to(message, "❌ ID không hợp lệ. Cú pháp: <code>/block [id] [lý do]</code>", parse_mode="HTML")
                return

    if not target_id:
        bot.reply_to(
            message,
            "⚠️ <b>Cú pháp lệnh chặn:</b>\n"
            "• Gõ: <code>/block [id_người_dùng] [lý do]</code>\n"
            "• Hoặc reply tin nhắn của người đó rồi gõ: <code>/block [lý do]</code>",
            parse_mode="HTML"
        )
        return

    if is_admin(target_id):
        bot.reply_to(message, "⚠️ Không thể khóa tài khoản của Quản trị viên (Admin)!", parse_mode="HTML")
        return

    block_user(target_id, reason, admin_id=user_id)
    bot.reply_to(
        message,
        f"🚫 <b>ĐÃ KHÓA NGƯỜI DÙNG THÀNH CÔNG!</b>\n"
        f"• <b>ID Telegram:</b> <code>{target_id}</code>\n"
        f"• <b>Lý do:</b> {reason}\n\n"
        f"<i>Người này từ bây giờ sẽ bị chặn, không thể tải video được nữa.</i>",
        parse_mode="HTML"
    )


@bot.message_handler(commands=['unblock', 'mokhoa', 'unban'])
def handle_admin_unblock(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    target_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
    else:
        parts = message.text.split()
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
            except ValueError:
                bot.reply_to(message, "❌ ID không hợp lệ. Cú pháp: <code>/unblock [id]</code>", parse_mode="HTML")
                return

    if not target_id:
        bot.reply_to(message, "⚠️ Cú pháp: <code>/unblock [id]</code> hoặc reply tin nhắn gõ <code>/unblock</code>", parse_mode="HTML")
        return

    if unblock_user(target_id):
        bot.reply_to(message, f"✅ <b>ĐÃ MỞ KHÓA THÀNH CÔNG!</b>\nNgười dùng <code>{target_id}</code> đã có thể tiếp tục tải video.", parse_mode="HTML")
    else:
        bot.reply_to(message, f"ℹ️ Người dùng <code>{target_id}</code> hiện không có trong danh sách bị khóa.", parse_mode="HTML")


@bot.message_handler(commands=['blocklist', 'dskhoa', 'listblock'])
def handle_admin_blocklist(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    blocked = load_blocked_users()
    if not blocked:
        bot.reply_to(message, "✅ <b>Hiện tại không có ID người dùng nào bị khóa!</b>", parse_mode="HTML")
        return

    res = [f"🚫 <b>DANH SÁCH NGƯỜI DÙNG BỊ KHÓA ({len(blocked)} người):</b>\n━━━━━━━━━━━━━━━━━━━━━━\n"]
    for idx, (uid, info) in enumerate(blocked.items(), 1):
        res.append(
            f"<b>{idx}. ID:</b> <code>{uid}</code>\n"
            f"   ⏰ Thời gian: {info.get('blocked_at', 'N/A')}\n"
            f"   📝 Lý do: {info.get('reason', 'N/A')}\n"
            f"   👮 Người khóa: <code>{info.get('blocked_by', 'Admin')}</code>"
        )

    bot.reply_to(message, "\n\n".join(res), parse_mode="HTML")


@bot.message_handler(commands=['stats', 'thongke'])
def handle_admin_stats(message):
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        bot.reply_to(message, "⛔ <b>Lệnh này chỉ dành riêng cho Admin!</b>", parse_mode="HTML")
        return

    logs = load_history_logs()
    blocked = load_blocked_users()
    
    total_reqs = len(logs)
    success_reqs = sum(1 for x in logs if x.get("status") == "Thành công")
    fail_reqs = total_reqs - success_reqs
    rate = (success_reqs / total_reqs * 100) if total_reqs > 0 else 0

    server_counts = {}
    user_counts = {}
    for item in logs:
        srv = item.get("server", "Khác")
        server_counts[srv] = server_counts.get(srv, 0) + 1
        
        uid = str(item.get("user_id"))
        user_counts[uid] = user_counts.get(uid, 0) + 1

    srv_text = []
    for srv, cnt in sorted(server_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
        srv_text.append(f"• <code>{srv}</code>: <b>{cnt}</b> lượt")

    stats_msg = (
        "📊 <b>THỐNG KÊ HOẠT ĐỘNG BOT TIKTOK</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 <b>Tổng số yêu cầu đã ghi nhận:</b> {total_reqs}\n"
        f"✅ <b>Thành công:</b> {success_reqs} ({rate:.1f}%)\n"
        f"❌ <b>Thất bại:</b> {fail_reqs}\n"
        f"👥 <b>Số người dùng đã tương tác:</b> {len(user_counts)}\n"
        f"🚫 <b>Số người dùng đang bị khóa:</b> {len(blocked)}\n\n"
        "⚙️ <b>TẦN SUẤT SỬ DỤNG CÁC MÁY CHỦ API:</b>\n" +
        ("\n".join(srv_text) if srv_text else "Chưa có dữ liệu")
    )
    bot.reply_to(message, stats_msg, parse_mode="HTML")


def keep_alive_ping(url):
    """Tự động gửi request ping đến /health mỗi 10 phút để Render không bị tắt (Sleep mode)"""
    while True:
        time.sleep(600)  # 10 phút
        try:
            requests.get(url, timeout=10)
            print(f"[Keep-Alive] Ping thành công tới {url}")
        except Exception as e:
            print(f"[Keep-Alive] Lỗi ping: {e}")


if __name__ == "__main__":
    print("[*] Bot Tải Video Đa Nền Tảng Cho Group & Chat Riêng Đang Khởi Động...")
    port = int(os.environ.get('PORT', 5000))
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    
    if render_url:
        # Chạy trên Render / Cloud có domain ngoài (Webhook mode)
        webhook_url = f"{render_url}/webhook"
        print(f"[*] Đang chạy trên Cloud: {render_url}")
        print(f"[*] Đang gắn webhook: {webhook_url}")
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        
        # Khởi động thread tự ping giữ bot thức 24/7 trên Render Free Tier
        ping_thread = threading.Thread(target=keep_alive_ping, args=(f"{render_url}/health",))
        ping_thread.daemon = True
        ping_thread.start()
        print(f"[*] Đã kích hoạt cơ chế giữ bot online 24/7 (Anti-Sleep)")
        
        app.run(host='0.0.0.0', port=port)
    else:
        # Chạy local hoặc VPS qua Polling
        print(f"[*] Đang chạy chế độ Polling (Local/VPS)")
        bot.delete_webhook()
        
        # Chạy ngầm Flask webserver cho health check (bọc try-except tránh xung đột port)
        def run_flask_safe():
            try:
                app.run(host='0.0.0.0', port=port)
            except Exception as e:
                print(f"[*] Cảnh báo Flask port {port}: {e}")

        flask_thread = threading.Thread(target=run_flask_safe)
        flask_thread.daemon = True
        flask_thread.start()
        
        print(f"[*] Web Server lắng nghe tại cổng {port}")
        bot.infinity_polling()


