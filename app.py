from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import uuid
import threading

app = Flask(__name__)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

download_status = {}

def do_download(task_id, url, fmt, quality):
    try:
        download_status[task_id] = {"status": "downloading", "progress": 0, "filename": None}

        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 1)
                downloaded = d.get('downloaded_bytes', 0)
                pct = int(downloaded / total * 100) if total else 0
                download_status[task_id]["progress"] = pct
            elif d['status'] == 'finished':
                download_status[task_id]["progress"] = 100

        filename = os.path.join(DOWNLOAD_FOLDER, f"{task_id}")

        cookies = 'cookies.txt' if os.path.exists('cookies.txt') else None

        if fmt == "mp3":
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': filename + '.%(ext)s',
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': quality.replace('kbps', '')}],
                'progress_hooks': [progress_hook],
                'cookiefile': cookies,
            }
        elif fmt == "jpg":
            ydl_opts = {
                'format': 'best',
                'outtmpl': filename + '.%(ext)s',
                'writethumbnail': True,
                'skip_download': True,
                'progress_hooks': [progress_hook],
                'cookiefile': cookies,
            }
        else:
            quality_map = {'2160p': 'bestvideo[height<=2160]+bestaudio/best', '1080p': 'bestvideo[height<=1080]+bestaudio/best', '720p': 'bestvideo[height<=720]+bestaudio/best', '480p': 'bestvideo[height<=480]+bestaudio/best', '360p': 'bestvideo[height<=360]+bestaudio/best'}
            ydl_opts = {
                'format': quality_map.get(quality, 'best'),
                'outtmpl': filename + '.%(ext)s',
                'merge_output_format': 'mp4',
                'progress_hooks': [progress_hook],
                'cookiefile': cookies,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            ext = 'mp3' if fmt == 'mp3' else ('jpg' if fmt == 'jpg' else 'mp4')
            final_file = filename + '.' + ext
            if not os.path.exists(final_file):
                for f in os.listdir(DOWNLOAD_FOLDER):
                    if f.startswith(task_id):
                        final_file = os.path.join(DOWNLOAD_FOLDER, f)
                        break
            download_status[task_id]["status"] = "done"
            download_status[task_id]["filename"] = final_file
            download_status[task_id]["title"] = info.get("title", "video")

    except Exception as e:
        download_status[task_id]["status"] = "error"
        download_status[task_id]["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/preview", methods=["POST"])
def preview():
    url = request.json.get("url", "")
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                "title": info.get("title", ""),
                "duration": info.get("duration_string", ""),
                "views": info.get("view_count", 0),
                "thumbnail": info.get("thumbnail", ""),
                "platform": info.get("extractor_key", "Web"),
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/download", methods=["POST"])
def download():
    url = request.json.get("url", "")
    fmt = request.json.get("format", "mp4")
    quality = request.json.get("quality", "1080p")
    task_id = str(uuid.uuid4())
    thread = threading.Thread(target=do_download, args=(task_id, url, fmt, quality))
    thread.daemon = True
    thread.start()
    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def status(task_id):
    return jsonify(download_status.get(task_id, {"status": "unknown"}))


@app.route("/file/<task_id>")
def get_file(task_id):
    info = download_status.get(task_id, {})
    filepath = info.get("filename")
    if filepath and os.path.exists(filepath):
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))
    return jsonify({"error": "Dosya bulunamadı"}), 404


if __name__ == "__main__":
    app.run(debug=True)
