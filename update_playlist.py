"""
Gabungkan beberapa playlist resmi dari iptv-org/iptv jadi satu playlist.m3u8
pribadi, dikategorikan sesuai pilihan kategori kamu.
Tidak butuh yt-dlp/cookies sama sekali -- semua sumber di sini adalah
playlist publik resmi, jadi tidak ada masalah bot-block.
Dijalankan otomatis oleh GitHub Actions (lihat .github/workflows/update.yml).
"""

import re
import urllib.request

TIMEOUT = 30

# (url sumber, label kategori yang mau ditampilkan di OTT Navigator)
SOURCES = [
    ("https://iptv-org.github.io/iptv/countries/id.m3u", "Indonesia"),
    ("https://iptv-org.github.io/iptv/categories/animation.m3u", "Anime & Animasi"),
    ("https://iptv-org.github.io/iptv/categories/music.m3u", "Musik"),
    ("https://iptv-org.github.io/iptv/categories/news.m3u", "Berita"),
    ("https://iptv-org.github.io/iptv/categories/movies.m3u", "Film"),
    ("https://iptv-org.github.io/iptv/categories/sports.m3u", "Olahraga"),
    ("https://iptv-org.github.io/iptv/categories/documentary.m3u", "Knowledge"),
    ("https://iptv-org.github.io/iptv/categories/education.m3u", "Knowledge"),
]


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
    """Parse 1 playlist m3u, kembalikan list baris #EXTINF + URL yang sudah ditag ulang."""
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
    print(f"[info] {group_label}: {count} channel diambil.")
    return out_lines


def build_playlist():
    all_lines = ["#EXTM3U"]
    total = 0
    for url, label in SOURCES:
        content = fetch(url)
        if not content:
            continue
        entries = parse_and_retag(content, label)
        all_lines.extend(entries)
        total += len(entries) // 2
    print(f"[info] Total {total} channel digabung dari {len(SOURCES)} sumber.")
    return "\n".join(all_lines) + "\n"


if __name__ == "__main__":
    content = build_playlist()
    with open("playlist.m3u8", "w", encoding="utf-8") as f:
        f.write(content)
    print("[done] playlist.m3u8 berhasil ditulis.")
