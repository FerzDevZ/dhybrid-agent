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
    base_dir=None,
) -> ToolRegistry:
    reg = ToolRegistry(allowlist=cfg.tool.get("allowlist"), base_dir=base_dir)
    max_chars = cfg.tool.get("max_output_chars", 8000)
    from dhybrid.tools import (
        ask,
        background,
        browser_tool,
        ci_cd,
        clarify,
        code_map,
        code_map_multi,
        codegen_tool,
        dep_graph,
        documents,
        dotnet_toolchain,
        files,
        git,
        go_toolchain,
        java_toolchain,
        mcp,
        memory,
        orchestrator,
        patch,
        project_memory,
        repo,
        rust_toolchain,
        search,
        semantic_search,
        soft,
        subagents,
        terminal,
        tests,
        todo,
        ts_toolchain,
        vision,
        web,
    )

    for mod in (terminal, files, patch, search, git, tests, todo, web, documents, code_map, code_map_multi, dep_graph, semantic_search, codegen_tool, ci_cd, go_toolchain, rust_toolchain, ts_toolchain, java_toolchain, dotnet_toolchain, project_memory, soft, repo):
        mod.register(reg, max_chars=max_chars)
    background.register(reg, max_chars=max_chars)
    orchestrator.register(reg, max_chars=max_chars, client_factory=client_factory)
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
