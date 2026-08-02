"""AgentLoop — loop ReAct: stream model → parse tool call → eksekusi → observe.

Fitur hemat token:
- kompaksi konteks saat budget lunak tercapai (pakai model kecil bila ada router)
- early-stop saat model menjawab final (atau sinyal TIDAK ADA YANG PERLU DIUBAH)
- eskalasi model kecil → besar bila tool error berulang (cheap-first)
- budget keras menghentikan loop
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.parsing import dedupe_tool_calls, parse_tool_calls, strip_tool_block
from dhybrid.agent.streaming import ToolBlockFilter
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.compress import compact_conversation
from dhybrid.efficiency.context import ContextManager
from dhybrid.efficiency.lazy import needs_change_check
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, Usage
from dhybrid.tools.registry import ToolRegistry

BUILD_VERBS = ("buat", "buatkan", "bikin", "buatin", "tambahkan", "create", "make", "implement", "bangun")
MUTATING_TOOLS = {"apply_patch", "write_file", "git_commit"}
MAX_NUDGES = 2
NUDGE_MSG = (
    "[instruksi sistem dari user] Jangan bertanya — user meminta DIBUATKAN. "
    "Pilih stack default yang toolnya tersedia di sistem (cek: which php composer node npm python3), "
    "LANGSUNG buat file + verifikasi, lalu laporkan. Kerjakan sekarang, jangan tanya dulu."
)
SILENT_MSG = (
    "[instruksi sistem] Kamu sudah memakai tool tetapi belum memberi jawaban. "
    "Berikan jawaban akhir yang jelas SEKARANG (ringkas hasilnya)."
)
EXEC_MSG = (
    "[instruksi sistem] Kamu belum membuat/mengubah file apa pun (tidak ada write_file/apply_patch). "
    "User meminta DIBUATKAN. EKSEKUSI SEKARANG: buat file dengan write_file/apply_patch, "
    "verifikasi dengan perintah terkecil, lalu laporkan hasilnya."
)


COMPLETION_SIGNALS = ("selesai", "dibuat", "berhasil", "beres", "siap dipakai", "done", "completed", "success", "berfungsi")


def _looks_complete(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in COMPLETION_SIGNALS)


def _is_build_request(prompt: str) -> bool:
    low = prompt.lower()
    return any(v in low for v in BUILD_VERBS)


def _ends_with_question(text: str) -> bool:
    return bool(re.search(r"\?\s*$", text.strip()))


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

    def _used_mutating_tool(self) -> bool:
        """Ada tool yang mengubah file? (untuk keputusan nudge)."""
        return any(self.tools.tool_count.get(t, 0) > 0 for t in MUTATING_TOOLS)

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
        """Satu turn model; streaming delta ke UI via hooks (blok ```tool disembunyikan)."""
        text = ""
        tool_calls: list[dict] = []
        usage = None
        filt = ToolBlockFilter(self.hooks.delta) if self.hooks.on_delta else None
        if filt:
            filt.debug = bool(os.environ.get("DHYBRID_DEBUG"))
        for ev in client.stream(messages):
            if ev.kind == "delta":
                text += ev.text
                if filt:
                    filt.feed(ev.text)
            elif ev.kind == "tool_call" and ev.tool_call:
                tool_calls.append(ev.tool_call)
            elif ev.kind == "done" and ev.usage:
                usage = ev.usage
        if filt:
            filt.flush()
        fallback = False
        if not tool_calls:
            calls = dedupe_tool_calls(parse_tool_calls(text))
            if calls:
                tool_calls = calls
                text = strip_tool_block(text)  # mode teks: simpan teks, buang blok tool
                fallback = True
        return ChatResponse(
            message=ChatMessage(role="assistant", content=text, tool_calls=tool_calls or None),
            usage=usage or Usage(),
            model=client.model_name(),
            fallback_tool_call=fallback,
        )

    def run(self, user_prompt: str, system_prompt: str) -> LoopResult:
        self.ctx.push(ChatMessage(role="user", content=user_prompt))
        result = LoopResult()
        client = self._pick_client(user_prompt)
        errors = 0
        last_text = ""
        nudges = 0  # sudah disodok untuk mengerjakan (max MAX_NUDGES per run)

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
                is_empty = not last_text.strip()
                # NUDGE (max MAX_NUDGES): (a) model diam → minta jawaban;
                # (b) minta dibuatkan tapi bertanya/berjanji tanpa eksekusi file
                # → sodok agar LANGSUNG kerjakan.
                needs_exec = (
                    _is_build_request(user_prompt)
                    and not self._used_mutating_tool()
                    and not result.stopped_early
                    and not _looks_complete(last_text)
                )
                if nudges < MAX_NUDGES and not self.budget.exhausted and (is_empty or needs_exec):
                    nudges += 1
                    if is_empty:
                        msg = SILENT_MSG
                    elif _ends_with_question(last_text):
                        msg = NUDGE_MSG
                    else:
                        msg = EXEC_MSG
                    self.ctx.push(ChatMessage(role="user", content=msg))
                    continue
                result.final_text = last_text
                result.stopped_early = needs_change_check(last_text)
                self.hooks.finish(result)
                return result

            # 4) eksekusi tool
            if resp.fallback_tool_call:
                # MODE TEKS: hasil tool dikirim sebagai pesan user biasa —
                # kompatibel dengan model yang tidak support native tool-calling
                # (mis. deepseek-v4-flash-free via zen → format native ditolak 400).
                self.ctx.push(
                    ChatMessage(role="assistant", content=resp.message.content)
                )
                for tc in resp.message.tool_calls:
                    output = self.tools.execute(tc["name"], tc.get("arguments", {}))
                    if output.startswith("ERROR"):
                        errors += 1
                    output = output[: self.cfg.max_tool_output_chars]
                    self.hooks.tool(tc["name"], tc.get("arguments", {}), output)
                    self.ctx.push(
                        ChatMessage(
                            role="user",
                            content=f"[Hasil tool '{tc['name']}']\n{output}",
                        )
                    )
            else:
                # MODE NATIVE: protokol tool_calls + role:tool (OpenAI/Anthropic)
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
