import os
import uuid
import shutil
import yt_dlp

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

PORT = int(os.environ.get("PORT", 5000))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def ffmpeg_ok():
    return shutil.which("ffmpeg") is not None


@app.route("/")
def home():
    return jsonify({"status": "online", "ffmpeg": ffmpeg_ok()})


# ANALYZE (frontend için lazım)
@app.route("/analiz", methods=["POST"])
def analiz():
    data = request.get_json()
    url = data.get("url")

    if not url:
        return jsonify({"error": "no url"}), 400

    return jsonify({
        "baslik": "Video hazır",
        "thumbnail": "",
        "sure": "unknown"
    })


# DOWNLOAD
@app.route("/download", methods=["POST"])
def download():

    try:
        data = request.get_json(force=True)

        url = data.get("url")
        quality = data.get("quality", "1080")
        mp3 = data.get("mp3", False)

        if not url:
            return jsonify({"error": "URL missing"}), 400

        uid = str(uuid.uuid4())[:8]
        out = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        if mp3:
            opts = {
                "format": "bestaudio/best",
                "outtmpl": out,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }]
            }
        else:
            fmt = f"bv*[height<={quality}]+ba/b"

            opts = {
                "format": fmt,
                "outtmpl": out,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True
            }

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        file = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(uid)][0]
        path = os.path.join(DOWNLOAD_DIR, file)

        return send_file(path, as_attachment=True)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
