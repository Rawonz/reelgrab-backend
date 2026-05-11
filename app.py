from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid

app = Flask(__name__)
CORS(app)

DOWNLOAD_DIR = tempfile.gettempdir()

def get_ydl_opts(kalite="1080", mp3=False, filepath=None):
    if mp3:
        return {
            "outtmpl": filepath,
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "quiet": True,
        }
    return {
        "outtmpl": filepath,
        "format": f"bestvideo[height<={kalite}]+bestaudio/best/best[height<={kalite}]",
        "merge_output_format": "mp4",
        "quiet": True,
    }

@app.route("/", methods=["GET"])
def index():
    return jsonify({"durum": "ReelGrab API çalışıyor 🎬"})

@app.route("/analiz", methods=["POST"])
def analiz():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "baslik": info.get("title", "Bilinmiyor"),
                "sure": info.get("duration_string") or str(info.get("duration", 0)) + "s",
                "thumbnail": info.get("thumbnail", ""),
                "platform": info.get("extractor_key", ""),
                "boyut_tahmini": info.get("filesize_approx", 0),
            })
    except Exception as e:
        return jsonify({"hata": str(e)}), 400

@app.route("/indir", methods=["POST"])
def indir():
    data = request.get_json()
    url    = data.get("url", "").strip()
    kalite = data.get("kalite", "1080")
    mp3    = data.get("mp3", False)

    if not url:
        return jsonify({"hata": "URL boş olamaz"}), 400

    uzanti = "mp3" if mp3 else "mp4"
    dosya_adi = f"{uuid.uuid4()}.{uzanti}"
    filepath = os.path.join(DOWNLOAD_DIR, dosya_adi)
    outtmpl = filepath if mp3 else filepath.replace(".mp4", ".%(ext)s")

    try:
        opts = get_ydl_opts(kalite=kalite, mp3=mp3, filepath=outtmpl)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not mp3:
                filepath = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".mkv", ".mp4")
                if not os.path.exists(filepath):
                    for f in os.listdir(DOWNLOAD_DIR):
                        if dosya_adi.split(".")[0] in f:
                            filepath = os.path.join(DOWNLOAD_DIR, f)
                            break

        temiz_ad = info.get("title", "video")[:60].replace("/", "-").replace("\\", "-")
        return send_file(
            filepath,
            as_attachment=True,
            download_name=f"{temiz_ad}.{uzanti}",
            mimetype="audio/mpeg" if mp3 else "video/mp4"
        )
    except Exception as e:
        return jsonify({"hata": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
