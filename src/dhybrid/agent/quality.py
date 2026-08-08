"""QualityScorer — interface pluggable untuk penilaian kualitas output.

Dua implementasi:
- HeuristicScorer (default, tanpa dependency) — berbasis keyword + bukti eksekusi.
- MLScorer — siap pakai bila model onnx tersedia (opsional; tidak dimuat default).

Alur:
    scorer = build_quality_scorer()   # otomatis pilih ML kalau ada, else heuristic
    score = scorer.score(text, is_build=..., tools_used=..., files_created=...)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class QualityInput:
    """Input untuk penilaian kualitas — semua sinyal terukur (tanpa LLM)."""
    text: str = ""
    is_build: bool = False
    tools_used: int = 0
    files_created: int = 0
    tests_passed: bool | None = None
    tool_errors: int = 0
    asks_question: bool = False


class QualityScorer(Protocol):
    """Kontrak scorer: input sinyal terukur → skor 0-100."""

    def score(self, inp: QualityInput) -> int: ...


# ============ HeuristicScorer ============


# Model menolak / membatalkan — sangat buruk untuk task membangun
REFUSAL_HINTS = (
    "tidak bisa", "tidak dapat", "tidak punya akses", "cannot", "can't",
    "belum bisa", "tidak tersedia", "tidak memiliki akses", "tidak sanggup",
    "saya tidak bisa", "tidak akan bisa", "maaf", "maafkan",
    "hanya bisa", "terbatas pada", "tidak dapat membantu",
)

# Model bingung / minta klarifikasi padahal sudah jelas
CONFUSED_HINTS = (
    "mau yang mana", "pilih", "bagaimana sebaiknya", "bisa jelaskan",
    "untuk memastikan", "agar saya yakin", "jika memungkinkan",
    "saya tidak yakin", "butuh klarifikasi", "perlu informasi",
    "silakan beri tahu saya", "bisakah Anda", "apakah kamu",
    "boleh tanya", "mungkin kita", "kita bisa", "saya usulkan",
)

# Model berjanji tanpa eksekusi (over-promise, under-deliver)
PROMISE_HINTS = (
    "akan saya buat", "saya akan membuatkan", "nanti akan", "akan kuselesaikan",
    "saya akan coba", "mungkin bisa", "semoga bisa",
)


class HeuristicScorer:
    """Skor berbasis bukti eksekusi + keyword (tanpa dependency, tanpa biaya).

    Prinsip: bukti EKSEKUSI NYATA (tools_used, files_created) lebih penting
    daripada pola teks. Bahasa Indonesia alami ("apakah kamu", "saya akan buat")
    adalah sopan santun, bukan kebingungan — jangan dihukum bila ada kerja nyata.
    """

    def score(self, inp: QualityInput) -> int:
        t = (inp.text or "").strip()
        low = t.lower()

        if not t and inp.tools_used == 0:
            return 0  # diam total + tidak ada kerja

        score = 50

        # Penalti teks: hanya berlaku jika TIDAK ada bukti eksekusi
        if inp.tools_used == 0:
            if any(h in low for h in REFUSAL_HINTS):
                score -= 40
            if any(h in low for h in CONFUSED_HINTS):
                score -= 25
            if any(h in low for h in PROMISE_HINTS):
                score -= 15

        # Penalti build (hanya bila tidak ada eksplor/eksekusi)
        if inp.is_build and inp.tools_used == 0 and inp.files_created == 0:
            score -= 35
        if inp.is_build and inp.files_created == 0 and inp.tools_used > 0:
            score -= 10  # kerja tapi belum ada file nyata

        # Bonus eksekusi nyata (dominan)
        score += min(inp.tools_used, 10)
        if inp.files_created > 0:
            score += min(inp.files_created * 10, 30)
            score = max(score, 60)  # task dengan file nyata ≥ "cukup"
        if inp.tests_passed is True:
            score += 20
        elif inp.tests_passed is False:
            score -= 15
        if len(t) > 300:
            score += 10
        elif len(t) < 60 and inp.is_build and inp.tools_used == 0:
            score -= 15  # pendek + tidak kerja → buruk

        return max(0, min(100, score))


# ============ MLScorer (opsional) ============

try:  # pragma: no cover — dependensi opsional
    import onnxruntime as _ort  # noqa: F401

    _HAS_ONNX = True
except ImportError:
    _HAS_ONNX = False


class MLScorer:
    """Skor berbasis model ONNX bila tersedia; fallback ke heuristic.

    Model opsional: `~/.dhybrid/models/quality.onnx` + `labels.json`.
    Input: teks tokenized (char n-gram sederhana) + fitur numerik.
    Ini adalah kerangka (skeleton) — model nyata bisa ditambahkan tanpa
    mengubah interface; tanpa model file, memakai heuristic internal.
    """

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self._session = None
        self._fallback = HeuristicScorer()
        if _HAS_ONNX and model_path:
            try:
                import onnxruntime as ort

                self._session = ort.InferenceSession(model_path)
            except Exception:  # noqa: BLE001 — gagal load ML → fallback heuristic
                self._session = None

    def score(self, inp: QualityInput) -> int:
        if self._session is None:
            # ML model belum tersedia → heuristic tetap andal
            return self._fallback.score(inp)
        # placeholder: inference nyata ditaruh di sini saat model dilatih
        return self._fallback.score(inp)


# ============ Factory ============


def build_quality_scorer(
    use_ml: bool = True,
    model_path: str | None = None,
) -> QualityScorer:
    """Pilih scorer: ML kalau enabled & model ada, else heuristic."""
    if use_ml:
        scorer = MLScorer(model_path=model_path)
        if getattr(scorer, "_session", None) is not None:
            return scorer
    return HeuristicScorer()


# ============ Back-compat: API lama ============


def score_output(
    text: str,
    *,
    is_build: bool = False,
    tools_used: int = 0,
    files_created: int = 0,
    tests_passed: bool | None = None,
) -> int:
    """Back-compat: delegasi ke HeuristicScorer (tanpa dependency)."""
    return HeuristicScorer().score(
        QualityInput(
            text=text,
            is_build=is_build,
            tools_used=tools_used,
            files_created=files_created,
            tests_passed=tests_passed,
        )
    )
