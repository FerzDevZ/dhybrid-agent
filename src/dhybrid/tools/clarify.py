"""Tool clarify — agent tanya pilihan bernomor + default ke user.

Terpisah dari ask_user:
- clarify: pilihan teknis ringan (stack, pendekatan, format) — user jawab
  angka / teks bebas / "Lanjutkan" (= default). Guardrail CLARIFY_MAX per sesi.
- ask_user: keputusan berdampak besar & tak bisa ditebak (maks 2x per sesi).

Alur sama dengan ask_user: tool mengisi `state.pending`; loop mendeteksinya,
berhenti, REPL menampilkan pilihan ke user lalu meneruskan jawabannya.
Non-interaktif (`dhybrid run`) → diblokir; agent pilih default sendiri.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CLARIFY_MAX = 3
PENDING_SENTINEL = "CLARIFY_PENDING"
BLOCKED_SENTINEL = "CLARIFY_BLOCKED"


@dataclass
class ClarifyState:
    interactive: bool = True
    count: int = 0
    pending: dict | None = field(default=None)

    def ask(self, question: str, options: list, default_index: int = 1) -> str:
        if not self.interactive:
            return (
                f"{BLOCKED_SENTINEL}: mode non-interaktif — pilih opsi default "
                f"(nomor {default_index}) dan lanjutkan tanpa bertanya."
            )
        if self.count >= CLARIFY_MAX:
            return (
                f"{BLOCKED_SENTINEL}: maks {CLARIFY_MAX} clarify per sesi — "
                "pilih opsi default dan lanjutkan."
            )
        self.count += 1
        self.pending = {
            "question": question,
            "options": list(options or []),
            "default_index": default_index,
        }
        return PENDING_SENTINEL


def register(reg, state: ClarifyState) -> None:
    def _clarify(question: str, options: list | None = None, default_index: int = 1) -> str:
        return state.ask(question, options or [], default_index)

    reg.register(
        "clarify",
        "Tanya pilihan bernomor ke user (stack/teknologi/pendekatan/format). "
        "User jawab angka, teks bebas, atau 'Lanjutkan' = opsi default. "
        "Maks 3x per sesi. Untuk keputusan berdampak besar & tak bisa ditebak "
        "pakai ask_user.",
        {
            "question": {"type": "string"},
            "options": {"type": "array", "items": {"type": "string"}},
            "default_index": {"type": "integer"},
        },
        _clarify,
    )
