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
from dataclasses import dataclass, field

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.text_parser import extract_tool_calls_from_text
from dhybrid.agent.quality import score_output
from dhybrid.agent.streaming import ToolBlockFilter
from dhybrid.agent.verify import count_created_files, snapshot_files, verify_build
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
CRITIQUE_MSG = (
    "[instruksi sistem] Review hasilmu sendiri sebelum selesai: apakah sudah lengkap, benar, "
    "dan sesuai permintaan user? Perbaiki kekurangan yang kamu temukan, lalu berikan jawaban "
    "akhir yang lebih baik."
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
    max_steps: int = 25                   # naik dari 20: lebih banyak ruang think
    max_tool_output_chars: int = 8000
    escalate_after_errors: int = 2
    self_critique: bool = True          # review diri untuk task kompleks
    quality_threshold: int = 35         # turun dari 40: lebih sensitif escalate
    max_nudges: int = 3                 # naik dari 2: lebih agresif nudge
    max_escalations: int = 2            # maksimal naik model berapa kali
    escalation_chain: list = field(default_factory=list)  # preset names untuk quality-based escalation
    escalation_cooldown_steps: int = 3  # jeda steps antar escalation (biar model bisa "pikir" dengan client baru)


@dataclass
class LoopResult:
    final_text: str = ""
    steps: int = 0
    compacted: bool = False
    stopped_early: bool = False
    escalated: bool = False
    budget_exhausted: bool = False
    quality_score: int = 100            # skor kualitas output (0-100)
    files_created: int = 0              # bukti nyata: file baru di workspace
    tests_passed: bool | None = None    # bukti nyata: test
    escalated_quality: bool = False     # pernah naik model karena skor rendah
    escalation_count: int = 0           # berapa kali naik model akibat quality rendah
    critiqued: bool = False             # pernah self-critique


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
        cwd: str = ".",
        client_factory=None,  # callable: preset_name -> LLMClient, untuk escalation chain
    ):
        self.router = client_or_router if hasattr(client_or_router, "route") else None
        self.client: LLMClient | None = None if self.router else client_or_router
        self.tools = tools
        self.ctx = ctx or ContextManager()
        self.budget = budget or TokenBudget()
        self.cfg = cfg or LoopConfig()
        self.hooks = hooks or Hooks()
        self.cwd = cwd
        self.tool_events: list[dict] = []  # jejak tool (untuk verifier & skor)
        self._client_factory = client_factory
        self._esc_idx = 0  # posisi di escalation_chain (0 = model awal)
        self._n_escalations = 0  # berapa kali udah naik model akibat quality rendah

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

    def _extract_facts(self, name: str, args: dict, output: str) -> None:
        """Ekstrak fakta sederhana dari tool output → ctx.facts.

        Mencegah agen bertanya hal yang sudah diketahui.
        """
        if not self.ctx.facts:
            return
        out = str(output).strip()
        # terminal: which <tool>
        if name == "terminal" and out and "not found" not in out.lower():
            cmd = (args or {}).get("command", "")
            if cmd.startswith("which "):
                tool_name = cmd[6:].split()[0] if len(cmd) > 6 else ""
                if tool_name:
                    self.ctx.facts.add_fact(f"{tool_name} tersedia di sistem")
        # read_file: file ada
        if name == "read_file" and out and not out.lower().startswith("error"):
            path = (args or {}).get("path", "")
            if path:
                self.ctx.facts.add_fact(f"file ada: {path}")
        # grep: ditemukan
        if name == "grep" and out and "not found" not in out.lower() and "\n" in out:
            pattern = (args or {}).get("pattern", "")
            if pattern:
                self.ctx.facts.add_fact(f"pattern '{pattern}' ditemukan di workspace")

    def _is_repeated_question(self, text: str) -> bool:
        """Cek apakah model bertanya hal yang sudah pernah kita tanyakan."""
        if not _ends_with_question(text):
            return False
        return self.ctx.facts.already_asked(text.strip())

    def _live_verify(self, step: int, before_files: set[str]) -> None:
        """Tiap 2 steps: cek file baru di workspace → inject evidence ke prompt.

        Ini memungkinkan model tahu progres secara real-time, bukan tunggu akhir.
        """
        if step % 2 != 0 or step <= 0:  # hanya di step genap (2, 4, 6, ...)
            return
        after = snapshot_files(self.cwd)
        created = count_created_files(before_files, after)
        if created > 0:
            self.ctx.facts.add_fact(f"{created} file baru terbuat di step {step}")

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
            calls = extract_tool_calls_from_text(text)
            if calls:
                tool_calls = calls
                text = ""  # mode teks: simpan teks, buang blok tool (sudah di-parse)
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
        critiqued = False
        before_files = snapshot_files(self.cwd)
        self.tool_events = []

        for step in range(self.cfg.max_steps):
            # 1) kompaksi saat budget lunak tercapai
            if self.budget.should_compact and not result.compacted:
                result.compacted = self._compact(client)

            # 2) panggil model
            try:
                resp = self._step_once(client, self.ctx.render(system_prompt))
            except Exception as e:  # noqa: BLE001 — API error
                # RETRY: coba ke model berikutnya di escalation chain
                # (jangan langsung stop — agen tetap berjuang sampai semua model gagal)
                if (
                    self.cfg.escalation_chain
                    and self._client_factory is not None
                    and self._n_escalations < self.cfg.max_escalations
                    and self._esc_idx < len(self.cfg.escalation_chain)
                ):
                    self._esc_idx += 1
                    self._n_escalations += 1
                    result.escalated_quality = True
                    result.escalation_count = self._n_escalations
                    next_preset = self.cfg.escalation_chain[self._esc_idx - 1]
                    client = self._client_factory(next_preset)
                    self.ctx.push(ChatMessage(
                        role="user",
                        content=f"[sistem] Gagal ke model sebelumnya ({type(e).__name__}). "
                                f"Coba model kuat berikutnya: {next_preset}. Silakan lanjutkan."
                    ))
                    continue
                # semua model gagal → berhenti dengan error yang jelas
                result.final_text = f"[error API] {type(e).__name__}: {e}"
                result.quality_score = 0
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
            # live verify: cek file baru tiap 2 steps (setelah step 2)
            if step > 0:
                self._live_verify(step, before_files)

            # 3) early-stop: jawaban final tanpa tool-call
            if not resp.message.tool_calls:
                # ukur kualitas + bukti nyata (file/test) untuk keputusan
                v = verify_build(self.cwd, before_files, snapshot_files(self.cwd), self.tool_events)
                is_build = _is_build_request(user_prompt)
                score = score_output(
                    last_text,
                    is_build=is_build,
                    tools_used=len(self.tool_events),
                    files_created=v["files_created"],
                    tests_passed=v["tests_passed"],
                )
                result.quality_score = score
                result.files_created = v["files_created"]
                result.tests_passed = v["tests_passed"]
                result.stopped_early = needs_change_check(last_text)
                is_empty = not last_text.strip()

                if not self.budget.exhausted:
                    # 3d-FIRST) Quality-based escalation: skor rendah → langsung naik model kuat
                    # Prioritaskan ini di atas nudge — jika kualitas jelek, jangan nyoba-nyoba nudge.
                    if (
                        score < self.cfg.quality_threshold
                        and self.cfg.escalation_chain
                        and self._client_factory is not None
                        and self._n_escalations < self.cfg.max_escalations
                        and self._esc_idx < len(self.cfg.escalation_chain)
                    ):
                        self._esc_idx += 1
                        self._n_escalations += 1
                        result.escalated_quality = True
                        result.escalation_count = self._n_escalations
                        next_preset = self.cfg.escalation_chain[self._esc_idx - 1]
                        client = self._client_factory(next_preset)
                        esc_msg = (
                            f"[sistem escalation] Skor kualitas rendah ({score}/100). "
                            f"Beralih ke model yang lebih kuat: {next_preset}. "
                            f"Selesaikan penuh tanpa bertanya, tanpa berjanji — lakukan eksekusi nyata."
                        )
                        self.ctx.push(ChatMessage(role="user", content=esc_msg))
                        continue
                    # catat pertanyaan yang sudah diajukan (mencegah loop bertanya)
                    if _ends_with_question(last_text):
                        self.ctx.facts.mark_asked(last_text.strip())
                    # 3a) model diam → minta jawaban
                    if is_empty and nudges < self.cfg.max_nudges:
                        nudges += 1
                        self.ctx.push(ChatMessage(role="user", content=SILENT_MSG))
                        continue
                    # 3b) nudge build: bertanya/berjanji tanpa eksekusi file
                    if (
                        not result.stopped_early
                        and nudges < self.cfg.max_nudges
                        and is_build
                        and not self._used_mutating_tool()
                        and not _looks_complete(last_text)
                        and not is_empty
                    ):
                        nudges += 1
                        msg = NUDGE_MSG if _ends_with_question(last_text) else EXEC_MSG
                        self.ctx.push(ChatMessage(role="user", content=msg))
                        continue
                    # 3c) self-critique: hanya bila model sudah BERTINDAK (pakai tool)
                    if (
                        not critiqued
                        and self.cfg.self_critique
                        and score < 90
                        and len(self.tool_events) > 0
                        and (is_build or len(user_prompt) >= 150)
                    ):
                        critiqued = True
                        result.critiqued = True
                        self.ctx.push(ChatMessage(role="user", content=CRITIQUE_MSG))
                        continue

                result.final_text = last_text
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
                    self.tool_events.append({"name": tc["name"], "args": tc.get("arguments", {}), "output": output})
                    self.hooks.tool(tc["name"], tc.get("arguments", {}), output)
                    self._extract_facts(tc["name"], tc.get("arguments", {}), output)
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
                    self.tool_events.append({"name": tc["name"], "args": tc.get("arguments", {}), "output": output})
                    self.hooks.tool(tc["name"], tc.get("arguments", {}), output)
                    self._extract_facts(tc["name"], tc.get("arguments", {}), output)
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
