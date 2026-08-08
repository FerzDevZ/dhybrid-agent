"""AgentLoop — ReAct loop using state machine, nudge controller, and escalation policy.

This is the refactored version that composes the new modular components.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from dhybrid.agent.auto_verify import VerificationReport, run_verification
from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop.escalation_policy import EscalationConfig, EscalationPolicy
from dhybrid.agent.loop.nudge_controller import NudgeConfig, NudgeController
from dhybrid.agent.loop.state_machine import LoopState, StateMachine
from dhybrid.agent.loop.step_executor import StepConfig, StepExecutor
from dhybrid.agent.parsing import strip_tool_block
from dhybrid.agent.quality import score_output
from dhybrid.agent.reasoning import ReasoningTrace
from dhybrid.agent.verify import count_created_files, snapshot_files, verify_build
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.checkpoint import (
    RunCheckpoint,
    load_run_checkpoint,
    save_run_checkpoint,
)
from dhybrid.efficiency.compress import compact_conversation
from dhybrid.efficiency.context import ContextManager
from dhybrid.efficiency.lazy import needs_change_check
from dhybrid.efficiency.predictor import PredictionLevel, RunPrediction, TokenPredictor
from dhybrid.health import HealthMonitor
from dhybrid.llm.base import ChatMessage, LLMClient
from dhybrid.security.guard import AuditLogger
from dhybrid.tools.registry import ToolRegistry

BUILD_VERBS = (
    "buat", "buatkan", "bikin", "buatin", "tambahkan", "tambah", "create", "make",
    "implement", "implementasikan", "bangun", "kerjakan", "kerjain", "setup",
    "set-up", "pasang", "install", "scaffold", "generate", "tulis", "tuliskan",
    "tulisin", "selesaikan", "selesaikin", "perbaiki", "perbaikin", "fix",
    "refactor", "optimasi", "optimalkan", "hapus", "remove", "delete", "ubah",
    "modif", "modifikasi", "migrate", "deploy",
)
MUTATING_TOOLS = {"apply_patch", "write_file", "git_commit"}
MAX_NUDGES = 2

INTENT_HINTS = (
    "saya akan", "aku akan", "akan saya", "akan kucek", "akan kucoba", "nanti saya",
    "nanti akan", "saya lanjutkan", "mari kita", "mari mulai", "sekarang saya",
    "berikutnya saya", "saya mulai", "saya cek dulu", "saya periksa dulu",
    "saya akan cek", "saya akan start", "saya akan jalankan", "saya akan buat",
    "lanjut eksekusi", "lanjut kerjakan", "lanjut setup",
    "mari verifikasi", "mari cek", "mari jalankan", "mari buat", "mari mulai",
)

COMPLETION_SIGNALS = ("selesai", "dibuat", "berhasil", "beres", "siap dipakai", "done", "completed", "success", "berfungsi")


def _looks_complete(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in COMPLETION_SIGNALS)


def _expresses_intent(text: str) -> bool:
    low = (text or "").lower().strip()
    if not low:
        return False
    if low.endswith(":") and len(low) > 15:
        return True
    return any(h in low for h in INTENT_HINTS)


def _is_build_request(prompt: str) -> bool:
    low = prompt.lower()
    return any(v in low for v in BUILD_VERBS)


def _is_continuation(prompt: str) -> bool:
    low = prompt.lower().strip()
    if any(v in low for v in ("lanjutkan", "lanjutin", "lanjut", "teruskan", "continue", "silahkan")):
        return True
    words = low.split()
    return len(words) <= 3 and any(
        v in low for v in ("ya", "yes", "ok", "oke", "iya", "ayo", "gas", "setuju", "next")
    )


def _is_transient_error(e: Exception) -> bool:
    s = str(e).lower()
    markers = (
        "429", "500", "502", "503", "504",
        "too many requests", "rate limit",
        "temporary failure", "name resolution",
        "connection", "connect error",
        "timed out", "timeout", "reset by peer", "gateway",
    )
    return any(m in s for m in markers)


def _ends_with_question(text: str) -> bool:
    return bool(re.search(r"\?\s*$", text.strip()))


@dataclass
class LoopConfig:
    max_steps: int = 25
    max_tool_output_chars: int = 8000
    escalate_after_errors: int = 2
    self_critique: bool = True
    quality_threshold: int = 35
    max_nudges: int = 3
    max_escalations: int = 2
    max_reflections: int = 2
    predict_budget: bool = True
    auto_verify: bool = True
    auto_verify_timeout_s: int = 60
    max_repair_rounds: int = 2
    checkpoint_every: int = 0      # 0 = off; >0 simpan snapshot tiap N langkah
    checkpoint_dir: str | None = None
    audit_dir: str | None = None   # ≥0 = jalur audit log (JSONL) tool eksekusi
    escalation_chain: list = field(default_factory=list)
    # Konfirmasi user sebelum eskalasi. None = otomatis (mode lama).
    escalation_confirm_fn: callable | None = None
    escalation_cooldown_steps: int = 3


@dataclass
class LoopResult:
    final_text: str = ""
    steps: int = 0
    compacted: bool = False
    stopped_early: bool = False
    escalated: bool = False
    budget_exhausted: bool = False
    quality_score: int = 100
    files_created: int = 0
    tests_passed: bool | None = None
    escalated_quality: bool = False
    escalation_count: int = 0
    critiqued: bool = False
    reflect_iterations: int = 0
    budget_predicted_total: int = 0
    budget_prediction_level: str = "ok"
    audit_records: int = 0
    auto_verify_ran: bool = False
    auto_verify_passed: bool | None = None
    auto_verify_runner: str | None = None
    auto_verify_log_tail: list[str] = field(default_factory=list)
    pending_question: dict | None = None
    reasoning_trace: ReasoningTrace = field(default_factory=ReasoningTrace)


class AgentLoop:
    """Refactored AgentLoop using modular components."""

    def __init__(
        self,
        client_or_router,
        tools: ToolRegistry,
        ctx: ContextManager | None = None,
        budget: TokenBudget | None = None,
        cfg: LoopConfig | None = None,
        hooks: Hooks | None = None,
        cwd: str = ".",
        client_factory=None,
        ask_state=None,
        clarify_state=None,
    ):
        self.router = client_or_router if hasattr(client_or_router, "route") else None
        self.client: LLMClient | None = None if self.router else client_or_router
        self.tools = tools
        self.ctx = ctx or ContextManager()
        self.budget = budget or TokenBudget()
        self.cfg = cfg or LoopConfig()
        self.hooks = hooks or Hooks()
        self.cwd = cwd
        self.ask_state = ask_state
        self.clarify_state = clarify_state
        self.tool_events: list[dict] = []
        self.reasoning_trace = ReasoningTrace()
        self._client_factory = client_factory
        self.reflect_iterations = 0
        # Predictive Token Budget state (dibuat lazily saat run pertama)
        self.predictor: TokenPredictor | None = None
        self._prediction: RunPrediction | None = None
        self._budget_warned = False
        self._cheapened = False
        # Verify→Repair loop: jumlah iterasi perbaikan yang sudah dipakai.
        self._repair_rounds = 0
        # Health monitoring provider LLM (failover proaktif)
        self.health = HealthMonitor()
        self._failover_notified = False
        self._pending_result: LoopResult | None = None
        # Audit log append-only tool eksekusi (JSONL) — `audit_dir` dari config
        self._audit: AuditLogger | None = AuditLogger(cfg.audit_dir) if self.cfg.audit_dir else None
        self._run_key = None

        # Initialize modular components
        self._init_components()

    def _init_components(self) -> None:
        """Initialize all modular components."""
        # State machine
        self.state_machine = StateMachine(
            on_transition=self._on_state_transition,
        )

        # Nudge controller
        nudge_cfg = NudgeConfig(
            max_nudges=self.cfg.max_nudges,
            intent_budget_multiplier=2 if not self.cfg.escalation_chain else 1,
        )
        self.nudge_controller = NudgeController(
            config=nudge_cfg,
            state_machine=self.state_machine,
            hooks=self.hooks,
            has_escalation_chain=bool(self.cfg.escalation_chain),
            push_message=self.ctx.push,
        )

        # Escalation policy
        esc_cfg = EscalationConfig(
            escalation_chain=self.cfg.escalation_chain,
            max_escalations=self.cfg.max_escalations,
            escalation_cooldown_steps=self.cfg.escalation_cooldown_steps,
            quality_threshold=self.cfg.quality_threshold,
            client_factory=self._client_factory,
            confirm_fn=self.cfg.escalation_confirm_fn,
        )
        self.escalation_policy = EscalationPolicy(
            config=esc_cfg,
            hooks=self.hooks,
        )

        # Step executor
        step_cfg = StepConfig(max_tool_output_chars=self.cfg.max_tool_output_chars)
        self.step_executor = StepExecutor(
            client=self.client or (self.router.route("") if self.router else None),  # will be updated per step
            tools=self.tools,
            hooks=self.hooks,
            reasoning_trace=self.reasoning_trace,
            config=step_cfg,
            cwd=self.cwd,
        )

    def _on_state_transition(self, transition) -> None:
        """Hook for state transitions (logging, metrics)."""
        self.hooks.state_transition(
            transition.from_state.value,
            transition.to_state.value,
            transition.reason,
        )

    @staticmethod
    def _provider_key(client: LLMClient | None, resp=None) -> str:
        """Kunci provider: nama model (atau fallback nama kelas client)."""
        if resp is not None and getattr(resp, "response", None) and resp.response.model:
            return resp.response.model
        model = getattr(client, "model", None)
        if model:
            return model
        return type(client).__name__ if client is not None else "unknown"

    def _escalation_allowed(self, reason: str) -> bool:
        """Gate izin user untuk eskalasi. None (default) = otomatis (lama)."""
        if self.cfg.escalation_confirm_fn is None:
            return True
        return self.cfg.escalation_confirm_fn(reason)

    def _pick_client(self, prompt: str, force: str | None = None) -> LLMClient:
        if self.router is not None:
            client = self.router.route(prompt, force=force)
            # Failover proaktif: hindari provider yang terbukti bermasalah,
            # selama tidak sedang dipaksa (force=big untuk escalation).
            if not force and not self.health.is_healthy(self._provider_key(client)):
                alt = self.router.small if client is self.router.big else self.router.big
                if alt is not None and self.health.is_healthy(self._provider_key(alt)):
                    if not self._failover_notified:
                        self._failover_notified = True
                        self.ctx.push(ChatMessage(role="user", content=(
                            "[sistem] Penyedia model ini sedang bermasalah — beralih "
                            "ke model cadangan sementara."
                        )))
                    return alt
            return client
        return self.client  # type: ignore[return-value]

    def _used_mutating_tool(self) -> bool:
        return any(self.tools.tool_count.get(t, 0) > 0 for t in MUTATING_TOOLS)

    def _compact(self, client: LLMClient) -> bool:
        cands = self.ctx.candidates_for_compaction()
        if not cands:
            return False
        cheap = self.router.small if self.router is not None else client
        summary = compact_conversation(cheap, cands)
        self.ctx.apply_compaction(summary)
        self.hooks.compaction(summary)
        return True

    def _extract_facts(self, name: str, args: dict, output: str) -> None:
        if not self.ctx.facts:
            return
        out = str(output).strip()
        if name == "terminal" and out and "not found" not in out.lower():
            cmd = (args or {}).get("command", "")
            if cmd.startswith("which "):
                tool_name = cmd[6:].split()[0] if len(cmd) > 6 else ""
                if tool_name:
                    self.ctx.facts.add_fact(f"{tool_name} tersedia di sistem")
        if name == "read_file" and out and not out.lower().startswith("error"):
            path = (args or {}).get("path", "")
            if path:
                self.ctx.facts.add_fact(f"file ada: {path}")
        if name == "grep" and out and "not found" not in out.lower() and "\n" in out:
            pattern = (args or {}).get("pattern", "")
            if pattern:
                self.ctx.facts.add_fact(f"pattern '{pattern}' ditemukan di workspace")

    def _is_repeated_question(self, text: str) -> bool:
        if not _ends_with_question(text):
            return False
        return self.ctx.facts.already_asked(text.strip())

    def _live_verify(self, step: int, last_snapshot: set[str]) -> set[str]:
        if step % 2 != 0 or step <= 0:
            return last_snapshot
        after = snapshot_files(self.cwd)
        created = count_created_files(last_snapshot, after)
        if created > 0:
            self.ctx.facts.add_fact(f"{created} file baru terbuat (step {step})")
            self.ctx.push(
                ChatMessage(
                    role="user",
                    content=(
                        f"[verifikasi] Sistem mendeteksi {created} file baru di workspace. "
                        "Lanjutkan pekerjaan; kalau sudah tuntas beri ringkasan singkat & akurat."
                    ),
                )
            )
            return after
        return last_snapshot

    def _maybe_pause_for_user(self, result: LoopResult, last_text: str) -> bool:
        for st in (self.ask_state, self.clarify_state):
            if st is not None and st.pending:
                result.pending_question = st.pending
                st.pending = None
                result.final_text = (
                    (last_text or "").strip() or "Pertanyaan diajukan ke user — menunggu jawaban."
                )
                self.hooks.finish(result)
                return True
        return False

    def _measure_output(
        self, user_prompt: str, last_text: str, before_files: set[str]
    ) -> tuple[dict, bool, int]:
        v = verify_build(self.cwd, before_files, snapshot_files(self.cwd), self.tool_events)
        is_build = _is_build_request(user_prompt)
        if not is_build and _is_continuation(user_prompt):
            recent = [
                m.content or ""
                for m in self.ctx.messages[-10:]
                if m.role == "user" and not (m.content or "").lstrip().startswith("[")
            ]
            if any(_is_build_request(u) for u in recent):
                is_build = True
        score = score_output(
            last_text,
            is_build=is_build,
            tools_used=len(self.tool_events),
            files_created=v["files_created"],
            tests_passed=v["tests_passed"],
        )
        return v, is_build, score

    def _system_prompt_for(self, base: str, prompt: str) -> str:
        """System prompt akhir: base + blok tool JIT (subset sesuai intent).

        Tool yang di-inject hanya yang relevan dgn prompt → menghemat token
        dibanding meng-inject seluruh daftar tool ~100 di setiap langkah.
        """
        tools_block = self.tools.spec_text_for(prompt)
        return f"{base}\n\n{tools_block}" if tools_block else base

    def _maybe_reflect(
        self, score: int, is_build: bool, evidence: bool, says_done: bool, asks_qa: bool
    ) -> bool:
        """Reflection loop — fase Reflect wajib sebelum finalisasi.

        Memaksa model meninjau hasilnya secara kritis (bandingkan dgn permintaan,
        verifikasi dgn tool bila perlu). TERBATAS oleh max_reflections, dan sengaja
        SKIP untuk kasus yang sudah punya budget nudge sendiri:
        - asks_qa   → ditangani nudge "continue-build" (bounded).
        - says_done → ditangani nudge "evidence" (bounded).
        Refleksi hanya untuk jawaban final yang buntu (build tanpa bukti / skor
        rendah) yang masih bisa dibantu satu tinjauan lagi.
        """
        if not self.cfg.self_critique:
            return False
        if self.reflect_iterations >= self.cfg.max_reflections:
            return False
        if says_done or asks_qa:
            return False
        needs_reflect = (is_build and not evidence) or score < self.cfg.quality_threshold
        if not needs_reflect:
            return False
        self.reflect_iterations += 1
        self.ctx.push(ChatMessage(role="user", content=(
            f"[refleksi {self.reflect_iterations}] Sebelum menyelesaikan, REVIEW hasilmu "
            "dengan kritis:\n"
            "- Sudahkah memenuhi SEMUA permintaan user? Apa yang kurang atau terlewat?\n"
            "- Verifikasi dengan tool bila perlu (baca file, jalankan test) — jangan menebak.\n"
            "- Perbaiki kekurangan yang kamu temukan, lalu beri jawaban akhir ringkas & akurat."
        )))
        self.hooks.nudge("reflect", f"Reflection pass {self.reflect_iterations}")
        return True

    # ---------- Predictive Token Budget ----------

    def _update_budget_prediction(self, prompt: str, system_prompt: str, steps_done: int):
        """Perbarui proyeksi token run; simpan di self._prediction untuk dipakai
        hasilnya (warning / auto-cheapen) oleh langkah berikutnya."""
        if not self.cfg.predict_budget:
            return None
        if self.predictor is None:
            self.predictor = TokenPredictor(hard_budget=self.budget.hard)
        self._prediction = self.predictor.predict(
            prompt, system_prompt, self.budget.used, steps_done, self.budget.history
        )
        return self._prediction

    def _copy_prediction(self, result: LoopResult) -> None:
        if self._prediction:
            result.budget_predicted_total = self._prediction.projected_total
            result.budget_prediction_level = self._prediction.level.value

    def _run_auto_verify(self, before: set[str]) -> VerificationReport | None:
        """Jika build membuat file baru, jalankan test ringkas sebagai bukti.

        Hasil disimpan ke result + dicatat di trace. Return report (None bila
        tidak ada file baru / fitur off) supaya caller bisa memutuskan repair."""
        if not self.cfg.auto_verify:
            return None
        new_files = snapshot_files(self.cwd) - before
        created_count = len({f for f in new_files if not f.startswith(".")})
        if created_count == 0:
            return None
        report = run_verification(self.cwd, new_files, timeout_s=self.cfg.auto_verify_timeout_s)
        result = self._pending_result
        if isinstance(result, LoopResult):
            result.auto_verify_ran = report.ran
            result.auto_verify_passed = report.passed
            result.auto_verify_runner = report.runner
            result.auto_verify_log_tail = list(report.log_tail)
            if report.ran:
                summary = report.summarize()
                self.hooks.nudge("auto_verify", summary)
                if report.log_tail and report.passed is False:
                    self.ctx.push(ChatMessage(role="user", content=(
                        f"[auto-verify] {summary}\n" + "\n".join(report.log_tail[-6:])
                    )))
                    self.reasoning_trace.add_step("auto_verify_fail", summary, [])
        return report

    # ---------- Mid-run checkpoint ----------

    def _checkpoint_path(self, prompt: str) -> str | None:
        if not self.cfg.checkpoint_every or not self.cfg.checkpoint_dir:
            return None
        key = hashlib.sha1(f"{self.cwd}::{prompt}".encode(), usedforsecurity=False).hexdigest()[:12]
        return str(Path(self.cfg.checkpoint_dir) / f"run_{key}.json")

    def _write_checkpoint(self, prompt: str, system_prompt: str, step: int) -> None:
        path = self._checkpoint_path(prompt)
        if not path:
            return
        if self.cfg.checkpoint_every > 0 and (step + 1) % self.cfg.checkpoint_every != 0:
            return
        ckpt = RunCheckpoint(
            run_id=hashlib.sha1(f"{self.cwd}::{prompt}".encode(), usedforsecurity=False).hexdigest()[:12],
            step=step + 1,
            prompt=prompt,
            system_prompt=system_prompt,
            cwd=self.cwd,
            budget_used=self.budget.used,
            budget_history=list(self.budget.history),
            reflect_iterations=self.reflect_iterations,
            repair_rounds=self._repair_rounds,
            messages=[
                {"role": m.role, "content": m.content}
                for m in self.ctx.messages
                if m.content  # buang tool_call-only
            ],
        )
        save_run_checkpoint(path, ckpt)

    def _run_id(self, prompt: str) -> str:
        """Kunci stabil utk sebuah run (cwd+prompt) — dipakai audit & checkpoint."""
        return hashlib.sha1(f"{self.cwd}::{prompt}".encode(), usedforsecurity=False).hexdigest()[:12]

    def _maybe_repair(self, report: VerificationReport) -> bool:
        """Verify→Repair: auto-verify GAGAL → injeksi koreksi + lanjutkan loop
        (model memperbaiki, test diulang di finalisasi berikutnya). Terbatas
        max_repair_rounds agar tidak infinite loop."""
        if report is None or report.passed is not False:
            return False
        if self._repair_rounds >= self.cfg.max_repair_rounds:
            return False
        self._repair_rounds += 1
        summary = report.summarize()
        self.ctx.push(ChatMessage(role="user", content=(
            f"[repair {self._repair_rounds}] Test hasil build GAGAL ({summary}). "
            "PERBAIKI sekarang: analisis log error di atas, cari akar masalahnya, "
            "ubah kode dengan tool, lalu biarkan loop memverifikasi ulang."
        )))
        self.hooks.nudge("repair", f"repair round {self._repair_rounds}")
        return True

    def _bind_result_to_verify(self, result: LoopResult) -> None:
        self._pending_result = result

    def _maybe_warn_budget(self, pred: RunPrediction) -> None:
        """Sekali per run: peringatkan model bila proyeksi mendekati batas."""
        if self._budget_warned or pred.remaining_steps <= 0:
            return
        self._budget_warned = True
        self.ctx.push(ChatMessage(role="user", content=(
            f"[budget proyeksi] Estimasi akan memakai ~{pred.projected_total:,} token "
            f"(sisa {pred.remaining:,}). Ringkas jawaban, prioritaskan langkah terpenting, "
            "pakai perintah kecil. Siapkan /compact bila konteks penuh."
        )))
        self.hooks.nudge("budget_warn", f"projected={pred.projected_total}")

    def _maybe_cheapen(self, cur: LLMClient) -> LLMClient | None:
        """Saat proyeksi kritis & memakai model besar → auto-switch ke model
        kecil (hemat) untuk sisa run. Sekali per run."""
        if self.router is None or self._cheapened:
            return None
        if cur is None or cur is self.router.small:
            return None
        if getattr(self.router, "last_class", "small") != "big":
            return None
        self._cheapened = True
        self.ctx.push(ChatMessage(role="user", content=(
            "[budget] Proyeksi melebihi batas → beralih ke model kecil sekarang. "
            "Rampungkan pekerjaan dengan langkah sesedikit & se-ringan mungkin."
        )))
        self.hooks.nudge("cheapen", "switched to small model")
        return self.router.small

    def _finalize_response(self, last_text: str, result: LoopResult) -> str:
        clean = strip_tool_block(last_text or "").strip()
        if clean:
            return clean
        bits: list[str] = []
        if result.files_created:
            bits.append(f"{result.files_created} file dibuat/diubah")
        cmds = [
            (ev.get("args") or {}).get("command")
            for ev in self.tool_events
            if ev.get("name") == "terminal"
        ]
        cmds = [c for c in cmds if c]
        if cmds:
            bits.append(f"{len(cmds)} perintah terminal dijalankan")
        if result.tests_passed is True:
            bits.append("test LULUS")
        elif result.tests_passed is False:
            bits.append("test GAGAL")
        detail = ", ".join(bits) if bits else "langkah sudah dieksekusi"
        return (
            f"Pekerjaan selesai — {detail}.\n"
            "Mau saya lanjutkan? Ketik apa yang mau diperbaiki/ditambah berikutnya, "
            "misalnya fitur login/register lengkap, styling, atau jalankan test."
        )

    def run(self, user_prompt: str, system_prompt: str, push_prompt: bool = True) -> LoopResult:
        # Mid-run resume: bila checkpoint run ini ada (crash/Ctrl-C), muat ulang
        # konteks + budget & lanjut dari langkah tersimpan, bukan mulai nol.
        ckpt: RunCheckpoint | None = None
        cpath = self._checkpoint_path(user_prompt)
        if cpath:
            ckpt = load_run_checkpoint(cpath)
        if ckpt is not None:
            for m in ckpt.messages:
                self.ctx.push(ChatMessage(role=m["role"], content=m["content"]))
            self.hooks.nudge("resume", f"resumed from step {ckpt.step}")
        elif push_prompt:
            self.ctx.push(ChatMessage(role="user", content=user_prompt))
        start_step = ckpt.step if ckpt is not None else 0
        result = LoopResult()
        
        # Initial state
        self.state_machine.transition(LoopState.THINKING, "start run")
        
        client = self._pick_client(user_prompt)
        self.step_executor.client = client
        
        errors = 0
        last_text = ""
        hard_nudged = False
        transient_retries = 0
        before_files = snapshot_files(self.cwd)
        last_snapshot = before_files
        self.tool_events = []
        self.reasoning_trace.clear()
        self.reasoning_trace.add_step("start", f"Starting task: {user_prompt[:100]}", [])
        self.tools.reset_counts()
        self._bind_result_to_verify(result)

        # Reset modular components for new run
        self.nudge_controller.nudges_given = 0
        self.nudge_controller.config.hard_nudge_given = False
        self.nudge_controller.config.critiqued = False
        self.escalation_policy.reset()
        self.reflect_iterations = 0
        self._prediction = None
        self._budget_warned = False
        self._cheapened = False
        # Reset health run-state: sehat/buruk berlaku per run, tidak lintas run —
        # deterministik & tidak bawa "hukuman" provider dari sesi lain.
        self.health.clear()
        self._failover_notified = False

        # Mid-run resume: restore budget + penghitung dari checkpoint
        if ckpt is not None:
            self.budget.used = ckpt.budget_used
            self.budget.history = list(ckpt.budget_history)
            self.reflect_iterations = ckpt.reflect_iterations
            self._repair_rounds = ckpt.repair_rounds

        for step in range(start_step, self.cfg.max_steps):
            # 1) Compaction when soft budget reached
            if self.budget.should_compact and not result.compacted:
                self.state_machine.transition(LoopState.COMPACTING, "soft budget reached")
                result.compacted = self._compact(client)
                self.state_machine.transition(LoopState.THINKING, "compaction done")

            # 2) Call model
            try:
                self.state_machine.transition(LoopState.THINKING, f"step {step + 1}")
                _t0 = time.perf_counter()
                resp = self.step_executor.execute(
                    self.ctx.render(self._system_prompt_for(system_prompt, user_prompt))
                )
                self.health.record(
                    self._provider_key(client, resp), True, (time.perf_counter() - _t0) * 1000
                )
            except Exception as e:  # noqa: BLE001 — transient model/provider error handling
                self.health.record(self._provider_key(client), False, 0.0)
                # Handle transient errors
                if _is_transient_error(e) and transient_retries < 2 and not self.budget.exhausted:
                    transient_retries += 1
                    self.ctx.push(ChatMessage(role="user", content=(
                        f"[sistem] Gagal sementara ({type(e).__name__}) — coba ulang "
                        f"({transient_retries}/2)."
                    )))
                    time.sleep(min(2 ** transient_retries, 5))
                    continue
                # Escalate on error
                esc_result = self.escalation_policy.escalate_for_errors(step, e)
                if esc_result.escalated:
                    client = esc_result.new_client
                    self.step_executor.client = client
                    result.escalated_quality = True
                    result.escalation_count = esc_result.escalation_count
                    self.ctx.push(ChatMessage(
                        role="user",
                        content=f"[sistem] {esc_result.reason} Coba model: {esc_result.preset_name}. Lanjutkan."
                    ))
                    continue
                # All failed
                if _is_transient_error(e):
                    result.final_text = (
                        "⚠️ Penyedia model sedang sibuk/menolak (rate limit atau timeout). "
                        "Tunggu sebentar lalu ulangi, atau ganti model lain via /settings."
                    )
                else:
                    result.final_text = f"[error API] {type(e).__name__}: {e}"
                result.quality_score = 0
                self.state_machine.transition(LoopState.ERROR, "api error exhausted")
                self.hooks.finish(result)
                return result

            result.steps = step + 1
            last_text = resp.response.message.content
            if resp.response.usage:
                self.budget.add(
                    resp.response.usage.prompt_tokens,
                    resp.response.usage.completion_tokens,
                    resp.response.usage.cached_tokens,
                    tag=f"step{step}",
                )
            self.hooks.step(step, resp.response.model, resp.response.usage, self.budget.used)

            # Predictive Token Budget: proyeksi + warn/auto-cheapen (untuk step berikutnya)
            pred = self._update_budget_prediction(user_prompt, system_prompt, step)
            if pred and pred.level is PredictionLevel.CRITICAL:
                cheap = self._maybe_cheapen(client)
                if cheap is not None:
                    client = cheap
                    self.step_executor.client = cheap
            elif pred and pred.level is PredictionLevel.WARNING:
                self._maybe_warn_budget(pred)

            # Record tool events
            self.tool_events.extend(resp.tool_events)
            # Audit trail append-only (opsional): tiap tool yg dieksekusi step ini
            if self._audit is not None and resp.tool_events:
                if self._run_key is None:
                    self._run_key = self._run_id(user_prompt)
                for ev in resp.tool_events:
                    self._audit.log_tool(
                        run_id=self._run_key,
                        step=step,
                        name=ev.get("name", "?"),
                        args=ev.get("args", {}),
                        result=ev.get("output") or "",
                        model=self._provider_key(self.step_executor.client, resp),
                    )
                    result = self._pending_result
                    if isinstance(result, LoopResult):
                        result.audit_records += 1
            self._write_checkpoint(user_prompt, system_prompt, step)

            # Live verify every 2 steps
            if step > 0:
                last_snapshot = self._live_verify(step, last_snapshot)

            # 3) Early stop check (no tool calls)
            if not resp.response.message.tool_calls:
                v, is_build, score = self._measure_output(user_prompt, last_text, before_files)
                result.quality_score = score
                result.files_created = v["files_created"]
                result.tests_passed = v["tests_passed"]
                result.stopped_early = needs_change_check(last_text)
                is_empty = not last_text.strip()
                asks_qa = _ends_with_question(last_text)
                repeated_qa = self._is_repeated_question(last_text)
                says_done = _looks_complete(last_text)
                evidence = (
                    v["files_created"] > 0
                    or v["tests_passed"] is True
                    or self._used_mutating_tool()
                )

                if not self.budget.exhausted:
                    if asks_qa or repeated_qa:
                        self.ctx.facts.mark_asked(last_text.strip())

                    # Quality-based escalation
                    esc_result = self.escalation_policy.escalate_for_quality(
                        current_step=step,
                        score=score,
                        is_build=is_build,
                        asks_qa=asks_qa,
                        repeated_qa=repeated_qa,
                    )
                    if esc_result.escalated:
                        client = esc_result.new_client
                        self.step_executor.client = client
                        result.escalated_quality = True
                        result.escalation_count = esc_result.escalation_count
                        self.ctx.push(ChatMessage(role="user", content=(
                            f"[sistem escalation] {esc_result.reason} Beralih ke model: {esc_result.preset_name}. "
                            "Selesaikan penuh tanpa bertanya/janji — lakukan eksekusi nyata."
                        )))
                        self.state_machine.transition(LoopState.ESCALATING, "quality escalation")
                        continue

                    # Nudge: silent model
                    if is_empty and self.nudge_controller.nudge_silent():
                        self.state_machine.transition(LoopState.NUDGING, "silent nudge")
                        continue

                    # Nudge: intent without execution
                    if _expresses_intent(last_text) and not says_done:
                        if self.nudge_controller.nudge_intent(last_text, says_done):
                            self.state_machine.transition(LoopState.NUDGING, "intent nudge")
                            continue
                        if not hard_nudged and self.nudge_controller.nudge_hard_final():
                            hard_nudged = True
                            self.state_machine.transition(LoopState.NUDGING, "hard final nudge")
                            continue

                    # Nudge: build without evidence
                    if self.nudge_controller.nudge_evidence(is_build, says_done, evidence):
                        self.state_machine.transition(LoopState.NUDGING, "evidence nudge")
                        continue

                    # Nudge: continue build (questions during build)
                    if is_build and (asks_qa or repeated_qa) and self.nudge_controller.nudge_continue_build():
                        self.state_machine.transition(LoopState.NUDGING, "continue build nudge")
                        continue

                    # Nudge: self-critique
                    if self.nudge_controller.nudge_critique(
                        score=score,
                        tool_events_count=len(self.tool_events),
                        is_build=is_build,
                        prompt_len=len(user_prompt),
                    ):
                        result.critiqued = True
                        self.state_machine.transition(LoopState.NUDGING, "self-critique")
                        continue

                    # Reflection loop — fase Reflect wajib sebelum finalisasi
                    if self._maybe_reflect(score, is_build, evidence, says_done, asks_qa):
                        self.state_machine.transition(LoopState.REFLECTING, "reflect phase")
                        continue

                    # Build forced stop without evidence
                    if is_build and not evidence:
                        result.stopped_early = True

                report = self._run_auto_verify(before_files)
                if self._maybe_repair(report):
                    self.state_machine.transition(LoopState.REFLECTING, "verify-repair")
                    continue
                result.reflect_iterations = self.reflect_iterations
                self._copy_prediction(result)
                result.final_text = self._finalize_response(last_text, result)
                self.state_machine.transition(LoopState.COMPLETED, "early stop")
                self.hooks.finish(result)
                return result

            # 4) Execute tools
            self.nudge_controller.reset_nudges()
            hard_nudged = False

            if resp.response.fallback_tool_call:
                # MODE TEKS: hasil tool dikirim sebagai pesan user biasa —
                # kompatibel dengan model yang tidak support native tool-calling.
                self.ctx.push(ChatMessage(role="assistant", content=resp.response.message.content))
                for ev in resp.tool_events:
                    if ev["output"].startswith("ERROR"):
                        errors += 1
                    self._extract_facts(ev["name"], ev["args"], ev["output"])
                    self.ctx.push(
                        ChatMessage(role="user", content=f"[Hasil tool '{ev['name']}']\n{ev['output']}")
                    )
                    if self._maybe_pause_for_user(result, last_text):
                        return result
            else:
                # MODE NATIVE: protokol tool_calls + role:tool (OpenAI/Anthropic)
                self.ctx.push(
                    ChatMessage(role="assistant", content="", tool_calls=resp.response.message.tool_calls)
                )
                for tc, ev in zip(resp.response.message.tool_calls, resp.tool_events):
                    if ev["output"].startswith("ERROR"):
                        errors += 1
                    self._extract_facts(ev["name"], ev["args"], ev["output"])
                    self.ctx.push(
                        ChatMessage(role="tool", content=ev["output"], tool_call_id=tc["id"])
                    )
                    if self._maybe_pause_for_user(result, last_text):
                        return result

            if self._maybe_pause_for_user(result, last_text):
                self.state_machine.transition(LoopState.PAUSED, "user question")
                return result

            # 5) Error-based escalation (cheap-first) — wajib izin user
            if errors >= self.cfg.escalate_after_errors and not result.escalated:
                if not self._escalation_allowed("terlalu banyak error tool"):
                    # User menolak — lanjut model sama, reset counter agar tidak
                    # memicu ulang di setiap langkah.
                    errors = 0
                elif self.router is not None:
                    client = self._pick_client(user_prompt, force="big")
                    self.step_executor.client = client
                    result.escalated = True
                    errors = 0
                    self.state_machine.transition(LoopState.ESCALATING, "error escalation")
                else:
                    esc_result = self.escalation_policy.escalate_for_errors(step, Exception("tool errors"))
                    if esc_result.escalated:
                        client = esc_result.new_client
                        self.step_executor.client = client
                        result.escalated_quality = True
                        result.escalation_count = esc_result.escalation_count
                        result.escalated = True
                        errors = 0
                        self.state_machine.transition(LoopState.ESCALATING, "error escalation")

            # 6) Hard budget
            if self.budget.exhausted:
                self._run_auto_verify(before_files)
                result.final_text = "[budget keras tercapai — sesi dihentikan, ketik /compact untuk lanjut]"
                result.budget_exhausted = True
                self._copy_prediction(result)
                self.state_machine.transition(LoopState.STUCK, "hard budget exhausted")
                self.hooks.finish(result)
                return result

        # Max steps reached
        v, is_build, score = self._measure_output(user_prompt, last_text, before_files)
        result.files_created = v["files_created"]
        result.tests_passed = v["tests_passed"]
        result.quality_score = score
        evidence = (
            v["files_created"] > 0
            or v["tests_passed"] is True
            or self._used_mutating_tool()
        )
        if is_build and not evidence:
            result.stopped_early = True
        self._run_auto_verify(before_files)
        result.reflect_iterations = self.reflect_iterations
        self._copy_prediction(result)
        result.final_text = self._finalize_response(last_text, result)
        self.state_machine.transition(LoopState.STUCK, "max steps reached")
        self.hooks.finish(result)
        return result