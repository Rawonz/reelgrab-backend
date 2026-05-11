import os
import uuid
import shutil
import yt_dlp

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def ffmpeg_installed():
    return shutil.which("ffmpeg") is not None


# -------------------------
# HEALTH CHECK
# -------------------------
@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "ffmpeg": ffmpeg_installed()
    })


# -------------------------
# ANALİZ ENDPOINT (FRONTEND BUNU BEKLİYOR)
# -------------------------
@app.route("/analiz", methods=["POST"])
def analiz():
    data = request.json
    url = data.get("url")

    if not url:
        return jsonify({"hata": "URL boş"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "noplaylist": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return jsonify({
            "baslik": info.get("title", "Video"),
            "thumbnail": info.get("thumbnail"),
            "sure": info.get("duration")
        })

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


# -------------------------
# DOWNLOAD ENDPOINT (FRONTEND /indir ÇAĞIRIYOR)
# -------------------------
@app.route("/indir", methods=["POST"])
def indir():
    data = request.json

    url = data.get("url")
    quality = data.get("kalite", "1080")
    mp3 = data.get("mp3", False)

    if not url:
        return jsonify({"hata": "URL boş"}), 400

    uid = str(uuid.uuid4())[:8]
    output = f"{DOWNLOAD_DIR}/{uid}.%(ext)s"

    try:

        if mp3:
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output,
                "noplaylist": True,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }]
            }
        else:
            fmt = "best"
            if quality == "2160":
                fmt = "bv*[height<=2160]+ba"
            elif quality == "1440":
                fmt = "bv*[height<=1440]+ba"
            elif quality == "1080":
                fmt = "bv*[height<=1080]+ba"
            elif quality == "720":
                fmt = "bv*[height<=720]+ba"

            ydl_opts = {
                "format": fmt,
                "outtmpl": output,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        file_path = None
        for f in os.listdir(DOWNLOAD_DIR):
            if f.startswith(uid):
                file_path = os.path.join(DOWNLOAD_DIR, f)
                break

        if not file_path:
            return jsonify({"hata": "dosya bulunamadı"}), 500

        response = send_file(file_path, as_attachment=True)

        @response.call_on_close
        def cleanup():
            try:
                os.remove(file_path)
            except:
                pass

        return response

    except Exception as e:
        return jsonify({"hata": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
