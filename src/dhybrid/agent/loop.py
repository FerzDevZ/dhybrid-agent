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
import time
from dataclasses import dataclass, field

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.parsing import strip_tool_block
from dhybrid.agent.quality import score_output
from dhybrid.agent.streaming import ToolBlockFilter
from dhybrid.agent.text_parser import extract_tool_calls_from_text
from dhybrid.agent.verify import count_created_files, snapshot_files, verify_build
from dhybrid.efficiency.budget import TokenBudget
from dhybrid.efficiency.compress import compact_conversation
from dhybrid.efficiency.context import ContextManager
from dhybrid.efficiency.lazy import needs_change_check
from dhybrid.llm.base import ChatMessage, ChatResponse, LLMClient, Usage
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
EVIDENCE_MSG = (
    "[instruksi sistem] Kamu mengklaim selesai, TAPI tidak ada bukti perubahan nyata "
    "(0 file dibuat/diubah, tidak ada write_file/apply_patch/git_commit, tidak ada test dijalankan). "
    "Kerjakan sekarang sampai ada bukti: buat/ubah file, jalankan test, atau commit — lalu lapor hasilnya."
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
INTENT_MSG = (
    "[instruksi sistem] Kamu baru MENYATAKAN NIAT (\"saya akan...\") tapi belum mengeksekusi "
    "apa pun di pesan ini. Jangan berhenti di janji/rencana — EKSEKUSI SEKARANG: jalankan "
    "tool (terminal/write_file/apply_patch) dan kerjakan sampai tuntas, lalu laporkan hasil nyata."
)
HARD_FINAL_MSG = (
    "[instruksi sistem] PERINGATAN TERAKHIR — kamu sudah berulang kali menyatakan niat "
    "(\"saya akan...\") TANPA eksekusi nyata. Respons berikutnya WAJIB berisi tool call "
    "(terminal/write_file/apply_patch) yang benar-benar mengerjakan tugas user. Kalau "
    "respons berikutnya masih tanpa tool call, sesi dihentikan dan dilaporkan gagal."
)
# Sinyal "niat tanpa eksekusi": model bilang akan mengerjakan tapi belum menjalankan tool.
# (Hindari kata terlalu pendek seperti "lanjut"/"mari" polos — "ok, lanjut" itu jawaban sah.)
INTENT_HINTS = (
    "saya akan", "aku akan", "akan saya", "akan kucek", "akan kucoba", "nanti saya",
    "nanti akan", "saya lanjutkan", "mari kita", "mari mulai", "sekarang saya",
    "berikutnya saya", "saya mulai", "saya cek dulu", "saya periksa dulu",
    "saya akan cek", "saya akan start", "saya akan jalankan", "saya akan buat",
    "lanjut eksekusi", "lanjut kerjakan", "lanjut setup",
    "mari verifikasi", "mari cek", "mari jalankan", "mari buat", "mari mulai",
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


def _expresses_intent(text: str) -> bool:
    """Deteksi NIAT tanpa eksekusi: \"Saya akan cek dan start server:\" — model
    berjanji/merencanakan kerja tapi belum menjalankan tool apa pun di pesan itu.
    Kalimat yang berakhir titik dua (:) juga sinyal 'lanjut eksekusi'."""
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
    """Prompt lanjutan ('lanjutkan', 'ya', 'teruskan'...) — konteks membangun
    diwarisi dari riwayat sesi supaya tidak bebas klaim selesai tanpa bukti.
    Kata pendek ('ya'/'ok') hanya dianggap lanjutan bila prompt-nya pendek,
    hindari false positive: "ya" ada di dalam "saya"."""
    low = prompt.lower().strip()
    if any(v in low for v in ("lanjutkan", "lanjutin", "lanjut", "teruskan", "continue", "silahkan")):
        return True
    words = low.split()
    return len(words) <= 3 and any(
        v in low for v in ("ya", "yes", "ok", "oke", "iya", "ayo", "gas", "setuju", "next")
    )


def _is_transient_error(e: Exception) -> bool:
    """Error jaringan/rate-limit yang SELAYAKNYA di-retry, bukan langsung menyerah.

    Menghindari DONE dengan stack mentah '429 Too Many Requests' padahal cuma
    sementara — retry dulu, baru escalate ke model lain.
    """
    s = str(e).lower()
    markers = (
        "429", "500", "502", "503", "504",
        "too many requests", "rate limit",
        "temporary failure", "name resolution",  # DNS
        "connection", "connect error",
        "timed out", "timeout", "reset by peer", "gateway",
    )
    return any(m in s for m in markers)


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
    pending_question: dict | None = None  # tool ask_user: tunggu jawaban user di REPL


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
        ask_state=None,       # AskState dari tool ask_user (None = tanpa tanya-user)
        clarify_state=None,   # ClarifyState dari tool clarify (None = tanpa clarify)
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
        self.tool_events: list[dict] = []  # jejak tool (untuk verifier & skor)
        self._client_factory = client_factory
        self._esc_idx = 0  # posisi di escalation_chain (0 = model awal)
        self._n_escalations = 0  # berapa kali udah naik model akibat quality rendah

    def _pick_client(self, prompt: str, force: str | None = None) -> LLMClient:
        if self.router is not None:
            return self.router.route(prompt, force=force)
        return self.client  # type: ignore[return-value]

    def _next_valid_escalation(self) -> tuple[str, LLMClient] | None:
        """Maju ke preset escalation berikutnya yang bisa di-build.

        Lewati preset yang factory-nya gagal (provider disabled / key kosong)
        sehingga tidak pernah naik ke model tanpa kredensial (mis. 401 OpenRouter).
        Batasi oleh max_escalations. Return (preset_name, client) atau None bila habis.
        """
        if not self.cfg.escalation_chain or self._client_factory is None:
            return None
        while (
            self._n_escalations < self.cfg.max_escalations
            and self._esc_idx < len(self.cfg.escalation_chain)
        ):
            self._esc_idx += 1
            self._n_escalations += 1
            next_preset = self.cfg.escalation_chain[self._esc_idx - 1]
            client = self._client_factory(next_preset)
            if client is None:
                continue  # preset tak bisa dibangun → coba berikutnya
            return next_preset, client
        return None

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

    def _live_verify(self, step: int, last_snapshot: set[str]) -> set[str]:
        """Tiap 2 steps: cek file baru sejak snapshot terakhir → INJECT evidence ke prompt.

        Ini membuat model 'melihat' kemajuan pekerjaan secara real-time
        (bukan tunggu akhir): fakta progresnya ditambah + pesan ringkas disodorkan.
        Mengembalikan snapshot terakhir supaya jumlah file baru dihitung inkremental.
        """
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
        """Tool ask_user/clarify dipanggil → hentikan loop, serahkan ke REPL.

        Return True bila loop harus berhenti (jawaban user akan diteruskan oleh REPL
        sebagai pesan user baru, lalu run_agent dipanggil ulang).
        """
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
        """Ukur hasil build: bukti file, status test, skor kualitas.

        Dipakai di SEMUA jalur berhenti (early-stop ATAU max_steps habis) supaya
        baris DONE tidak membohongi: kualitas 100/100 & 0 file tidak pernah
        muncul bersamaan (dulu jalur max_steps tidak menghitung sama sekali →
        quality_score default 100 padahal tidak ada file dibuat).
        """
        v = verify_build(self.cwd, before_files, snapshot_files(self.cwd), self.tool_events)
        is_build = _is_build_request(user_prompt)
        # 'lanjutkan'/'ya' dst → warisi konteks membangun dari riwayat sesi,
        # supaya klaim selesai tanpa bukti tetap ditolak.
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

    def _finalize_response(self, last_text: str, result: LoopResult) -> str:
        """Bersihkan markup tool & pastikan jawaban final TIDAK kosong.

        Model free sering mengakhiri dengan blok <tool_call>/<invoke>/tag semata
        tanpa kalimat penutup → user hanya melihat 'DONE' kosong. Bila teks final
        kosong atau hanya berisi markup, susun ringkasan dari jejak tool
        (file dibuat, perintah dijalankan, status test) + tawaran lanjutan, supaya
        dhybrid selalu merespons dengan bermanfaat & 'agentic'.
        """
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
                # mode teks: simpan PROSA (tanpa markup tool), jangan dibuang —
                # penjelasan model tetap masuk riwayat supaya konteks konsisten.
                text = strip_tool_block(text)
                fallback = True
        return ChatResponse(
            message=ChatMessage(role="assistant", content=text, tool_calls=tool_calls or None),
            usage=usage or Usage(),
            model=client.model_name(),
            fallback_tool_call=fallback,
        )

    def run(self, user_prompt: str, system_prompt: str, push_prompt: bool = True) -> LoopResult:
        if push_prompt:
            self.ctx.push(ChatMessage(role="user", content=user_prompt))
        result = LoopResult()
        client = self._pick_client(user_prompt)
        errors = 0
        last_text = ""
        nudges = 0  # sudah disodok untuk mengerjakan (max per run)
        hard_nudged = False  # PERINGATAN TERAKHIR sudah diberikan?
        critiqued = False
        transient_retries = 0  # retry karena rate-limit/timeout sementara
        # Tanpa escalation chain tidak ada model kuat sebagai penyelamat → budget
        # nudge diperbesar (satu-satunya jalan: paksa model yang sama bekerja).
        intent_budget = self.cfg.max_nudges * (2 if not self.cfg.escalation_chain else 1)
        before_files = snapshot_files(self.cwd)
        last_snapshot = before_files
        self.tool_events = []
        # hitungan tool per-RUN: auto-skill & verifier hanya melihat run ini,
        # bukan akumulasi sesi (cegah kontaminasi antar-prompt di REPL)
        self.tools.reset_counts()

        for step in range(self.cfg.max_steps):
            # 1) kompaksi saat budget lunak tercapai
            if self.budget.should_compact and not result.compacted:
                result.compacted = self._compact(client)

            # 2) panggil model
            try:
                resp = self._step_once(client, self.ctx.render(system_prompt))
            except Exception as e:  # noqa: BLE001 — API error
                # 2a) transient (429/timeout/DNS) → retry model yang sama dengan backoff,
                #     JANGAN langsung menyerah/stop dengan stack mentah.
                if _is_transient_error(e) and transient_retries < 2 and not self.budget.exhausted:
                    transient_retries += 1
                    self.ctx.push(ChatMessage(role="user", content=(
                        f"[sistem] Gagal sementara ({type(e).__name__}) — coba ulang "
                        f"({transient_retries}/2)."
                    )))
                    time.sleep(min(2 ** transient_retries, 5))
                    continue
                # 2b) RETRY: lewati chain escalation ke model valid berikutnya.
                # (jangan langsung stop — agen berjuang sampai semua model gagal)
                nxt = self._next_valid_escalation()
                if nxt:
                    next_preset, client = nxt
                    result.escalated_quality = True
                    result.escalation_count = self._n_escalations
                    self.ctx.push(ChatMessage(
                        role="user",
                        content=f"[sistem] Gagal ke model sebelumnya ({type(e).__name__}). "
                                f"Coba model kuat berikutnya: {next_preset}. Silakan lanjutkan."
                    ))
                    continue
                # 2c) semua jalan buntu → berhenti dengan pesan ramah
                if _is_transient_error(e):
                    result.final_text = (
                        "⚠️ Penyedia model sedang sibuk/menolak (rate limit atau timeout). "
                        "Tunggu sebentar lalu ulangi, atau ganti model lain via /settings "
                        "(mis. opencode-zen-* yang gratis)."
                    )
                else:
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
                last_snapshot = self._live_verify(step, last_snapshot)

            # 3) early-stop: jawaban tanpa tool-call — TAPI hanya bila benar-benar final.
            # Task membangun TIDAK boleh berhenti: (a) sambil bertanya/meminta user pilih,
            # atau (b) tanpa menghasilkan perubahan file apa pun. Kalau itu terjadi → escalate/nudge.
            if not resp.message.tool_calls:
                # measure kualitas + bukti nyata (file/test) untuk keputusan
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
                    # jangan tanya berulang soal yang sudah diajukan
                    if asks_qa or repeated_qa:
                        self.ctx.facts.mark_asked(last_text.strip())

                    # 3d-FIRST) eskalasi kualitas: skor rendah, ATAU build masih bertanya /
                    # tanya ulang → langsung naik model kuat (bukan cuma nudge lagi
                    # yang membuang token atas model lemah).
                    if (
                        self.cfg.escalation_chain
                        and self._client_factory is not None
                        and self._n_escalations < self.cfg.max_escalations
                        and (score < self.cfg.quality_threshold or (is_build and (asks_qa or repeated_qa)))
                    ):
                        nxt = self._next_valid_escalation()
                        if nxt:
                            client = nxt[1]
                            result.escalated_quality = True
                            result.escalation_count = self._n_escalations
                            reason = (
                                f"Skor kualitas rendah ({score}/100)."
                                if score < self.cfg.quality_threshold
                                else "Masih bertanya di tengah tugas membangun."
                            )
                            self.ctx.push(ChatMessage(role="user", content=(
                                f"[sistem escalation] {reason} Beralih ke model lebih kuat: {nxt[0]}. "
                                "Selesaikan penuh tanpa bertanya/janji — lakukan eksekusi nyata."
                            )))
                            continue

                    # 3a) model diam → minta jawaban
                    if is_empty and nudges < intent_budget:
                        nudges += 1
                        self.ctx.push(ChatMessage(role="user", content=SILENT_MSG))
                        continue

                    # 3a2) NIAT tanpa eksekusi: "Saya akan cek dan start server:" —
                    # model berjanji/merencanakan tapi belum menjalankan tool di
                    # pesan ini. Jangan dianggap jawaban final (dulu langsung DONE
                    # "0 file") → suruh EKSEKUSI sekarang. Budget lebih besar dari
                    # max_nudges bila tidak ada escalation chain (tidak ada model
                    # kuat untuk menyelamatkan → paksa model yang sama bekerja).
                    if _expresses_intent(last_text) and not says_done:
                        if nudges < intent_budget:
                            nudges += 1
                            self.ctx.push(ChatMessage(role="user", content=INTENT_MSG))
                            continue
                        if not hard_nudged:
                            hard_nudged = True
                            self.ctx.push(ChatMessage(role="user", content=HARD_FINAL_MSG))
                            continue

                    # 3b) nudge build: diminta buat tapi belum ada bukti perubahan → jangan selesai.
                    # Klaim "selesai/done/berhasil" TANPA bukti tetap ditolak (says_done tidak bypass).
                    if (
                        is_build
                        and not evidence
                        and not result.stopped_early
                        and nudges < self.cfg.max_nudges
                    ):
                        nudges += 1
                        self.ctx.push(
                            ChatMessage(role="user", content=EVIDENCE_MSG if says_done else EXEC_MSG)
                        )
                        continue

                    # 3b2) HARD RULE: build diakhiri pertanyaan / tanya ulang dan escalation sudah habis
                    # → tetap jangan disangkakan "selesai". Sodor pilih-default lalu lanjut.
                    if is_build and (asks_qa or repeated_qa) and nudges < self.cfg.max_nudges * 2:
                        nudges += 1
                        self.ctx.push(ChatMessage(role="user", content=(
                            "[instruksi sistem] Kamu masih mengajukan pertanyaan/menawarkan pilihan "
                            "padahal ini tugas MEMBANGUN. PILIH default yang masuk akal dan LANJUTKAN "
                            "eksekusi sampai tuntas. Jangan berhenti untuk memilih."
                        )))
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

                    # tandai jujur: build dipaksa berhenti padahal belum ada bukti file berubah
                    if is_build and not evidence:
                        result.stopped_early = True  # biar baris DONE tidak membohongi "beres"

                result.final_text = self._finalize_response(last_text, result)
                self.hooks.finish(result)
                return result

            # 4) eksekusi tool
            nudges = 0  # aktivitas tool = progres nyata → budget nudge segar
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
                    # ask_user → pause LANGSUNG (tanpa model call tambahan)
                    if self._maybe_pause_for_user(result, last_text):
                        return result
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
                    # ask_user → pause LANGSUNG (tanpa model call tambahan)
                    if self._maybe_pause_for_user(result, last_text):
                        return result

            # 4b) ask_user dipanggil → hentikan loop, REPL akan tanya user & lanjut
            if self._maybe_pause_for_user(result, last_text):
                return result

            # 5) eskalasi cheap-first: model kecil gagal → model besar
            if errors >= self.cfg.escalate_after_errors and not result.escalated:
                if self.router is not None:
                    client = self._pick_client(user_prompt, force="big")
                else:
                    # tanpa router: coba preset berikutnya di escalation_chain
                    # (failover provider saat error beruntun, bukan cuma kualitas)
                    nxt = self._next_valid_escalation()
                    if nxt is not None:
                        client = nxt[1]
                        result.escalated_quality = True
                        result.escalation_count = self._n_escalations
                result.escalated = True
                errors = 0

            # 6) budget keras
            if self.budget.exhausted:
                result.final_text = "[budget keras tercapai — sesi dihentikan, ketik /compact untuk lanjut]"
                result.budget_exhausted = True
                self.hooks.finish(result)
                return result

        # max_steps habis — ukur JUJUR: kualitas & bukti file harus dihitung,
        # bukan default 100/100 & 0 file (bug: baris DONE membohongi).
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
            result.stopped_early = True  # build dipaksa berhenti tanpa bukti → jujur
        result.final_text = self._finalize_response(last_text, result)
        self.hooks.finish(result)
        return result
