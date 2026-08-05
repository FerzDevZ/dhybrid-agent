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
    clarify_state=None,
) -> ToolRegistry:
    reg = ToolRegistry(allowlist=cfg.tool.get("allowlist"))
    max_chars = cfg.tool.get("max_output_chars", 8000)
    from dhybrid.tools import (
        ask,
        browser_tool,
        clarify,
        code_map,
        code_map_multi,
        dep_graph,
        documents,
        files,
        git,
        mcp,
        memory,
        orchestrator,
        patch,
        project_memory,
        search,
        semantic_search,
        soft,
        subagents,
        terminal,
        tests,
        todo,
        vision,
        web,
    )

    for mod in (terminal, files, patch, search, git, tests, todo, web, documents, code_map, code_map_multi, dep_graph, semantic_search, orchestrator, project_memory, soft):
        mod.register(reg, max_chars=max_chars)
    browser_tool.register(reg)
    vision.register(reg)
    mcp.register(reg, servers=cfg.tool.get("mcp_servers", []))
    memory.register(reg, max_chars=max_chars, store=memory_store)
    subagents.register(reg, max_chars=max_chars, client_factory=client_factory)
    from dhybrid.tools.ask import AskState

    ask.register(reg, ask_state or AskState(interactive=True))
    from dhybrid.tools.clarify import ClarifyState

    clarify.register(reg, clarify_state or ClarifyState(interactive=True))
    return reg
