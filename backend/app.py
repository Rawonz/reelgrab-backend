import os
import tempfile
import uuid
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "./downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


def get_cookie_file(platform="youtube"):
    if platform == "instagram":
        content = os.environ.get("IG_COOKIES", "")
    else:
        content = os.environ.get("YT_COOKIES", "")
    if not content.strip():
        return None
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(content)
    tmp.close()
    return tmp.name


def detect_platform(url):
    if "instagram.com" in url:
        return "instagram"
    elif "tiktok.com" in url:
        return "tiktok"
    return "youtube"


def get_ydl_opts(url, kalite="1080", mp3=False, filepath=None):
    platform = detect_platform(url)
    cookie_file = get_cookie_file(platform)

    base = {
        "outtmpl": filepath or f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "quiet": True,
        "no_warnings": True,
    }

    if cookie_file:
        base["cookiefile"] = cookie_file

    if mp3:
        # ffmpeg varsa MP3'e çevir, yoksa ham audio indir
        base["format"] = "bestaudio/best"
        base["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        kalite = str(kalite)
        # Progressive (birleşik) stream — ffmpeg gerektirmez
        if kalite in ["4k", "2160"]:
            base["format"] = "best[height<=2160][ext=mp4]/best[ext=mp4]/best"
        elif kalite == "1080":
            base["format"] = "best[height<=1080][ext=mp4]/best[ext=mp4]/best"
        elif kalite == "720":
            base["format"] = "best[height<=720][ext=mp4]/best[ext=mp4]/best"
        else:
            base["format"] = "best[height<=480][ext=mp4]/best[ext=mp4]/best"

        # TikTok için filigransız kaynak
        if platform == "tiktok":
            base["extractor_args"] = {"tiktok": {"webpage_download": ["1"]}}

    return base


@app.route("/", methods=["GET"])
def index():
    return jsonify({"durum": "ReelGrab API çalışıyor 🎬"})


@app.route("/analiz", methods=["POST"])
def analiz():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    platform = detect_platform(url)
    cookie_file = get_cookie_file(platform)
    ydl_opts = {"quiet": True, "skip_download": True, "no_warnings": True}
    if cookie_file:
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "baslik": info.get("title", "Bilinmiyor"),
                "sure":   info.get("duration_string", "?"),
                "thumb":  info.get("thumbnail", ""),
                "kanal":  info.get("uploader", ""),
            })
    except Exception as e:
        return jsonify({"hata": str(e)}), 400


@app.route("/indir", methods=["POST"])
def indir():
    url    = request.json.get("url", "").strip()
    kalite = request.json.get("kalite", "1080")
    mp3    = request.json.get("mp3", False)

    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    unique_id = str(uuid.uuid4())[:8]
    filepath = f"{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s"
    opts = get_ydl_opts(url=url, kalite=kalite, mp3=mp3, filepath=filepath)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        for fname in os.listdir(DOWNLOAD_FOLDER):
            if fname.startswith(unique_id):
                fpath = os.path.join(DOWNLOAD_FOLDER, fname)
                safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:60]
                download_name = f"{safe_title}.{fname.split('.')[-1]}"
                response = send_file(fpath, as_attachment=True, download_name=download_name)

                @response.call_on_close
                def cleanup():
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
                return response

        return jsonify({"hata": "Dosya bulunamadı"}), 500

    except Exception as e:
        return jsonify({"hata": str(e)}), 400


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
