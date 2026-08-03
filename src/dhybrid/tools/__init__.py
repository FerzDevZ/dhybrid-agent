"""Paket tools: registry + implementasi tool."""

from __future__ import annotations

from collections.abc import Callable

from dhybrid.config import Config
from dhybrid.session.memory import MemoryStore
from dhybrid.tools.registry import ToolRegistry


def build_tools(
    cfg: Config,
    client_factory: Callable | None = None,
    memory_store: MemoryStore | None = None,
    ask_state=None,
) -> ToolRegistry:
    reg = ToolRegistry(allowlist=cfg.tool.get("allowlist"))
    max_chars = cfg.tool.get("max_output_chars", 8000)
    from dhybrid.tools import (
        ask,
        documents,
        files,
        git,
        mcp,
        memory,
        patch,
        search,
        subagents,
        terminal,
        tests,
        todo,
        web,
    )

    for mod in (terminal, files, patch, search, git, tests, todo, web, documents):
        mod.register(reg, max_chars=max_chars)
    mcp.register(reg, servers=cfg.tool.get("mcp_servers", []))
    memory.register(reg, max_chars=max_chars, store=memory_store)
    subagents.register(reg, max_chars=max_chars, client_factory=client_factory)
    from dhybrid.tools.ask import AskState

    ask.register(reg, ask_state or AskState(interactive=True))
    return reg
