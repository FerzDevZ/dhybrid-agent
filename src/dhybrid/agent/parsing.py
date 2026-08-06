"""Parser tool-call dari output model (fallback untuk provider tanpa native tool calling).

Dukung 5 gaya penulisan model free:
1. kode ```tool ...``` (format dhybrid) — parse pake regex blok.
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
# (bangun dari string agar source tak mengandung literal closing tag penutup
#  sehingga tidak bentrok dengan transport tool-call; semua regex tetap sama.)
T = "``" + "`"
FSTART = "<function"
FEND = "</function>"
INV_END = "</invoke>"
TOOL_RE = re.compile(T + r"tool\n(.*?)\n" + T + "", re.DOTALL)
TOOLCALL_SINGLE_RE = re.compile(
    r"<tool_call>\s*<tool_name>(.*?)</tool_name>\s*<parameters>(.*?)</parameters>\s*</tool_call>",
    re.DOTALL,
)
INVOKE_RE = re.compile(r'<invoke\s+name="([\w_-]+)"\s*>(.*?)' + INV_END, re.DOTALL)
TOOLCALLS_RE = re.compile(r"<tool_calls>.*?</tool_calls>", re.DOTALL)
FUNC_TAG_RE = re.compile(FSTART + r"\s*=\s*([\w_-]+)>(.*?)" + FEND, re.DOTALL)
ARG_KEY_RE = re.compile(r"<arg_key>\s*(.*?)\s*</arg_key>", re.IGNORECASE | re.DOTALL)
# buat arg_value jangan pakai literal closing tag di source → gabung string
AV = "arg_value"
ARG_VALUE_RE = re.compile("<" + AV + r"\s*>(.*?)</" + AV + ">", re.DOTALL)


def parse_tool_call(text: str) -> dict | None:
    """Parsing blok tool PERTAMA (backward-compat)."""
    calls = parse_tool_calls(text)
    return calls[0] if calls else None


def _iter_json_objects(text: str):
    """Yield dict dari objek JSON mandiri di teks (brace-matched, string-aware)."""
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        j = i
        in_str = False
        esc = False
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[i : j + 1])
                    except json.JSONDecodeError:
                        obj = None
                    if isinstance(obj, dict):
                        yield obj
                    break
            j += 1
        i = j + 1


def _parse_index_alias_calls(text: str) -> list[dict]:
    """Bentuk {0: nama, 1: args} key TANPA quote (gaya python dict) —
    json.loads gagal. Dipakai regex brace-matched satu level."""
    calls: list[dict] = []
    for m in re.finditer(
        r'\{\s*0\s*:\s*["\']\s*(\w[\w-]*)\s*["\'].{0,40}?1\s*:\s*(\{[^{}]*\})\s*\}',
        text,
        re.DOTALL,
    ):
        name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except json.JSONDecodeError:
            args = {}
        if isinstance(name, str) and isinstance(args, dict):
            calls.append({"id": f"idx{len(calls)}", "name": name, "arguments": args})
    return calls


def _parse_array_calls(text: str) -> list[dict]:
    """Bentuk LIST python: [nama, {args}] — name di idx 0, args di idx 1."""
    calls: list[dict] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "[":
            i += 1
            continue
        depth = 0
        in_str = False
        esc = False
        j = i
        while j < n:
            c = text[j]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            elif c == '"':
                in_str = True
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth == 0 and j > i:
            try:
                obj = json.loads(text[i : j + 1])
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, list) and len(obj) >= 2:
                name, args = obj[0], obj[1]
                if isinstance(name, str) and isinstance(args, dict):
                    calls.append({"id": f"arr{len(calls)}", "name": name, "arguments": args})
            i = j + 1
        else:
            i += 1
    return calls


def _parse_function_tag_calls(text: str) -> list[dict]:
    """Format function-call tag (model free): <function=NAME> <arg_key>K</arg_key> VALUE.
    K dan VALUE diekstrak via ARG_KEY_RE / ARG_VALUE_RE yang sudah didefinisikan
    dengan string concatenation (agar source tidak mengandung literal penutup)."""
    calls: list[dict] = []
    for k, m in enumerate(FUNC_TAG_RE.finditer(text)):
        name = m.group(1)
        content = m.group(2)
        keys = ARG_KEY_RE.findall(content)
        vals = [v.strip() for v in ARG_VALUE_RE.findall(content)]
        args = {}
        for i, key in enumerate(keys):
            if i < len(vals) and vals[i]:
                args[key] = vals[i]
        calls.append({"id": f"func{k}", "name": name, "arguments": args})
    return calls


def parse_bare_json_calls(text: str) -> list[dict]:
    """Tool call JSON telanjang (tanpa fenced ```tool). Bentuk:
    {"name": "x", "arguments": {...}} atau kunci-indeks {"0": nama, "1": args}.
    Termasuk versi key TANPA quote {0: nama, 1: args} (model free meniru python)."""
    calls: list[dict] = []
    for k, obj in enumerate(_iter_json_objects(text)):
        name = obj.get("name")
        args = obj.get("arguments")
        # format indeks-alias: {"0": nama, "1": args}
        if not name and obj.get("0") and isinstance(obj.get("1"), dict):
            calls.append({"id": f"alias{k}", "name": obj["0"], "arguments": obj["1"]})
            continue
        if isinstance(name, str) and name:
            if not isinstance(args, dict) and isinstance(obj.get("1"), dict):
                args = obj["1"]
            elif args is None:
                args = {}
            if isinstance(args, dict):
                calls.append({"id": f"bare{k}", "name": name, "arguments": args})
    calls.extend(_parse_index_alias_calls(text))
    calls.extend(_parse_array_calls(text))
    return calls


def parse_tool_calls(text: str) -> list[dict]:
    """Parsing SEMUA blok panggilan tool:
    - ```tool {JSON} ``` (format dhybrid)
    - tag invoke/argumen (format Claude Code)
    - {name/arguments} JSON telanjang
    - bentuk indeks {0/1} dan LIST [nama, args] (model free)
    """
    calls: list[dict] = []
    for i, m in enumerate(TOOL_RE.finditer(text)):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or "name" not in data:
            continue
        args = data.get("arguments", {})
        calls.append({
            "id": f"gen{i}",
            "name": data["name"],
            "arguments": args if isinstance(args, dict) else {},
        })
    for j, m in enumerate(INVOKE_RE.finditer(text)):
        name = m.group(1)
        raw = m.group(2).strip()
        try:
            args = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            args = {"command": raw} if raw else {}
        if not isinstance(args, dict):
            args = {"value": raw}
        calls.append({"id": f"inv{j}", "name": name, "arguments": args})
    calls.extend(parse_bare_json_calls(text))
    calls.extend(_parse_function_tag_calls(text))
    calls.extend(_parse_toolcall_single(text))
    return dedupe_tool_calls(calls)


def _parse_toolcall_single(text: str) -> list[dict]:
    """Format: <tool_call><tool_name>X</tool_name><parameters>{JSON}</parameters></tool_call>"""
    calls: list[dict] = []
    for i, m in enumerate(TOOLCALL_SINGLE_RE.finditer(text)):
        name = m.group(1).strip()
        raw = m.group(2).strip()
        try:
            args = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            args = {"command": raw} if raw else {}
        if isinstance(args, dict) and name:
            calls.append({"id": f"tc{i}", "name": name, "arguments": args})
    return calls


def dedupe_tool_calls(calls: list[dict]) -> list[dict]:
    """Buang panggilan identik berulang (model sering mengulang blok yang sama)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for c in calls:
        key = (c["name"], json.dumps(c.get("arguments", {}), sort_keys=True))
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def strip_tool_block(text: str) -> str:
    """Bersihkan semua markup panggilan tool agar teks final bersih/prosa."""
    text = TOOL_RE.sub("", text)
    text = TOOLCALL_SINGLE_RE.sub("", text)
    text = INVOKE_RE.sub("", text)
    text = TOOLCALLS_RE.sub("", text)
    text = FUNC_TAG_RE.sub("", text)
    text = re.sub(
        r"<\s*/?\s*(?:tool_call|tool_calls|tool_name|invoke|function|analysis|anteThinking|parameters?|parameters)\b[^>]*>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"<\s*/?\s*arg_(?:key|value)\b[^>]*>", "", text, flags=re.IGNORECASE)
    # baris JSON telanjang {name/arguments}
    text = re.sub(
        r'^\{[^\n]*"name"\s*:\s*"[^"]+"[^\n]*\}\s*$',
        "",
        text,
        flags=re.MULTILINE,
    )
    # bentuk indeks {0: nama, 1: args} (key boleh tidak di-quote), satu baris
    text = re.sub(
        r"^\{[^\n]*\b0\s*:\s*[^\n]*\b1\s*:[^\n]*\}\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )
    # bentuk array [nama, {args}], satu baris
    text = re.sub(
        r'^\[[^\n]*"[\s]*,[\s]*\{.*\}\s*\]\s*$',
        "",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    # baris artefak model hanya berisi marker role
    text = re.sub(
        r"^\s*(?:response|assistant|user|tool)\s*$",
        "",
        text,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    return text.strip()
