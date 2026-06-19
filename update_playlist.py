"""
Bangun playlist.m3u8 pribadi dari 2 sumber:

1. sources.csv          -> kategori "borongan" dari playlist publik (iptv-org dkk)
2. channels_custom.csv  -> channel satuan yang kamu tambah/hapus manual

PENTING: untuk nambah/hapus channel atau kategori, edit sources.csv atau
channels_custom.csv langsung di GitHub. File .py ini tidak perlu disentuh lagi.
"""

import csv
import re
import urllib.request

TIMEOUT = 30
SOURCES_FILE = "sources.csv"
CUSTOM_FILE = "channels_custom.csv"
STATIC_FILE = "channels_static.m3u8"


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"[warn] gagal ambil {url} -> {e}")
        return ""


def retag_group(extinf_line, new_group):
    """Ganti (atau tambahkan) atribut group-title pada baris #EXTINF."""
    if 'group-title="' in extinf_line:
        return re.sub(r'group-title="[^"]*"', f'group-title="{new_group}"', extinf_line)
    return extinf_line.replace("#EXTINF:", f'#EXTINF: group-title="{new_group}"', 1)


def parse_and_retag(content, group_label):
    """Parse 1 playlist m3u publik, retag group-title sesuai label di sources.csv."""
    out_lines = []
    lines = content.splitlines()
    i = 0
    count = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            extinf = retag_group(line, group_label)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("http"):
                out_lines.append(extinf)
                out_lines.append(lines[j].strip())
                count += 1
                i = j + 1
                continue
        i += 1
    print(f"[info] {group_label}: {count} channel diambil dari sumber borongan.")
    return out_lines


def load_sources():
    """Baca sources.csv -> list (url, label_kategori)."""
    sources = []
    try:
        with open(SOURCES_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                label = (row.get("label") or "").strip()
                url = (row.get("url") or "").strip()
                if label and url:
                    sources.append((url, label))
    except FileNotFoundError:
        print(f"[warn] {SOURCES_FILE} tidak ditemukan, dilewati.")
    return sources


def load_custom_channels():
    """Baca channels_custom.csv -> baris #EXTINF + URL siap pakai."""
    lines = []
    count = 0
    try:
        with open(CUSTOM_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                url = (row.get("url") or "").strip()
                category = (row.get("category") or "Lainnya").strip()
                logo = (row.get("logo") or "").strip()
                if not name or not url or not url.startswith("http"):
                    continue
                lines.append(
                    f'#EXTINF:-1 tvg-logo="{logo}" group-title="{category}",{name}'
                )
                lines.append(url)
                count += 1
    except FileNotFoundError:
        print(f"[warn] {CUSTOM_FILE} tidak ditemukan, dilewati.")
    print(f"[info] Channel custom: {count} channel dimuat dari channels_custom.csv.")
    return lines


def load_static_channels():
    """Baca channels_static.m3u8 -> baris #EXTINF (+ #KODIPROP dkk) + URL apa adanya.
    Mendukung format dengan baris tambahan (mis. #KODIPROP untuk header/User-Agent)
    di antara #EXTINF dan URL stream-nya."""
    try:
        with open(STATIC_FILE, encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[warn] {STATIC_FILE} tidak ditemukan, dilewati.")
        return []

    out_lines = []
    lines = content.splitlines()
    n = len(lines)
    i = 0
    count = 0
    skipped = 0
    while i < n:
        line = lines[i].strip()
        if line.startswith("#EXTINF"):
            block = [lines[i]]
            j = i + 1
            found_url = False
            while j < n:
                cur = lines[j].strip()
                if cur.startswith("#EXTINF"):
                    break  # entry sebelumnya rusak (tidak ada URL), berhenti di sini
                if not cur:
                    j += 1
                    continue
                block.append(lines[j])
                if cur.startswith("http"):
                    found_url = True
                    j += 1
                    break
                j += 1
            if found_url:
                out_lines.extend(block)
                count += 1
                i = j
                continue
            else:
                skipped += 1
                i = j
                continue
        i += 1
    print(f"[info] Channel static (paste manual): {count} channel dimuat dari {STATIC_FILE} "
          f"({skipped} entri dilewati karena tidak ada URL).")
    return out_lines


def get_static_epg_header():
    """Ambil atribut url-tvg (EPG) dari baris #EXTM3U pertama di channels_static.m3u8, kalau ada."""
    try:
        with open(STATIC_FILE, encoding="utf-8") as f:
            first_line = f.readline().strip()
    except FileNotFoundError:
        return None
    if first_line.startswith("#EXTM3U") and "url-tvg=" in first_line:
        return first_line
    return None
    print(f"[info] Channel static (paste manual): {count} channel dimuat dari {STATIC_FILE}.")
    return out_lines


def build_playlist():
    header = get_static_epg_header() or "#EXTM3U"
    all_lines = [header]

    for url, label in load_sources():
        content = fetch(url)
        if content:
            all_lines.extend(parse_and_retag(content, label))

    all_lines.extend(load_custom_channels())
    all_lines.extend(load_static_channels())

    total = (len(all_lines) - 1) // 2
    print(f"[info] Total {total} channel digabung.")
    return "\n".join(all_lines) + "\n"


if __name__ == "__main__":
    content = build_playlist()
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(content)
    print("[done] playlist.m3u8 berhasil ditulis.")
