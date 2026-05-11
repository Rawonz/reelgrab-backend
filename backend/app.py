import os
                "thumbnail": info.get("thumbnail", ""),
                "uploader": info.get("uploader", ""),
                "view_count": info.get("view_count", 0),
                "like_count": info.get("like_count", 0),
                "platform": platform,
            })

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# DOWNLOAD
# =========================
@app.route("/indir", methods=["POST"])
def indir():
    data = request.get_json(force=True)

    url = data.get("url", "").strip()
    kalite = data.get("kalite", "1080")
    mp3 = data.get("mp3", False)

    if not url:
        return jsonify({"error": "URL boşdur"}), 400

    if not validate_url(url):
        return jsonify({"error": "URL dəstəklənmir"}), 400

    unique_id = str(uuid.uuid4())[:8]
    filepath = f"{DOWNLOAD_FOLDER}/{unique_id}.%(ext)s"

    try:
        opts = get_ydl_opts(
            url=url,
            kalite=kalite,
            mp3=mp3,
            filepath=filepath
        )

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        title = clean_filename(info.get("title", "media"))

        downloaded_files = []

        for fname in os.listdir(DOWNLOAD_FOLDER):
            if fname.startswith(unique_id):
                downloaded_files.append(fname)

        if not downloaded_files:
            return jsonify({"error": "Fayl tapılmadı"}), 500

        latest_file = downloaded_files[0]
        file_path = os.path.join(DOWNLOAD_FOLDER, latest_file)

        ext = latest_file.split(".")[-1]
        download_name = f"{title}.{ext}"

        response = send_file(
            file_path,
            as_attachment=True,
            download_name=download_name
        )

        @response.call_on_close
        def cleanup():
            try:
                os.remove(file_path)
            except Exception:
                pass

        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 400


# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
