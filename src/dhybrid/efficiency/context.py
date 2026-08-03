"""ContextManager — jendela konteks dengan kompaksi.

KnownFacts tracker mencegah agen bertanya hal yang sudah diketahui.
"""

from __future__ import annotations

import re

from dhybrid.llm.base import ChatMessage
from dhybrid.llm.tokens import estimate_messages

# ---- Known Facts Tracker ----
# Mencegah agen menanyakan hal yang sudah diketahati.
_FACT_PATTERNS = [
    (re.compile(r"which\s+(\S+)"), "checked_tool:{group}"),
    (re.compile(r"Stack apa"), "asked_stack"),
    (re.compile(r"mau.*pilih"), "asked_choice"),
]
_BINGUNG_RE = re.compile(
    r"(mau yang mana|pilih|bagaimana sebaiknya|Stack apa|bingung|tidak yakin)",
    re.IGNORECASE,
)


class KnownFacts:
    """Track fakta yang sudah diverifikasi & pertanyaan yang sudah diajukan.

    Mencegah agen bolong bertanya — setiap fakta/pertanyaan dicatat,
    dan sistem akan tahu "sudah tahu ini" sehingga tidak perlu tanya lagi.
    """

    def __init__(self):
        self.facts: set[str] = set()
        self.asked_questions: list[str] = []

    def add_fact(self, fact: str) -> None:
        self.facts.add(fact)

    def is_known(self, question: str) -> bool:
        q = question.lower()
        return any(q in f.lower() or f.lower() in q for f in self.facts)

    def already_asked(self, question: str) -> bool:
        return any(question.lower() in q.lower() for q in self.asked_questions)

    def mark_asked(self, question: str) -> None:
        self.asked_questions.append(question)

    def render(self) -> str:
        """Render facts & asked questions ke string untuk inject ke prompt.

        Dibatasi (8 fakta / 3 pertanyaan terakhir) supaya hemat token.
        """
        parts = []
        if self.facts:
            parts.append("Fakta yang sudah diketahui:")
            for f in sorted(self.facts)[-8:]:
                parts.append(f"  - {f}")
        if self.asked_questions:
            parts.append("Pertanyaan yang sudah diajukan (jangan tanya ulang):")
            for q in self.asked_questions[-3:]:
                parts.append(f"  - {q[:100]}")
        return "\n".join(parts) if parts else ""


class ContextManager:
    def __init__(self, keep_recent: int = 8, compact_ratio: float = 0.5):
        self.keep_recent = keep_recent
        self.compact_ratio = compact_ratio
        self.messages: list[ChatMessage] = []
        self.summary: str | None = None
        self.compactions = 0
        self.facts: KnownFacts = KnownFacts()

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
        # fakta & pertanyaan yang sudah diketahui → model TIDAK boleh tanya ulang
        facts = self.facts.render()
        if facts:
            out.append(
                ChatMessage(
                    role="system",
                    content=(
                        "[KONTEKS YANG SUDAH DIKETAHUI]\n"
                        f"{facts}\n"
                        "JANGAN tanya ulang hal yang sudah diketahui; eksplor dengan tool, bukan bertanya."
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
