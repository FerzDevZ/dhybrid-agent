"""ToolRegistry — daftar tool + eksekusi dengan allowlist & error handling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON-schema ringkas
    fn: Callable[..., Any]


class ToolRegistry:
    def __init__(self, allowlist: list[str] | None = None):
        self._tools: dict[str, ToolSpec] = {}
        self.allowlist = set(allowlist or [])
        self.tool_count: dict[str, int] = {}

    def register(self, name: str, description: str, parameters: dict, fn: Callable[..., Any]) -> None:
        self._tools[name] = ToolSpec(name, description, parameters, fn)

    def specs(self) -> list[dict]:
        """Tool definitions ringkas untuk system prompt (hemat token)."""
        return [
            {"name": t.name, "description": t.description, "parameters": t.parameters}
            for t in self._tools.values()
            if t.name in self.allowlist or not self.allowlist
        ]

    def spec_text(self) -> str:
        """Rendering tool definitions jadi teks prompt yang ringkas."""
        lines = ["TOOLS TERSEDIA (format panggilan di akhir pesan):"]
        for s in self.specs():
            params = ", ".join(f"{k}={v.get('type', '?')}" for k, v in s["parameters"].items())
            lines.append(f"- {s['name']}({params}) — {s['description']}")
        return "\n".join(lines)

    def execute(self, name: str, arguments: dict) -> str:
        if name not in self._tools:
            return f"ERROR: tool '{name}' tidak dikenal"
        if self.allowlist and name not in self.allowlist:
            return f"ERROR: tool '{name}' tidak diizinkan (allowlist)"
        self.tool_count[name] = self.tool_count.get(name, 0) + 1
        try:
            out = self._tools[name].fn(**arguments)
            return str(out)
        except TypeError as e:
            return f"ERROR argumen {name}: {e}"
        except Exception as e:  # noqa: BLE001
            return f"ERROR {name}: {type(e).__name__}: {e}"
