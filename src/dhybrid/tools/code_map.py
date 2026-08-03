"""Tool code_map — peta struktur kode via tree-sitter (AST).

Model butuh konteks struktur file tanpa membaca seluruh isi (hemat token):
`code_map` me-list semua fungsi/class + rentang baris dari AST. Didukung:
Python, PHP, JavaScript (grammar tree-sitter resmi — library ringan, TANPA GPU).

Parser AST dipakai langsung dari grammar (paket tree-sitter-<lang>), jadi
tidak ada regex rapuh yang salah tangkap di komentar/string.
"""

from __future__ import annotations

from pathlib import Path

_EXT_LANG = {
    ".py": "python",
    ".php": "php",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

# tipe node AST yang dianggap "simbol" (fungsi/class) di ketiga grammar
_SYMBOL_KINDS = {
    "function_definition",  # python + php
    "class_definition",  # python
    "function_declaration",  # js
    "class_declaration",  # js + php
    "method_definition",  # js
    "arrow_function",  # js (anonymous — tanpa nama)
    "method_declaration",  # php
}

_READ_CAP = 2_000_000  # 2MB — file lebih besar ditolak (bukan kode normal)


def _get_language(lang: str):
    """Load grammar tree-sitter untuk bahasa; raise RuntimeError bila tidak
    tersedia. Defensif terhadap perbedaan API antar-versi paket."""
    from tree_sitter import Language

    mods = {
        "python": "tree_sitter_python",
        "php": "tree_sitter_php",
        "javascript": "tree_sitter_javascript",
    }
    import importlib

    mod = importlib.import_module(mods[lang])
    candidates = ("language", "language_php", "language_js", "language_javascript")
    for attr in candidates:
        fn = getattr(mod, attr, None)
        if fn is None:
            continue
        try:
            obj = fn()
            if obj is None:
                continue
            if isinstance(obj, Language):
                return obj
            return Language(obj)  # 0.23+: PyCapsule → Language(obj)
        except Exception:  # noqa: BLE001,S112 — coba accessor berikutnya
            continue
    raise RuntimeError(f"grammar tree-sitter '{lang}' tidak tersedia (pip install tree-sitter-{lang})")


def _collect_symbols(root) -> list[tuple[str, str, int, int]]:
    """Walk AST (iteratif, anti-recursion-limit) → (kind, name, start_line, end_line)."""
    out: list[tuple[str, str, int, int]] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type in _SYMBOL_KINDS:
            name = ""
            name_node = node.child_by_field_name("name")
            if name_node is not None and name_node.type != "ERROR":
                try:
                    name = name_node.text.decode("utf-8", errors="replace")
                except Exception:  # noqa: BLE001
                    name = ""
            out.append((node.type, name, node.start_point[0] + 1, node.end_point[0] + 1))
        stack.extend(node.children)
    return out


def code_map(path: str, lang: str | None = None) -> str:
    """List fungsi/class dalam satu file kode (AST tree-sitter) + rentang baris.

    Args:
        path: jalur file (relatif terhadap cwd atau absolut).
        lang: python | php | javascript. Bila kosong, dideteksi dari ekstensi.
    """
    p = Path(path)
    if not p.is_file():
        return f"ERROR: file tidak ditemukan: {path}"
    size = p.stat().st_size
    if size > _READ_CAP:
        return f"ERROR: file terlalu besar ({size // 1024}KB > {_READ_CAP // 1024}KB) — bukan kode normal"
    if not lang:
        lang = _EXT_LANG.get(p.suffix.lower())
        if not lang:
            return (
                f"ERROR: ekstensi {p.suffix or '(tanpa ekstensi)'} tidak didukung — "
                "sebut lang= (python|php|javascript)"
            )
    try:
        _lang = _get_language(lang)
        from tree_sitter import Parser

        parser = Parser(_lang)
        tree = parser.parse(p.read_bytes())
    except RuntimeError as e:
        return f"ERROR: {e}"
    except Exception as e:  # noqa: BLE001
        return f"ERROR parse {path}: {type(e).__name__}: {e}"

    symbols = _collect_symbols(tree.root_node)
    if not symbols:
        return f"code_map: {path} ({lang}) — tidak ada fungsi/class ditemukan"
    kinds = {
        "function_definition": "fn",
        "function_declaration": "fn",
        "method_definition": "fn",
        "method_declaration": "fn",
        "arrow_function": "fn",
        "class_definition": "class",
        "class_declaration": "class",
    }
    lines = [f"code_map: {path} ({lang}) — {len(symbols)} simbol:"]
    for kind, name, start, end in sorted(symbols, key=lambda s: s[2]):
        label = name or "(anonymous)"
        lines.append(f"  {kinds.get(kind, kind)} {label} :{start}-{end}")
    return "\n".join(lines)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "code_map",
        "Peta struktur kode (AST tree-sitter): daftar fungsi/class + rentang baris "
        "per file — python, php, javascript. Hemat token: lihat peta dulu, baca "
        "hanya bagian yang relevan.",
        {"path": {"type": "string", "required": True}, "lang": {"type": "string"}},
        code_map,
    )
