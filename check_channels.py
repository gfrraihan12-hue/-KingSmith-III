"""
check_channels.py — Cek URL channel yang mati di channels_static.m3u8

Cara pakai:
  python check_channels.py

Output:
  - dead_channels.txt  : daftar channel yang mati (tidak bisa diakses)
  - live_channels.txt  : daftar channel yang hidup
  - Di terminal juga tampil ringkasan hasil

Bisa dijalankan lokal atau via GitHub Actions (tambah workflow baru).
"""

import urllib.request
import urllib.error
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Konfigurasi ──────────────────────────────────────────────────────────────
STATIC_FILE   = "channels_static.m3u8"
TIMEOUT       = 10      # detik per request
MAX_WORKERS   = 30      # cek paralel, percepat proses
DEAD_OUTPUT   = "dead_channels.txt"
LIVE_OUTPUT   = "live_channels.txt"
# ─────────────────────────────────────────────────────────────────────────────


def parse_m3u(filepath):
    """Baca file m3u8, return list of (name, url)."""
    channels = []
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = [l.rstrip() for l in f]
    except FileNotFoundError:
        print(f"[error] File '{filepath}' tidak ditemukan.")
        sys.exit(1)

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            # Ambil nama channel (setelah koma terakhir di baris #EXTINF)
            match = re.search(r",(.+)$", line)
            name = match.group(1).strip() if match else "Unknown"
            # Cari baris URL berikutnya (lewati baris #KODIPROP dll)
            j = i + 1
            while j < len(lines) and not lines[j].startswith("http"):
                j += 1
            if j < len(lines) and lines[j].startswith("http"):
                channels.append((name, lines[j].strip()))
                i = j + 1
                continue
        i += 1
    return channels


def check_url(name, url):
    """Return (name, url, is_live, reason)."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 10) "
                    "AppleWebKit/537.36 Chrome/91.0 Safari/537.36"
                )
            },
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            status = resp.status
            if status < 400:
                return (name, url, True, f"HTTP {status}")
            else:
                return (name, url, False, f"HTTP {status}")
    except urllib.error.HTTPError as e:
        return (name, url, False, f"HTTP {e.code}")
    except urllib.error.URLError as e:
        return (name, url, False, str(e.reason))
    except Exception as e:
        return (name, url, False, str(e))


def main():
    print(f"[info] Membaca {STATIC_FILE} ...")
    channels = parse_m3u(STATIC_FILE)
    total = len(channels)
    print(f"[info] {total} channel ditemukan, mulai pengecekan ({MAX_WORKERS} paralel) ...\n")

    live  = []
    dead  = []
    done  = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, name, url): (name, url)
                   for name, url in channels}
        for future in as_completed(futures):
            name, url, is_live, reason = future.result()
            done += 1
            status_str = "✓ LIVE" if is_live else "✗ MATI"
            print(f"[{done:>3}/{total}] {status_str}  {name}  ({reason})")
            if is_live:
                live.append((name, url, reason))
            else:
                dead.append((name, url, reason))

    # ── Tulis output ──────────────────────────────────────────────────────────
    with open(DEAD_OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Channel MATI — {len(dead)} dari {total}\n\n")
        for name, url, reason in sorted(dead, key=lambda x: x[0].lower()):
            f.write(f"{name}\n  {url}\n  Alasan: {reason}\n\n")

    with open(LIVE_OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Channel HIDUP — {len(live)} dari {total}\n\n")
        for name, url, reason in sorted(live, key=lambda x: x[0].lower()):
            f.write(f"{name}\n  {url}\n\n")

    # ── Ringkasan ─────────────────────────────────────────────────────────────
    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total channel : {total}
  ✓ Hidup       : {len(live)}
  ✗ Mati        : {len(dead)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Hasil disimpan ke:
    {DEAD_OUTPUT}
    {LIVE_OUTPUT}
""")


if __name__ == "__main__":
    main()
