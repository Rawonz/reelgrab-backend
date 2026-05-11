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


def get_cookie_file():
    """YT_COOKIES env variable varsa geçici bir dosyaya yazar, path döndürür."""
    cookies_content = os.environ.get("YT_COOKIES", "")
    if not cookies_content.strip():
        return None
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
    tmp.write(cookies_content)
    tmp.close()
    return tmp.name


def get_ydl_opts(kalite="1080", mp3=False, filepath=None):
    cookie_file = get_cookie_file()

    base = {
        "outtmpl": filepath or f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "quiet": True,
    }

    if cookie_file:
        base["cookiefile"] = cookie_file

    if mp3:
        base["format"] = "bestaudio/best"
        base["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }]
    else:
        base["format"] = f"bestvideo[height<={kalite}]+bestaudio/best/best[height<={kalite}]"
        base["merge_output_format"] = "mp4"

    return base


@app.route("/", methods=["GET"])
def index():
    return jsonify({"durum": "ReelGrab API çalışıyor 🎬"})


@app.route("/analiz", methods=["POST"])
def analiz():
    url = request.json.get("url", "").strip()
    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    cookie_file = get_cookie_file()
    ydl_opts = {"quiet": True, "skip_download": True}
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

    # Her indirme için benzersiz dosya adı
    unique_id = str(uuid.uuid4())[:8]
    ext = "mp3" if mp3 else "mp4"
    filepath = f"{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s"

    opts = get_ydl_opts(kalite=kalite, mp3=mp3, filepath=filepath)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "video")

        # İndirilen dosyayı bul
        for fname in os.listdir(DOWNLOAD_FOLDER):
            if fname.startswith(unique_id):
                fpath = os.path.join(DOWNLOAD_FOLDER, fname)
                safe_title = "".join(c for c in title if c.isalnum() or c in " _-")[:60]
                download_name = f"{safe_title}.{fname.split('.')[-1]}"
                response = send_file(
                    fpath,
                    as_attachment=True,
                    download_name=download_name
                )
                # Gönderdikten sonra sil
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
