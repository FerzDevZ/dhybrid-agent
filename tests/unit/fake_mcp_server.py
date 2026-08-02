"""Fake MCP server (stdio JSON-RPC) untuk test."""

import json
import sys


def main():
    tools = [
        {"name": "echo", "description": "balas pesan", "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}}},
    ]
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        msg = json.loads(line)
        rid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": "2024-11-05", "capabilities": {}, "serverInfo": {"name": "fake", "version": "1"}}}
        elif method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools}}
        elif method == "tools/call":
            args = msg.get("params", {})
            text = args.get("arguments", {}).get("text", "")
            resp = {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": f"echo:{text}"}]}}
        else:
            resp = {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "unknown"}}
        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
