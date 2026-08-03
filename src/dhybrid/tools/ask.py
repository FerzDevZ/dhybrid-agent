"""Tool ask_user — agent boleh bertanya ke user bila benar-benar ambigu.

Guardrail:
- maks ASK_MAX pertanyaan per sesi (agent tidak boleh tanya terus-menerus)
- mode non-interaktif (`dhybrid run`) → diblokir; agent harus pilih default sendiri

Alur: tool mengisi `state.pending`; loop mendeteksinya, berhenti, dan REPL
menampilkan pertanyaan ke user lalu meneruskan jawabannya ke sesi.
"""

from __future__ import annotations

from dataclasses import dataclass, field

ASK_MAX = 2
PENDING_SENTINEL = "ASK_USER_PENDING"
BLOCKED_SENTINEL = "ASK_USER_BLOCKED"


@dataclass
class AskState:
    interactive: bool = True
    count: int = 0
    pending: dict | None = field(default=None)


def register(reg, state: AskState) -> None:
    def _ask_user(prompt: str, options: list | None = None) -> str:
        if not state.interactive:
            return (
                f"{BLOCKED_SENTINEL}: mode non-interaktif — pilih default terbaik "
                "dan lanjutkan tanpa bertanya."
            )
        if state.count >= ASK_MAX:
            return (
                f"{BLOCKED_SENTINEL}: maks {ASK_MAX} tanya per sesi — "
                "putuskan dengan asumsi masuk akal dan lanjutkan."
            )
        state.count += 1
        state.pending = {"prompt": prompt, "options": list(options or [])}
        return PENDING_SENTINEL

    reg.register(
        "ask_user",
        "Tanya keputusan ke user. HANYA bila pilihan berdampak besar & tak bisa ditebak "
        "(maks 2x per sesi). Kalau bisa ditebak, pilih default dan lanjutkan.",
        {"prompt": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}},
        _ask_user,
    )
