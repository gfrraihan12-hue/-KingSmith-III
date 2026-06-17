"""
Auto-generate playlist.m3u8 untuk channel YouTube Kaela Kovalskia.
Dijalankan otomatis oleh GitHub Actions (lihat .github/workflows/update.yml).
Membutuhkan yt-dlp (pip install -U yt-dlp).
"""

import os
import subprocess

CHANNEL_ID = "UCZLZ8Jjx_RN2CXloOmgTHVg"
CHANNEL_NAME = "Kaela Kovalskia"
LOGO_URL = (
    "https://yt3.googleusercontent.com/w97I-49S9Z9O-KvsLgBv2YwW-lq8_Y86BWh43-"
    "YvF8r_v4n_8tX0vW8V3pP4V9L68Q_G_5V6=s800-c-k-c0x00ffffff-no-rj"
)
NUM_VOD = 8          # jumlah video terbaru yang dimasukkan ke playlist
TIMEOUT = 90         # detik, batas waktu tiap pemanggilan yt-dlp
COOKIES_FILE = "cookies.txt"

# Prioritas: manifest HLS (m3u8, paling cocok buat OTT Navigator) -> itag 18
# (mp4 progresif klasik) -> apapun yang tersedia.
FORMAT_SELECTOR = "best[protocol*=m3u8]/18/best"

# Banyak format disembunyikan yt-dlp kalau tidak ada PO Token; paksa tampilkan.
EXTRA_ARGS = ["--extractor-args", "youtube:formats=missing_pot"]


def cookie_args():
    """Sertakan --cookies kalau file cookies.txt ada dan tidak kosong."""
    if os.path.exists(COOKIES_FILE) and os.path.getsize(COOKIES_FILE) > 0:
        return ["--cookies", COOKIES_FILE]
    return []


def run(cmd):
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=TIMEOUT
        )
        out = result.stdout.strip()
        if result.returncode != 0 or not out:
            stderr_snippet = result.stderr.strip()[-800:]
            print(f"[debug] cmd: {' '.join(cmd)}")
            print(f"[debug] returncode: {result.returncode}")
            print(f"[debug] stderr: {stderr_snippet}")
        return out
    except Exception as e:
        print(f"[warn] command failed: {cmd} -> {e}")
        return ""


def get_live_url():
    """Cek apakah channel sedang live, kembalikan direct stream URL kalau ada."""
    out = run([
        "yt-dlp", "-g", "--no-warnings", "-f", FORMAT_SELECTOR,
        *EXTRA_ARGS, *cookie_args(),
        f"https://www.youtube.com/channel/{CHANNEL_ID}/live",
    ])
    first_line = out.split("\n")[0] if out else ""
    return first_line if first_line.startswith("http") else None


def get_recent_video_ids():
    """Ambil daftar (video_id, title) upload terbaru dari channel."""
    out = run([
        "yt-dlp", "--flat-playlist", "--print", "%(id)s|||%(title)s",
        "--playlist-end", str(NUM_VOD), *EXTRA_ARGS, *cookie_args(),
        f"https://www.youtube.com/channel/{CHANNEL_ID}/videos",
    ])
    videos = []
    for line in out.split("\n"):
        if "|||" in line:
            vid, title = line.split("|||", 1)
            videos.append((vid.strip(), title.strip()))
    return videos


def get_video_stream_url(video_id):
    """Ambil direct playback URL untuk 1 video (akan expire setelah beberapa jam)."""
    out = run([
        "yt-dlp", "-g", "--no-warnings", "-f", FORMAT_SELECTOR,
        *EXTRA_ARGS, *cookie_args(),
        f"https://www.youtube.com/watch?v={video_id}",
    ])
    first_line = out.split("\n")[0] if out else ""
    return first_line if first_line.startswith("http") else None


def build_playlist():
    lines = ["#EXTM3U"]

    live_url = get_live_url()
    if live_url:
        lines.append(
            f'#EXTINF:-1 tvg-id="Kaela.Live" tvg-logo="{LOGO_URL}" '
            f'group-title="[LIVE] {CHANNEL_NAME}",[LIVE] {CHANNEL_NAME}'
        )
        lines.append(live_url)
        print("[info] Channel sedang LIVE, entry ditambahkan.")
    else:
        print("[info] Channel tidak sedang live, entry LIVE dilewati.")

    videos = get_recent_video_ids()
    print(f"[info] Ditemukan {len(videos)} video terbaru.")
    added = 0
    for vid, title in videos:
        stream_url = get_video_stream_url(vid)
        if not stream_url:
            print(f"[warn] gagal ambil stream untuk video {vid}, skip.")
            continue
        safe_title = title.replace(",", " ").replace('"', "'")
        lines.append(
            f'#EXTINF:-1 tvg-id="Kaela.{vid}" tvg-logo="{LOGO_URL}" '
            f'group-title="[VOD] {CHANNEL_NAME} Videos",{safe_title}'
        )
        lines.append(stream_url)
        added += 1

    print(f"[info] {added} video VOD ditambahkan ke playlist.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    content = build_playlist()
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(content)
    print("[done] playlist.m3u8 berhasil ditulis.")
