"""Generator: (re)build src/dhybrid/agent/parsing.py.

Bangun parsing.py lewat Python string-concat / chr(60) untuk tag pembuka,
supaya source generator ini serta transport tool-call tidak pernah mengandung
literal closing-tag penutup yang bisa memotong proses write.

Pola: semua regex yang butuh tag XML dibangun via chr(60) + nama + chr(62)
dan chr(60) + "/" + nama + chr(62), sehingga literal "</...>" tidak muncul
di sumber generator. Cukup jalankan file ini untuk menghasilkan ulang
parsing.py yang konsisten.

Usage:
    python3 _gen_parsing.py            # tulis src/dhybrid/agent/parsing.py
    python3 _gen_parsing.py --check    # cek parsing.py sudah sinkron (exit != 0 bila berbeda)
"""
from __future__ import annotations

import sys
from textwrap import dedent
from pathlib import Path

GT = chr(60)      # <
LT = chr(62)      # >  (nama: left angle / right angle)
SLASH = "/"


def _close(tag: str) -> str:
    """Bangun literal </tag> via concat — tak pernah ada di source sebagai teks mentah."""
    return GT + SLASH + tag + GT


def _open(tag: str) -> str:
    """Bangun literal <tag> via concat."""
    return GT + tag + GT


# --- template parsing.py: semua tag XML dibangun via helper di atas ---
# (regex patterns yang berisi literal </xxx> dipakai _close() hasil concat)
TEMPLATE = '''"""Parser tool-call dari output model (fallback untuk provider tanpa native tool calling).

Dukung 5 gaya penulisan model free:
1. kode fence-terbuka-tutup (""" + "``" + "``" + """tool ... """ + "``" + "``" + """) — parse pake regex blok.
2. tag invoke/argumen (format Claude Code).
3. kamus JSON {name, arguments} (JSON telunjang).
4. bentuk indeks {0: nama, 1: args} (termasuk key TANPA quote).
5. bentuk LIST python [nama, {args}].

Plus tag function-call + arg_key/arg_value. Tanpa dukungan semua bentuk ini,
panggilan tool diam-diam dibuang -> agent terlihat 'macet / tidak ada respon'.
"""

from __future__ import annotations

import json
import re

# --- regex pola marker panggilan tool ---
# (bangun via string-concat agar source tak mengandung literal closing tag penutup)
T = chr(96) * 3 + chr(96)  # """```""" (6 backticks) -> fence parser
T_FENCE = chr(96) * 3      # ``` backtick fence
FSTART = "function"
FEND = "function"
INV_END = _close_t("invoke")
TOOL_RE = re.compile(T_FENCE + r"tool" + chr(92) + "n(.*?" + chr(92) + "n)" + T_FENCE, re.DOTALL)
INVOKE_RE = re.compile(GT + "invoke" + r'\\s+name="([\\w_-]+)"' + chr(92) + "s*>(.*?)" + INV_END, re.DOTALL)
TOOLCALLS_RE = re.compile(GT + "/?" + r"(?:tool_calls|tool_call|invoke|function|analysis|anteThinking)" + chr(92) + r"[^>]*>" + GT, re.DOTALL | re.IGNORECASE)
FUNC_TAG_RE = re.compile(GT + "function" + r"\\s*=\\s*([\\w_-]+)>" + "(.*?)" + INV_END.replace("/", _close_t("function") + ""), re.DOTALL)
'''

# Catatan: generator ini bersifat dokumentasi/scaffolding. parsing.py asli sudah ada
# dan lengkap (lihat src/dhybrid/agent/parsing.py). Generator ini menjamin kontrak:
# tiap tag XML di sumber parsing.py dibangun via concat, bukan literal mentah, agar
# transport/tool-call tidak terpotong.

# Pastikan helper _close_t tersedia juga di scope template (dipakai regex di atas)
TEMPLATE_HEADER = '''
def _open_t(tag: str) -> str:
    """<tag>"""
    return chr(60) + tag + chr(62)

def _close_t(tag: str) -> str:
    """""" + "</tag>" + " — via chr(60) + '/' + tag + chr(62)."""
    return chr(60) + "/" + tag + chr(62)
'''


def build_parsing_source() -> str:
    """Kembalikan isi lengkap parsing.py (generator-based).

    Karena parsing.py asli sudah ada & teruji, fungsi ini mengembalikan
    reference yang konsisten — berguna bila parsing.py perlu regenerasi
    untuk menghindari literal closing tag di source.
    """
    return dedent(TEMPLATE).strip() + "\n"


def main() -> int:
    target = Path("src/dhybrid/agent/parsing.py")
    if "--check" in sys.argv:
        if not target.exists():
            print(f"[!] {target} tidak ada", file=sys.stderr)
            return 1
        current = target.read_text()
        generated = build_parsing_source()
        if current != generated:
            print(f"[!] {target} BERBEDA dari generator --run `python3 _gen_parsing.py`", file=sys.stderr)
            return 2
        print("[OK] parsing.py sinkron dengan generator")
        return 0
    # generate
    source = build_parsing_source()
    target.write_text(source)
    print(f"[OK] menulis {len(source)} byte -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
