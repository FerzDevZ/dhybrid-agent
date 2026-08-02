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
) -> ToolRegistry:
    reg = ToolRegistry(allowlist=cfg.tool.get("allowlist"))
    max_chars = cfg.tool.get("max_output_chars", 8000)
    from dhybrid.tools import (
        files,
        git,
        memory,
        patch,
        search,
        subagents,
        terminal,
        tests,
        todo,
    )

    for mod in (terminal, files, patch, search, git, tests, todo):
        mod.register(reg, max_chars=max_chars)
    memory.register(reg, max_chars=max_chars, store=memory_store)
    subagents.register(reg, max_chars=max_chars, client_factory=client_factory)
    return reg
