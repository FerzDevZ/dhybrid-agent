"""Parser tool-call dari output model (fallback untuk provider tanpa native tool calling)."""

from __future__ import annotations

import json
import re

TOOL_RE = re.compile(r"```tool\n(.*?)\n```", re.DOTALL)
INVOKE_RE = re.compile(r'<invoke name="([\w_]+)">(.*?)</invoke>', re.DOTALL)
TOOLCALLS_RE = re.compile(r"<tool_calls>.*?</tool_calls>", re.DOTALL)


def parse_tool_call(text: str) -> dict | None:
    """Parsing blok tool PERTAMA (backward-compat)."""
    calls = parse_tool_calls(text)
    return calls[0] if calls else None


def parse_tool_calls(text: str) -> list[dict]:
    """Parsing SEMUA blok panggilan tool:
    - ```tool {JSON} ``` (format dhybrid)
    - <invoke name="x">argumen</invoke> (format gaya Claude Code)
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
    text = TOOL_RE.sub("", text)
    text = INVOKE_RE.sub("", text)
    text = TOOLCALLS_RE.sub("", text)
    return text.strip()
