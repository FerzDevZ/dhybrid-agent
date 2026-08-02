"""AgentLoop — loop ReAct: stream model → parse tool call → eksekusi → observe.

Fitur hemat token:
- kompaksi konteks saat budget lunak tercapai (pakai model kecil bila ada router)
- early-stop saat model menjawab final (atau sinyal TIDAK ADA YANG PERLU DIUBAH)
- eskalasi model kecil → besar bila tool error berulang (cheap-first)
- budget keras menghentikan loop
"""

from __future__ import annotations

from dataclasses import dataclass

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.parsing import parse_tool_call
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.compress import compact_conversation
from dhybrid.efficiency.context import ContextManager
from dhybrid.efficiency.lazy import needs_change_check
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, Usage
from dhybrid.tools.registry import ToolRegistry


@dataclass
class LoopConfig:
    max_steps: int = 20
    max_tool_output_chars: int = 8000
    escalate_after_errors: int = 2


@dataclass
class LoopResult:
    final_text: str = ""
    steps: int = 0
    compacted: bool = False
    stopped_early: bool = False
    escalated: bool = False
    budget_exhausted: bool = False


class AgentLoop:
    """client_or_router: LLMClient langsung, atau objek dengan .route(prompt, force=None)."""

    def __init__(
        self,
        client_or_router,
        tools: ToolRegistry,
        ctx: ContextManager | None = None,
        budget: TokenBudget | None = None,
        cfg: LoopConfig | None = None,
        hooks: Hooks | None = None,
    ):
        self.router = client_or_router if hasattr(client_or_router, "route") else None
        self.client: LLMClient | None = None if self.router else client_or_router
        self.tools = tools
        self.ctx = ctx or ContextManager()
        self.budget = budget or TokenBudget()
        self.cfg = cfg or LoopConfig()
        self.hooks = hooks or Hooks()

    def _pick_client(self, prompt: str, force: str | None = None) -> LLMClient:
        if self.router is not None:
            return self.router.route(prompt, force=force)
        return self.client  # type: ignore[return-value]

    def _compact(self, client: LLMClient) -> bool:
        cands = self.ctx.candidates_for_compaction()
        if not cands:
            return False
        # gunakan model kecil untuk kompaksi (murah)
        cheap = self.router.small if self.router is not None else client
        summary = compact_conversation(cheap, cands)
        self.ctx.apply_compaction(summary)
        self.hooks.compaction(summary)
        return True

    def _step_once(self, client: LLMClient, messages: list[ChatMessage]) -> ChatResponse:
        """Satu turn model; streaming delta ke UI via hooks."""
        text = ""
        tool_calls: list[dict] = []
        usage = None
        for ev in client.stream(messages):
            if ev.kind == "delta":
                text += ev.text
                self.hooks.delta(ev.text)
            elif ev.kind == "tool_call" and ev.tool_call:
                tool_calls.append(ev.tool_call)
            elif ev.kind == "done" and ev.usage:
                usage = ev.usage
        if not tool_calls:
            tc = parse_tool_call(text)
            if tc:
                tool_calls = [tc]
                text = ""
        return ChatResponse(
            message=ChatMessage(role="assistant", content=text, tool_calls=tool_calls or None),
            usage=usage or Usage(),
            model=client.model_name(),
        )

    def run(self, user_prompt: str, system_prompt: str) -> LoopResult:
        self.ctx.push(ChatMessage(role="user", content=user_prompt))
        result = LoopResult()
        client = self._pick_client(user_prompt)
        errors = 0
        last_text = ""

        for step in range(self.cfg.max_steps):
            # 1) kompaksi saat budget lunak tercapai
            if self.budget.should_compact and not result.compacted:
                result.compacted = self._compact(client)

            # 2) panggil model
            try:
                resp = self._step_once(client, self.ctx.render(system_prompt))
            except Exception as e:  # noqa: BLE001 — API error jangan crash agent
                result.final_text = f"[error API] {type(e).__name__}: {e}"
                self.hooks.finish(result)
                return result
            result.steps = step + 1
            last_text = resp.message.content
            if resp.usage:
                self.budget.add(
                    resp.usage.prompt_tokens,
                    resp.usage.completion_tokens,
                    resp.usage.cached_tokens,
                    tag=f"step{step}",
                )
            self.hooks.step(step, resp.model, resp.usage, self.budget.used)

            # 3) early-stop: jawaban final tanpa tool-call
            if not resp.message.tool_calls:
                result.final_text = last_text
                result.stopped_early = needs_change_check(last_text)
                self.hooks.finish(result)
                return result

            # 4) eksekusi tool (protokol: assistant msg dgn tool_calls, lalu hasil)
            self.ctx.push(
                ChatMessage(role="assistant", content="", tool_calls=resp.message.tool_calls)
            )
            for tc in resp.message.tool_calls:
                output = self.tools.execute(tc["name"], tc.get("arguments", {}))
                if output.startswith("ERROR"):
                    errors += 1
                output = output[: self.cfg.max_tool_output_chars]
                self.hooks.tool(tc["name"], tc.get("arguments", {}), output)
                self.ctx.push(
                    ChatMessage(role="tool", content=output, tool_call_id=tc["id"])
                )

            # 5) eskalasi cheap-first: model kecil gagal → model besar
            if (
                self.router is not None
                and errors >= self.cfg.escalate_after_errors
                and not result.escalated
            ):
                client = self._pick_client(user_prompt, force="big")
                result.escalated = True
                errors = 0

            # 6) budget keras
            if self.budget.exhausted:
                result.final_text = "[budget keras tercapai — sesi dihentikan, ketik /compact untuk lanjut]"
                result.budget_exhausted = True
                self.hooks.finish(result)
                return result

        result.final_text = last_text or "[max steps tercapai]"
        self.hooks.finish(result)
        return result
