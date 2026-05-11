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


def ffmpeg_installed():
    return shutil.which("ffmpeg") is not None


@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "ffmpeg": ffmpeg_installed()
    })


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
        output = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

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

            fmt = "bv*+ba/b"

            if quality == "1080":
                fmt = "bv*[height<=1080]+ba/b"
            elif quality == "720":
                fmt = "bv*[height<=720]+ba/b"
            elif quality == "1440":
                fmt = "bv*[height<=1440]+ba/b"
            elif quality == "2160":
                fmt = "bv*[height<=2160]+ba/b"

            ydl_opts = {
                "format": fmt,
                "outtmpl": output,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
                "retries": 10,
                "fragment_retries": 10
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(url, download=True)

        files = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(uid)]

        if not files:
            return jsonify({"error": "file not found"}), 500

        path = os.path.join(DOWNLOAD_DIR, files[0])

        response = send_file(path, as_attachment=True, download_name=files[0])

        @response.call_on_close
        def cleanup():
            try:
                os.remove(path)
            except:
                pass

        return response

    except Exception as e:
        return jsonify({
            "error": "backend crash",
            "detail": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
