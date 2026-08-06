"""Tool subagent — delegasi tugas ke agent terisolasi (anti-runaway limits)."""

from __future__ import annotations

import threading
from collections.abc import Callable

from dhybrid.subagents.delegate import delegate


def register(reg, max_chars: int = 8000, client_factory: Callable | None = None) -> None:
    """client_factory() -> LLMClient baru utk subagent (dibuat per panggilan)."""
    state = {"active": 0, "max_active": 3, "max_result_chars": max_chars}
    _lock = threading.Lock()

    def subagent(goal: str) -> str:
        if client_factory is None:
            return "ERROR: tool subagent tidak aktif (factory belum di-set)"
        
        # Atomic check-and-increment
        with _lock:
            if state["active"] >= state["max_active"]:
                return "ERROR: batas subagent aktif tercapai (3) — selesaikan dulu atau gabungkan tugas"
            state["active"] += 1
        
        try:
            client = client_factory()
            result = delegate(goal, client, reg, _SUBAGENT_SYSTEM)
            text = result.text[: state["max_result_chars"]]
            if len(result.text) > state["max_result_chars"]:
                text += "\n[hasil subagent dipotong]"
            return f"[subagent selesai dalam {result.steps} langkah]\n{text}"
        finally:
            with _lock:
                state["active"] -= 1

    reg.register(
        "subagent",
        "Delegasikan subtugas besar ke agent terisolasi (konteks terpisah — hemat token).",
        {"goal": {"type": "string"}},
        subagent,
    )


_SUBAGENT_SYSTEM = (
    "Kamu adalah sub-agent coding yang fokus pada SATU tugas. "
    "Kerjakan dengan edit minimal (lazy senior dev). "
    "Selesaikan lalu laporkan ringkas: apa yang diubah, file apa, status test."
)
