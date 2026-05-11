import os
import uuid
import shutil
import yt_dlp

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = "backend/downloads"
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

    data = request.json

    url = data.get("url")
    quality = data.get("quality", "1080")
    mp3 = data.get("mp3", False)

    if not url:
        return jsonify({"error": "URL missing"}), 400

    unique_id = str(uuid.uuid4())[:8]

    output_template = f"{DOWNLOAD_DIR}/{unique_id}.%(ext)s"

    try:

        # =====================
        # FORMAT SELECT
        # =====================

        if mp3:

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "noplaylist": True,
                "quiet": True,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                }]
            }

        else:

            if quality == "2160":
                selected_format = "bv*[height<=2160]+ba/b"

            elif quality == "1440":
                selected_format = "bv*[height<=1440]+ba/b"

            elif quality == "1080":
                selected_format = "bv*[height<=1080]+ba/b"

            elif quality == "720":
                selected_format = "bv*[height<=720]+ba/b"

            else:
                selected_format = "best"

            ydl_opts = {
                "format": selected_format,
                "outtmpl": output_template,
                "merge_output_format": "mp4",
                "noplaylist": True,
                "quiet": True,
                "concurrent_fragment_downloads": 5,
                "retries": 10,
                "fragment_retries": 10
            }

        # =====================
        # DOWNLOAD
        # =====================

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:

            info = ydl.extract_info(url, download=True)

            title = info.get("title", "media")

        # =====================
        # FIND FILE
        # =====================

        downloaded_file = None

        for file in os.listdir(DOWNLOAD_DIR):

            if file.startswith(unique_id):
                downloaded_file = file
                break

        if not downloaded_file:
            return jsonify({"error": "file not found"}), 500

        file_path = os.path.join(DOWNLOAD_DIR, downloaded_file)

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=downloaded_file
        )

        @response.call_on_close
        def cleanup():
            try:
                os.remove(file_path)
            except:
                pass

        return response

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
