import re
import requests
import telebot
import threading
import time
import os
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

TIKTOK_REGEX = r'https?://(?:www\.|vm\.|vt\.)?tiktok\.com/[^\s]+'
FACEBOOK_REGEX = r'https?://(?:www\.|web\.|m\.)?(?:facebook\.com|fb\.watch|fb\.com)/[^\s]+'
YOUTUBE_REGEX = r'https?://(?:www\.)?(?:youtube\.com/(?:watch\?v=|shorts/|embed/|v/)|youtu\.be/)[^\s]+'

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
    # Thông báo tiến trình
    user_name = (message.from_user.first_name if message.from_user else None) or "bạn"
    status_msg = bot.reply_to(
        message, 
        f"⏳ Đang xử lý video cho {user_name}...\nTiến trình: 0%"
    )
    
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

    # Cơ chế xoay tua (Fallback)
    for server in api_servers:
        uid = message.from_user.id if message.from_user else "Channel"
        print(f"[*] Group {message.chat.id} | User {uid} -> Thử qua: {server['name']}...")
        video_link, caption = server["func"](raw_url)
        if video_link:
            print(f"[+] Thành công tại {server['name']}.")
            break
        print(f"[-] {server['name']} thất bại, thử tiếp...")

    progress_running = False

    if video_link:
        try:
            bot.edit_message_text(f"✅ Đã tải xong video cho {user_name}! Đang gửi...", chat_id=message.chat.id, message_id=status_msg.message_id)
            
            # Gửi video dưới dạng reply lại tin nhắn người gửi trong nhóm
            bot.send_video(
                chat_id=message.chat.id,
                video=video_link,
                caption=caption if caption else "🎬 Video đã được tải thành công!",
                reply_to_message_id=message.message_id
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
        bot.edit_message_text(
            "💥 Không thể lấy được video từ link này (máy chủ bận hoặc link riêng tư/không hỗ trợ). Vui lòng thử lại sau!",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )


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
        
        # Chạy ngầm Flask webserver cho health check
        flask_thread = threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': port})
        flask_thread.daemon = True
        flask_thread.start()
        
        print(f"[*] Web Server lắng nghe tại cổng {port}")
        bot.infinity_polling()


