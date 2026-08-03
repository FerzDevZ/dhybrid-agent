"""Parser tool-call dari output model (fallback untuk provider tanpa native tool calling)."""

from __future__ import annotations

import json
import re

TOOL_RE = re.compile(r"```tool\n(.*?)\n```", re.DOTALL)
INVOKE_RE = re.compile(r'<invoke name="([\w_]+)">(.*?)</invoke>', re.DOTALL)
TOOLCALLS_RE = re.compile(r"<tool_calls>.*?</tool_calls>", re.DOTALL)
# <function=terminal>  ... <arg_key>command</arg_key><arg_value>cdn ...</arg_value> ... </function>
FUNC_TAG_RE = re.compile(r"<function\s*=\s*([\w-]+)>(.*?)</function>", re.DOTALL)
ARG_KEY_RE = re.compile(r"<arg_key\s*>\s*([\w.]+)\s*</arg_key>", re.DOTALL)
ARG_VALUE_RE = re.compile(r"<arg_value\s*>(.*?)</arg_value>", re.DOTALL)


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
    """Bentuk {0: nama, 1: args} dengan KEY TIDAK DIBERI QUOTE (gaya python dict)
    — model free memakai ini; json.loads biasa gagal karena key 0/1 tak di-quote."""
    calls: list[dict] = []
    for m in re.finditer(
        r'\{\s*0\s*:\s*["\']\s*([A-Za-z_][A-Za-z0-9_-]*)\s*["\'].{0,60}?1\s*:\s*(\{[^{}]*\})\s*\}',
        text,
        re.DOTALL,
    ):
        name = m.group(1)
        raw = m.group(2)
        try:
            args = json.loads(raw)
        except json.JSONDecodeError:
            args = {}
        if isinstance(name, str) and name and isinstance(args, dict):
            calls.append({"id": f"idx{len(calls)}", "name": name, "arguments": args})
    return calls


def _parse_function_tag_calls(text: str) -> list[dict]:
    """Format gaya function-call: <function=terminal> <arg_key>command</arg_key>
    <arg_value>cd ..</arg_value> </function>. Model free kadang menulis begini.
    """
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
    """Tool call sebagai JSON TELANJANG (tanpa fenced ```tool / <invoke>):
    {\"name\": \"write_file\", \"arguments\": {...}} — model sering memakai format ini.

    Juga menangani bentuk BERBASIS INDEKS (model free sering meniru array):
        {\"0\": \"terminal\", \"1\": {\"command\": \"php artisan migrate\"}}
    termasuk versi key TANPA quote {0: ..., 1: ...}. Tanpa ini call tsb diam-diam
    dibuang → agent terlihat 'macet / tidak ada respon' padahal ingin menjalankan tool.
    """
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
    return calls


def parse_tool_calls(text: str) -> list[dict]:
    """Parsing SEMUA blok panggilan tool:
    - ```tool {JSON} ``` (format dhybrid)
    - <invoke name="x">argumen</invoke> (format gaya Claude Code)
    - {\"name\": \"x\", \"arguments\": {...}} (JSON telanjang)
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
    return dedupe_tool_calls(calls)


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
    text = TOOL_RE.sub("", text)
    text = INVOKE_RE.sub("", text)
    text = TOOLCALLS_RE.sub("", text)
    text = FUNC_TAG_RE.sub("", text)  # buang <function>...</function> sekaligus isinya
    # tag <tool_call>/<tool_calls>/<invoke>/<function=..>/<analysis>/<anteThinking>
    text = re.sub(
        r"<\s*/?\s*(?:tool_call|tool_calls|invoke|function|analysis|anteThinking)\b[^>]*>",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # tag arg <arg_key>../</arg_key> & <arg_value>../</arg_value>
    text = re.sub(r"<\s*/?\s*arg_(?:key|value)\b[^>]*>", "", text, flags=re.IGNORECASE)
    # baris JSON telanjang tool call {"name": ..., "arguments": ...}
    text = re.sub(r'^\{[^\n]*"name"\s*:\s*"[^"]+"[^\n]*\}\s*$', "", text, flags=re.MULTILINE)
    # bentuk indeks {0: nama, 1: args} — key boleh TIDAK di-quote
    text = re.sub(r'^\{[^\n]*\b0\s*:\s*[^\n]*\b1\s*:[^\n]*\}\s*$', "", text, flags=re.MULTILINE)
    # baris artefak model yang hanya berisi marker (response/assistant/tool)
    text = re.sub(r"^\s*(?:response|assistant|user|tool)\s*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()
