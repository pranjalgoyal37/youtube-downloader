import streamlit as st
import yt_dlp
import os
import subprocess
import platform
import json
from datetime import datetime
from googleapiclient.discovery import build

# ---- CONFIG ----
DOWNLOAD_FOLDER = "downloads"
HISTORY_FILE = "download_history.json"
YOUTUBE_API_KEY = "AIzaSyA95wT6u39lsWa76him7dOjpAD90UGLGJY"  # Replace with your actual API key
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ---- Open Downloads Folder ----
def open_downloads_folder():
    folder_path = os.path.abspath(DOWNLOAD_FOLDER)
    if platform.system() == "Windows":
        subprocess.run(f'explorer "{folder_path}"')
    elif platform.system() == "Darwin":
        subprocess.run(["open", folder_path])
    else:
        subprocess.run(["xdg-open", folder_path])

# ---- Download progress handler ----
def create_hook(pbar, status_text):
    def progress_hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)
            if total_bytes:
                progress = int(downloaded_bytes / total_bytes * 100)
                pbar.progress(progress)
                status_text.text(f"\U0001F4E5 Downloading... {progress}%")
        elif d['status'] == 'finished':
            pbar.progress(100)
            status_text.text("\u2705 Download finished. Processing...")
    return progress_hook

# ---- Save download history ----
def save_history(item):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            data = json.load(f)
    else:
        data = []
    data.append(item)
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---- Download Video or Audio ----
def download_youtube(url, resolution=None, audio_only=False, is_playlist=False, pbar=None, status_text=None):
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'progress_hooks': [create_hook(pbar, status_text)] if pbar and status_text else []
    }

    if is_playlist:
        ydl_opts['noplaylist'] = False

    if audio_only:
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    else:
        ydl_opts.update({
            'format': f'bestvideo[height={resolution}]+bestaudio/best' if resolution else 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4'
        })

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(url, download=True)
        save_history({
            "title": result.get("title"),
            "url": url,
            "format": "audio" if audio_only else "video",
            "time": datetime.now().isoformat()
        })

# ---- Get YouTube Info (cached & optimized) ----
@st.cache_data(show_spinner=False)
def get_video_info(url):
    ydl_opts = {
        'quiet': True,
        'nocheckcertificate': True,
        'extract_flat': 'playlist' in url,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)

# ---- Search YouTube using Data API ----
def youtube_search(query, max_results=5):
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
    request = youtube.search().list(
        part="snippet",
        q=query,
        maxResults=max_results,
        type="video"
    )
    response = request.execute()
    return response.get("items", [])

# ---- Streamlit UI ----
st.set_page_config(page_title="YT Downloader", page_icon="\U0001F3AC")
st.title("\U0001F3AC YouTube Downloader with Progress Bar")
st.markdown("Download YouTube videos or audio with full control and live progress.")

mode = st.sidebar.selectbox("Choose Mode", ["Single URL", "Search", "Batch", "History"])

if mode == "Search":
    query = st.text_input("🔍 Search on YouTube")
    if st.button("Search"):
        results = youtube_search(query)
        for video in results:
            vid_id = video['id']['videoId']
            title = video['snippet']['title']
            url = f"https://www.youtube.com/watch?v={vid_id}"
            st.markdown(f"### {title}")
            st.video(url)
            if st.button(f"⬇️ Download {title}", key=vid_id):
                pbar = st.progress(0)
                status = st.empty()
                download_youtube(url, resolution="720", audio_only=False, pbar=pbar, status_text=status)
                st.success("✅ Downloaded!")

elif mode == "Single URL":
    url = st.text_input("🔗 Enter YouTube Video or Playlist URL")
    if url:
        try:
            with st.spinner("⏳ Fetching video details..."):
                info = get_video_info(url)
            is_playlist = 'entries' in info

            if is_playlist:
                st.subheader(f"📃 Playlist: {info['title']}")
                st.markdown(f"🔢 Videos in playlist: {len(info['entries'])}")
            else:
                st.video(url)
                st.subheader(info['title'])
                st.markdown(f"👁 Views: {info.get('view_count', 'N/A')}")
                st.markdown(f"⏱ Duration: {round(info.get('duration', 0) / 60, 2)} minutes")

            choice = st.radio("Select download type:", ["🎞 Video (MP4)", "🎧 Audio (MP3)"])
            is_audio = (choice == "🎧 Audio (MP3)")
            selected_res = None

            if not is_audio and not is_playlist:
                formats = info.get('formats', [])
                resolutions = sorted({f['height'] for f in formats if f.get('vcodec') != 'none' and f.get('height')}, reverse=True)
                selected_res = st.selectbox("📺 Choose resolution", resolutions)

            if st.button("⬇️ Download Now"):
                pbar = st.progress(0)
                status = st.empty()
                download_youtube(url, resolution=selected_res, audio_only=is_audio, is_playlist=is_playlist, pbar=pbar, status_text=status)
                st.success("✅ Download completed!")

        except Exception as e:
            st.error(f"❌ Failed to fetch info: {e}")

elif mode == "Batch":
    urls = st.text_area("📋 Paste multiple YouTube URLs (one per line)")
    choice = st.radio("Select download type:", ["🎞 Video (MP4)", "🎧 Audio (MP3)"])
    is_audio = (choice == "🎧 Audio (MP3)")
    selected_res = None
    if not is_audio:
        selected_res = st.text_input("Resolution (e.g. 720)")

    if st.button("⬇️ Download All"):
        url_list = urls.strip().splitlines()
        for u in url_list:
            pbar = st.progress(0)
            status = st.empty()
            download_youtube(u, resolution=selected_res, audio_only=is_audio, pbar=pbar, status_text=status)
        st.success("✅ Batch download completed!")

elif mode == "History":
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            history = json.load(f)
        for entry in history[::-1]:
            st.markdown(f"**{entry['title']}** — {entry['format']} — {entry['time']}")
            st.caption(entry['url'])
    else:
        st.info("No download history found.")

st.sidebar.button("📂 Open Downloads Folder", on_click=open_downloads_folder)
