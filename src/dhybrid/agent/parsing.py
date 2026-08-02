"""Parser tool-call dari output model (fallback untuk provider tanpa native tool calling)."""

from __future__ import annotations

import json
import re

TOOL_RE = re.compile(r"```tool\n(.*?)\n```", re.DOTALL)


def parse_tool_call(text: str) -> dict | None:
    """Parsing output model berformat:
    ```tool
    {"name": "grep", "arguments": {"pattern": "x", "path": "."}}
    ```"""
    m = TOOL_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or "name" not in data:
        return None
    return {
        "id": "gen",
        "name": data["name"],
        "arguments": data.get("arguments", {}) if isinstance(data.get("arguments"), dict) else {},
    }


def strip_tool_block(text: str) -> str:
    return TOOL_RE.sub("", text).strip()
