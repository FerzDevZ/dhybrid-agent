"""MCP tools — dukung MCP server eksternal via stdio (JSON-RPC).

Server hanya dari config eksplisit (tool.mcp_servers) — bukan dari prompt.
Output di-cap; proses di-terminate saat tool selesai.
"""

from __future__ import annotations

import json
import subprocess
import threading

# ---- client stdio minimal ----

class MCPError(Exception):
    pass


class McpClient:
    def __init__(self, name: str, command: str, args: list[str], timeout: float = 30.0):
        self.name = name
        self.timeout = timeout
        self.proc = subprocess.Popen(
            [command, *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self._req_id = 0
        self._lock = threading.Lock()
        self._init_done = False

    def _request(self, method: str, params: dict) -> dict:
        with self._lock:
            self._req_id += 1
            req_id = self._req_id
            assert self.proc.stdin is not None and self.proc.stdout is not None
            self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}) + "\n")
            self.proc.stdin.flush()
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == req_id:
                    if "error" in msg:
                        raise MCPError(f"{self.name}: {msg['error']}")
                    return msg.get("result", {})
        raise MCPError(f"{self.name}: tidak ada respons")

    def initialize(self) -> None:
        self._request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "dhybrid", "version": "0.3"}})
        self._init_done = True

    def list_tools(self) -> list[dict]:
        if not self._init_done:
            self.initialize()
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> str:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        content = result.get("content", [])
        if result.get("isError"):
            return f"ERROR {self.name}/{name}: {content}"
        return "\n".join(c.get("text", json.dumps(c)) for c in content if isinstance(c, dict))

    def close(self) -> None:
        try:
            self.proc.terminate()
        except Exception:  # noqa: BLE001, S110
            pass


# ---- registry wiring ----

def register(reg, servers: list[dict] | None = None, max_chars: int = 8000) -> None:
    for srv in servers or []:
        name = srv.get("name", "mcp")
        command = srv.get("command", "")
        args = srv.get("args", [])
        if not command:
            continue
        client = McpClient(name, command, args)
        try:
            tools = client.list_tools()
        except Exception as e:  # noqa: BLE001
            print(f"[mcp] server '{name}' gagal init: {e}")
            client.close()
            continue
        for tool in tools:
            tname = tool.get("name", "")
            desc = tool.get("description", "")[:120]
            schema = tool.get("inputSchema", {})
            reg.register(
                f"mcp_{name}_{tname}",
                f"[MCP:{name}] {desc}",
                schema.get("properties", {}),
                (lambda c=client, tn=tname, **kw: c.call_tool(tn, kw)) if callable(getattr(client, "call_tool", None)) else None,
            )
