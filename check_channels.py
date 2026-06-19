"""
check_channels.py — Cek URL channel di channels_static.m3u8

Fitur:
- Pakai GET request + User-Agent OTT Navigator (lebih akurat dari HEAD)
- Baca & kirim header #KODIPROP (Origin, Referer, User-Agent custom)
- Channel yang sudah di kategori 'Dead Channels' di-SKIP (tidak dicek ulang)
- Channel mati → group-title diganti jadi 'Dead Channels' di file langsung
- Channel hidup → tetap di kategori aslinya
- Output: dead_channels.txt & live_channels.txt sebagai laporan

Cara pakai:
  python check_channels.py
"""

import urllib.request
import urllib.error
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── Konfigurasi ───────────────────────────────────────────────────────────────
STATIC_FILE  = "channels_static.m3u8"
TIMEOUT      = 12
MAX_WORKERS  = 30
DEAD_LABEL   = "Dead Channels"
DEAD_OUTPUT  = "dead_channels.txt"
LIVE_OUTPUT  = "live_channels.txt"

DEFAULT_UA = (
    "Dalvik/2.1.0 (Linux; U; Android 9; "
    "Mi A1 Build/PKQ1.180917.001) OTTNavigator/2.6.7.6"
)
# ─────────────────────────────────────────────────────────────────────────────


def parse_blocks(filepath):
    """
    Baca channels_static.m3u8, return list of dict:
      {
        'extinf': str,          # baris #EXTINF lengkap
        'kodiprop': [str],      # baris #KODIPROP (bisa kosong)
        'url': str,             # URL stream
        'name': str,            # nama channel
        'group': str,           # group-title saat ini
        'dead_skip': bool,      # True kalau sudah di Dead Channels
      }
    """
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = [l.rstrip() for l in f]
    except FileNotFoundError:
        print(f"[error] File '{filepath}' tidak ditemukan.")
        sys.exit(1)

    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            extinf = line
            # ambil nama
            name_match = re.search(r",(.+)$", line)
            name = name_match.group(1).strip() if name_match else "Unknown"
            # ambil group-title
            group_match = re.search(r'group-title="([^"]*)"', line)
            group = group_match.group(1) if group_match else ""
            # kumpulkan #KODIPROP
            kodiprop = []
            j = i + 1
            while j < len(lines) and lines[j].startswith("#KODIPROP"):
                kodiprop.append(lines[j])
                j += 1
            # skip baris kosong
            while j < len(lines) and not lines[j].strip():
                j += 1
            # URL
            if j < len(lines) and lines[j].startswith("http"):
                url = lines[j].strip()
                blocks.append({
                    "extinf": extinf,
                    "kodiprop": kodiprop,
                    "url": url,
                    "name": name,
                    "group": group,
                    "dead_skip": group == DEAD_LABEL,
                })
                i = j + 1
                continue
        i += 1
    return blocks


def extract_kodiprop_headers(kodiprop_lines):
    """Parse #KODIPROP:inputstream.adaptive.stream_headers=... jadi dict header."""
    headers = {}
    for line in kodiprop_lines:
        # cari stream_headers
        m = re.search(r"stream_headers=(.+)$", line)
        if m:
            raw = m.group(1)
            # format: Key=Value&Key2=Value2
            for part in raw.split("&"):
                if "=" in part:
                    k, _, v = part.partition("=")
                    headers[k.strip()] = v.strip()
    return headers


def check_url(block):
    """Cek satu channel. Return (block, is_live, reason)."""
    name = block["name"]
    url  = block["url"]

    # Bangun headers: mulai dari default, timpa dengan KODIPROP kalau ada
    headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "*/*",
        "Connection": "close",
    }
    kodi_headers = extract_kodiprop_headers(block["kodiprop"])
    headers.update(kodi_headers)
    # Pastikan User-Agent dari KODIPROP dipakai kalau ada
    if "User-Agent" not in kodi_headers:
        headers["User-Agent"] = DEFAULT_UA

    # Coba GET dulu (lebih akurat untuk stream IPTV)
    for method in ("GET", "HEAD"):
        try:
            req = urllib.request.Request(url, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                status = resp.status
                if status < 400:
                    return (block, True, f"HTTP {status} ({method})")
                # kalau GET dapat 4xx, langsung tandai mati
                return (block, False, f"HTTP {status} ({method})")
        except urllib.error.HTTPError as e:
            if method == "GET":
                # kalau GET 403/404, coba HEAD sekali lagi
                # (beberapa server nolak GET tapi izinkan HEAD)
                continue
            return (block, False, f"HTTP {e.code}")
        except urllib.error.URLError as e:
            return (block, False, str(e.reason))
        except Exception as e:
            return (block, False, str(e))

    return (block, False, "Semua metode gagal")


def rewrite_file(filepath, blocks):
    """Tulis ulang channels_static.m3u8 dengan group-title yang sudah diupdate."""
    with open(filepath, "w", encoding="utf-8") as f:
        for b in blocks:
            # Update group-title di baris #EXTINF
            extinf = re.sub(
                r'group-title="[^"]*"',
                f'group-title="{b["group"]}"',
                b["extinf"]
            )
            f.write(extinf + "\n")
            for kp in b["kodiprop"]:
                f.write(kp + "\n")
            f.write(b["url"] + "\n")


def main():
    print(f"[info] Membaca {STATIC_FILE} ...")
    blocks = parse_blocks(STATIC_FILE)
    total  = len(blocks)

    # Pisahkan yang di-skip (sudah Dead Channels) dan yang perlu dicek
    to_check = [b for b in blocks if not b["dead_skip"]]
    skipped  = [b for b in blocks if b["dead_skip"]]
    print(f"[info] {total} channel total | {len(to_check)} dicek | "
          f"{len(skipped)} dilewati (sudah Dead Channels)\n")

    live_results = []
    dead_results = []
    done = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_url, b): b for b in to_check}
        for future in as_completed(futures):
            block, is_live, reason = future.result()
            done += 1
            label = "✓ LIVE" if is_live else "✗ MATI"
            print(f"[{done:>3}/{len(to_check)}] {label}  {block['name']}  ({reason})")
            if is_live:
                live_results.append((block, reason))
            else:
                # Tandai sebagai Dead Channels
                block["group"] = DEAD_LABEL
                dead_results.append((block, reason))

    # Tulis ulang file dengan group-title yang sudah diupdate
    rewrite_file(STATIC_FILE, blocks)
    print(f"\n[info] {STATIC_FILE} sudah diupdate.")

    # Tulis laporan
    with open(DEAD_OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Channel MATI — {len(dead_results)} dari {len(to_check)} yang dicek\n")
        f.write(f"# ({len(skipped)} channel sudah di Dead Channels sebelumnya, dilewati)\n\n")
        for block, reason in sorted(dead_results, key=lambda x: x[0]["name"].lower()):
            f.write(f"{block['name']}\n  {block['url']}\n  Alasan: {reason}\n\n")

    with open(LIVE_OUTPUT, "w", encoding="utf-8") as f:
        f.write(f"# Channel HIDUP — {len(live_results)} dari {len(to_check)} yang dicek\n\n")
        for block, reason in sorted(live_results, key=lambda x: x[0]["name"].lower()):
            f.write(f"{block['name']}\n  {block['url']}\n\n")

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total channel     : {total}
  Dicek             : {len(to_check)}
  Dilewati (dead)   : {len(skipped)}
  ✓ Hidup           : {len(live_results)}
  ✗ Mati (dipindah) : {len(dead_results)}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Channel mati sudah dipindah ke kategori '{DEAD_LABEL}'
  di {STATIC_FILE}. Jalankan update_playlist.py untuk
  update playlist.m3u8.
""")


if __name__ == "__main__":
    main()
