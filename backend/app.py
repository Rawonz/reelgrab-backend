import os
import uuid
import shutil
import yt_dlp

from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)

# CORS FIX (502 OPTIONS problemi üçün)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Railway safe port (MƏCBURİ)
PORT = int(os.environ.get("PORT", 5000))

# düzgün path (relative yox, absolute daha stabil)
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

        unique_id = str(uuid.uuid4())[:8]
        output_template = os.path.join(DOWNLOAD_DIR, f"{unique_id}.%(ext)s")

        # =====================
        # MP3 MODE
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

        # =====================
        # VIDEO MODE (FIXED QUALITY)
        # =====================
        else:

            selected_format = "bv*+ba/b"

            if quality == "2160":
                selected_format = "bv*[height<=2160]+ba/b"
            elif quality == "1440":
                selected_format = "bv*[height<=1440]+ba/b"
            elif quality == "1080":
                selected_format = "bv*[height<=1080]+ba/b"
            elif quality == "720":
                selected_format = "bv*[height<=720]+ba/b"

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
        # DOWNLOAD SAFE EXEC
        # =====================
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # =====================
        # FIND FILE SAFELY
        # =====================
        files = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(unique_id)]

        if not files:
            return jsonify({"error": "file not found"}), 500

        file_path = os.path.join(DOWNLOAD_DIR, files[0])

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=files[0]
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
            "error": "backend crashed",
            "detail": str(e)
        }), 500


# =====================
# RAILWAY ENTRY FIX
# =====================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
