"""Nudge controller — manages multi-level nudge strategy for agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from dhybrid.agent.hooks import Hooks
from dhybrid.agent.loop.state_machine import StateMachine
from dhybrid.llm.base import ChatMessage

# Nudge messages (moved from loop.py for reusability)
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
EVIDENCE_MSG = (
    "[instruksi sistem] Kamu mengklaim selesai, TAPI tidak ada bukti perubahan nyata "
    "(0 file dibuat/diubah, tidak ada write_file/apply_patch/git_commit, tidak ada test dijalankan). "
    "Kerjakan sekarang sampai ada bukti: buat/ubah file, jalankan test, atau commit — lalu lapor hasilnya."
)
CONTINUE_BUILD_MSG = (
    "[instruksi sistem] Kamu masih mengajukan pertanyaan/menawarkan pilihan "
    "padahal ini tugas MEMBANGUN. PILIH default yang masuk akal dan LANJUTKAN "
    "eksekusi sampai tuntas. Jangan berhenti untuk memilih."
)
CRITIQUE_MSG = (
    "[instruksi sistem] Review hasilmu sendiri sebelum selesai: apakah sudah lengkap, benar, "
    "dan sesuai permintaan user? Perbaiki kekurangan yang kamu temukan, lalu berikan jawaban "
    "akhir yang lebih baik."
)


@dataclass
class NudgeConfig:
    """Configuration for nudge behavior."""
    max_nudges: int = 3
    intent_budget_multiplier: int = 2  # extra budget when no escalation chain
    hard_nudge_given: bool = False
    critiqued: bool = False


class NudgeController:
    """Controls nudge strategy based on model behavior and task type."""

    def __init__(
        self,
        config: NudgeConfig,
        state_machine: StateMachine,
        hooks: Hooks,
        has_escalation_chain: bool = False,
        push_message: Callable[[ChatMessage], None] | None = None,
    ):
        self.config = config
        self.state_machine = state_machine
        self.hooks = hooks
        self.has_escalation_chain = has_escalation_chain
        # Callback untuk memasukkan pesan nudge ke konteks percakapan.
        # (Nudge harus TERLIHAT oleh model pada turn berikutnya — tanpa ini
        # model tidak pernah menerima instruksi nudge, loop jadi tidak efektif.)
        self.push_message = push_message or (lambda m: None)

        # Counters
        self.nudges_given = 0
        self.intent_budget = config.max_nudges * (
            config.intent_budget_multiplier if not has_escalation_chain else 1
        )

    def _effective_intent_budget(self) -> int:
        return self.intent_budget

    def can_nudge(self, nudge_type: str = "general") -> bool:
        """Check if we can give another nudge."""
        if nudge_type == "intent":
            return self.nudges_given < self._effective_intent_budget()
        return self.nudges_given < self.config.max_nudges

    def nudge_silent(self) -> bool:
        """Nudge when model is silent (no content)."""
        if not self.can_nudge():
            return False
        self.nudges_given += 1
        self._push_nudge(SILENT_MSG, "silent")
        return True

    def nudge_intent(self, last_text: str, says_done: bool = False) -> bool:
        """Nudge when model expresses intent without execution."""
        if not self.can_nudge("intent"):
            return False
        if says_done:
            return False  # if model says done, let quality check handle it
        self.nudges_given += 1
        self._push_nudge(INTENT_MSG, "intent")
        return True

    def nudge_hard_final(self) -> bool:
        """Give the final hard nudge (only once)."""
        if self.config.hard_nudge_given:
            return False
        self.config.hard_nudge_given = True
        self._push_nudge(HARD_FINAL_MSG, "hard_final")
        return True

    def nudge_evidence(self, is_build: bool, says_done: bool, evidence: bool) -> bool:
        """Nudge when build task has no evidence of work."""
        if not self.can_nudge():
            return False
        if not is_build or evidence:
            return False
        self.nudges_given += 1
        msg = EVIDENCE_MSG if says_done else EXEC_MSG
        self._push_nudge(msg, "evidence")
        return True

    def nudge_continue_build(self) -> bool:
        """Nudge when model keeps asking questions during build task."""
        # Extra budget for question nudges during build
        if self.nudges_given >= self.config.max_nudges * 2:
            return False
        self.nudges_given += 1
        self._push_nudge(CONTINUE_BUILD_MSG, "continue_build")
        return True

    def nudge_critique(self, score: int, tool_events_count: int, is_build: bool, prompt_len: int) -> bool:
        """Nudge for self-critique (only once, for complex tasks)."""
        if self.config.critiqued:
            return False
        if not is_build and prompt_len < 150:
            return False
        if tool_events_count == 0:
            return False
        if score >= 90:
            return False
        self.config.critiqued = True
        self._push_nudge(CRITIQUE_MSG, "critique")
        return True

    def _push_nudge(self, message: str, nudge_type: str) -> None:
        """Push nudge message to conversation context and emit hook."""
        self.push_message(ChatMessage(role="user", content=message))
        self.hooks.nudge(nudge_type, message)

    def reset_nudges(self) -> None:
        """Reset nudge budget (called when tool activity happens)."""
        self.nudges_given = 0

    def get_status(self) -> dict:
        """Return current nudge status for debugging."""
        return {
            "nudges_given": self.nudges_given,
            "max_nudges": self.config.max_nudges,
            "intent_budget": self._effective_intent_budget(),
            "hard_nudge_given": self.config.hard_nudge_given,
            "critiqued": self.config.critiqued,
        }