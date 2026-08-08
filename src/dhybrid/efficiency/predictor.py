"""TokenPredictor — estimasi biaya token run & sinyal peringatan/auto-switch.

Nilai vs TokenBudget polos:
- TokenBudget hanya tahu "used sudah lewat soft/hard" — reaktif.
- TokenPredictor menekstrapolasi rata-rata token/langkah dari history nyata dan
  kompleksitas prompt → PROYEKSI total token sebelum run selesai, lalu
  memberi sinyal: warning, /compact, auto-switch ke model murah saat
  sudah terlambat.

Tidak menjalankan LLM apa pun — murni aritmetika angka, safe & offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from dhybrid.llm.tokens import estimate_tokens


class PredictionLevel(Enum):
    """Tingkat urgensi proyeksi budget."""
    OK = "ok"
    WARNING = "warning"      # → AgentLoop sarankan compact & ringkas
    CRITICAL = "critical"    # → AgentLoop auto-switch ke model murah


@dataclass
class RunPrediction:
    level: PredictionLevel
    projected_total: int
    remaining: int
    remaining_steps: int = 0


class TokenPredictor:
    """Proyeksi total token & klasifikasi urgensi dari ekstrapolasi rata-rata."""

    def __init__(
        self,
        hard_budget: int,
        warning_fraction: float = 0.75,
        critical_fraction: float = 0.9,
    ):
        self.hard_budget = hard_budget
        self.warning_fraction = warning_fraction
        self.critical_fraction = critical_fraction

    # ---------- komponen yang bisa di-override / dites terpisah ----------

    @staticmethod
    def estimate_steps(prompt: str) -> int:
        """Perkiraan jumlah langkah model dari kompleksitas prompt (0-10).

        Kompleksitas tinggi (auth, db, arsitektur) → lebih banyak langkah.
        Dibatasi [1, 20] supaya proyeksi tidak inflate di run pendek.
        """
        # Lazy import: dhybrid.agent memicu __init__ yang menarik agent_loop
        # (yang juga import predictor) → circular import. Di dalam fungsi aman.
        from dhybrid.agent.router import estimate_complexity

        rel = estimate_complexity(prompt) / 10.0
        return max(1, min(20, int(rel * 19) + 1))

    @staticmethod
    def estimate_avg_step_tokens(prompt: str, system_prompt: str, history: list[dict]) -> int:
        """Rata-rata token per langkah dari beberapa langkah TERAKHIR.

        Memakai data nyata bila sudah ada; kalau belum ada, anchor ke estimasi
        input (prompt+system) dibagi 4 + overhead jawaban.
        """
        recent = history[-4:]
        if recent:
            avg = sum(h.get("prompt", 0) + h.get("completion", 0) for h in recent) / len(recent)
            if avg > 0:
                return int(avg)
        return (estimate_tokens(prompt) + estimate_tokens(system_prompt)) // 4 + 150

    # ---------- API utama ----------

    def predict(
        self,
        prompt: str,
        system_prompt: str,
        used: int,
        steps_done: int,
        history: list[dict],
        est_steps: int | None = None,
    ) -> RunPrediction:
        """Proyeksi total token + tingkat urgensi.

        projected = token TERPAKAI + (avg/langkah * sisa langkah). Memakai avg
        nyata bila ada; kalau proyeksi melewati ambang hard → urgen.
        """
        est = min(est_steps or self.estimate_steps(prompt), 20)
        avg = self.estimate_avg_step_tokens(prompt, system_prompt, history)
        remaining_steps = max(0, est - steps_done)
        projected = used + avg * min(remaining_steps, 20)
        level = self._level(projected)
        return RunPrediction(level, int(projected), self.hard_budget - int(projected), int(remaining_steps))

    def _level(self, projected: int) -> PredictionLevel:
        if projected >= self.critical_fraction * self.hard_budget:
            return PredictionLevel.CRITICAL
        if projected >= self.warning_fraction * self.hard_budget:
            return PredictionLevel.WARNING
        return PredictionLevel.OK