#!/usr/bin/env bash
# skills_fetch.sh — helper untuk mengambil metadata & (jika ada) isi skill
# dari skills.sh ke format dhybrid SKILL.md.
#
# Usage:
#   dhybrid skills-sh/scripts/skills_fetch.sh <skill-slug>
#   dhybrid skills-sh/scripts/skills_fetch.sh cline-build-and-debug-extension
#
# Output: menuliskan skills/<nama>/SKILL.md (nama = slug, strip prefix agen jika ada)
#
# CATATAN: skills.sh merender isi skill via JS/RSC. Helper ini mencoba 2 jalur:
#   1) curl HTML -> ekstrak frontmatter (meta/og) yang tersedia statis
#   2) cek apakah ada link ke file .md mentah di repo (sering ada)
# Jika isi penuh tidak tersedia via curl, gunakan URL repo yang ditemukan atau
# buka di browser untuk copy manual (lihat SKILL.md -> "Contoh nyata").
set -euo pipefail

SLUG="${1:-}"
if [[ -z "$SLUG" ]]; then
  echo "Usage: $0 <skill-slug>" >&2
  echo "Contoh: $0 cline-build-and-debug-extension" >&2
  exit 1
fi

URL="https://www.skills.sh/s/${SLUG}"
echo "[*] Fetching ${URL}"

HTML="$(mktemp)"
curl -sL --max-time 25 "$URL" -o "$HTML" || {
  echo "[!] gagal fetch $URL" >&2
  rm -f "$HTML"
  exit 1
}

# --- ekstrak metadata statis ---
TITLE="$(grep -oP '<title>\K[^<]+' "$HTML" | head -1 || true)"
DESC="$(grep -oP 'name="description" content="\K[^"]+' "$HTML" | head -1 || true)"
# cari link ke repo file .md (pola /raw/ atau /blob/ ... .md)
RAW_MD="$(grep -oE 'https:\/\/[^"]+\.md' "$HTML" | head -1 || true)"
# cari data-agent / tag (sering ada di atribut data di card skill)
AGENT="$(grep -oP 'data-agent="\K[^"]+' "$HTML" | head -1 || true)"
DIFF="$(grep -oP 'data-difficulty="\K[^"]+' "$HTML" | head -1 || true)"

echo "[*] title: ${TITLE:-?}"
echo "[*] agent: ${AGENT:-?}"
echo "[*] difficulty: ${DIFF:-?}"
echo "[*] desc : ${DESC:-?}"
if [[ -n "$RAW_MD" ]]; then
  echo "[*] raw md: $RAW_MD"
fi

# --- nama file output ---
# strip prefix "agen-" jika ada (misal cline-build-debug-extension -> build-debug-extension)
BASE="$SLUG"
# output path
OUT="skills/${BASE}/SKILL.md"
echo "[*] Would write to: $OUT"
echo "[*] (dry-run: tidak menulis. Buka $URL di browser & copy isi ke $OUT secara manual,)"
echo "[*]     atau jalankan ulang setelah dapat URL file .md mentah)"

rm -f "$HTML"
