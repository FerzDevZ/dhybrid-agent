"""ContextManager — jendela konteks dengan kompaksi.

Pesan TUA (di luar keep_recent) diringkas menjadi 1 pesan summary;
pesan terakhir keep_recent dipertahankan verbatim.
"""

from __future__ import annotations

from dhybrid.llm.base import ChatMessage
from dhybrid.llm.tokens import estimate_messages


class ContextManager:
    def __init__(self, keep_recent: int = 8, compact_ratio: float = 0.5):
        self.keep_recent = keep_recent
        self.compact_ratio = compact_ratio
        self.messages: list[ChatMessage] = []
        self.summary: str | None = None
        self.compactions = 0

    def push(self, msg: ChatMessage) -> None:
        self.messages.append(msg)

    def estimated_tokens(self) -> int:
        head: list[ChatMessage] = []
        if self.summary:
            head.append(ChatMessage(role="system", content=f"[ringkasan sesi] {self.summary}"))
        return estimate_messages(head + self.messages)

    def render(self, system_prompt: str = "") -> list[ChatMessage]:
        """Pesan siap kirim ke API: system (opsional) + summary + percakapan."""
        out: list[ChatMessage] = []
        if system_prompt:
            out.append(ChatMessage(role="system", content=system_prompt))
        if self.summary:
            out.append(
                ChatMessage(
                    role="system",
                    content=(
                        "Berikut ringkasan percakapan SEBELUM ini. Pakai hanya bila relevan, "
                        f"jangan ulangi: {self.summary}"
                    ),
                )
            )
        return out + self.messages

    def candidates_for_compaction(self) -> list[ChatMessage]:
        if len(self.messages) > self.keep_recent:
            return self.messages[: -self.keep_recent]
        return []

    def apply_compaction(self, new_summary: str) -> None:
        if self.candidates_for_compaction():
            self.summary = new_summary
            self.messages = self.messages[-self.keep_recent :]
            self.compactions += 1
