import os
import uuid
import shutil
import tempfile
import yt_dlp

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "/tmp/reelgrab_downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def ffmpeg_installed():
    return shutil.which("ffmpeg") is not None


def get_cookie_file():
    """Railway'de YT_COOKIES environment variable'dan cookie dosyası oluşturur."""
    cookies_content = os.environ.get("YT_COOKIES", "")
    if not cookies_content:
        return None
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(cookies_content)
    tmp.close()
    return tmp.name


def build_ydl_opts(quality="1080", mp3=False, outtmpl=None):
    """Tüm platformlar için yt-dlp ayarları. Cookie varsa kullanır, yoksa devam eder."""
    cookie_file = get_cookie_file()

    opts = {
        "outtmpl": outtmpl or f"{DOWNLOAD_DIR}/%(id)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        # Bot tespitini azaltmak için
        "sleep_interval": 1,
        "max_sleep_interval": 3,
    }

    if cookie_file:
        opts["cookiefile"] = cookie_file

    if mp3:
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    else:
        # Kaliteye göre format seç
        q = int(quality) if quality.isdigit() else 1080
        opts["format"] = f"bestvideo[height<={q}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={q}]+bestaudio/best[height<={q}]/best"
        opts["merge_output_format"] = "mp4"

    return opts


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "ffmpeg": ffmpeg_installed(),
        "cookies": bool(os.environ.get("YT_COOKIES"))
    })


# ─────────────────────────────────────────
# ANALİZ
# ─────────────────────────────────────────
@app.route("/analiz", methods=["POST"])
def analiz():
    data = request.get_json()
    url = (data or {}).get("url", "").strip()

    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    cookie_file = get_cookie_file()
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    }
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Süreyi okunabilir formata çevir
        duration = info.get("duration", 0)
        if duration:
            mins = int(duration) // 60
            secs = int(duration) % 60
            sure_str = f"{mins}:{secs:02d}"
        else:
            sure_str = info.get("duration_string", "—")

        return jsonify({
            "baslik": info.get("title", "Video"),
            "thumbnail": info.get("thumbnail", ""),
            "sure": sure_str,
            "platform": info.get("extractor_key", ""),
        })

    except Exception as e:
        hata = str(e)
        # Daha anlaşılır hata mesajları
        if "Sign in" in hata or "bot" in hata.lower():
            hata = "YouTube bot koruması devrede. YT_COOKIES environment variable'ını ekle."
        elif "Private video" in hata:
            hata = "Bu video özel, indirilemez."
        elif "not available" in hata:
            hata = "Bu video bölgenizde mevcut değil."
        return jsonify({"hata": hata}), 500


# ─────────────────────────────────────────
# İNDİR
# ─────────────────────────────────────────
@app.route("/indir", methods=["POST"])
def indir():
    data = request.get_json()
    url     = (data or {}).get("url", "").strip()
    quality = (data or {}).get("kalite", "1080")
    mp3     = (data or {}).get("mp3", False)

    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    uid = str(uuid.uuid4())[:8]
    ext = "mp3" if mp3 else "mp4"
    outtmpl = f"{DOWNLOAD_DIR}/{uid}.%(ext)s"

    try:
        opts = build_ydl_opts(quality=quality, mp3=mp3, outtmpl=outtmpl)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # İndirilen dosyayı bul
        file_path = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(uid):
                file_path = os.path.join(DOWNLOAD_DIR, f)
                break

        if not file_path or not os.path.exists(file_path):
            return jsonify({"hata": "Dosya oluşturulamadı"}), 500

        # Temiz dosya adı
        title = info.get("title", "video")[:80]
        # Güvenli karakter filtresi
        safe_title = "".join(c for c in title if c.isalnum() or c in " ._-ğüşıöçĞÜŞİÖÇ").strip()
        download_name = f"{safe_title}.{ext}"

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="audio/mpeg" if mp3 else "video/mp4"
        )

        # Gönderdikten sonra dosyayı sil
        @response.call_on_close
        def cleanup():
            try:
                os.remove(file_path)
            except Exception:
                pass

        return response

    except Exception as e:
        hata = str(e)
        if "Sign in" in hata or "bot" in hata.lower():
            hata = "YouTube bot koruması devrede. Cookie eklemen gerekiyor."
        elif "Private video" in hata:
            hata = "Bu video özel, indirilemez."
        return jsonify({"hata": hata}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
