"""MessageStore — urutan pesan sederhana + helper hasil tool."""

from __future__ import annotations

from dhybrid.llm.base import ChatMessage


class MessageStore:
    def __init__(self):
        self.items: list[ChatMessage] = []

    def add(self, role: str, content: str, **kw) -> ChatMessage:
        msg = ChatMessage(role=role, content=content, **kw)
        self.items.append(msg)
        return msg

    def add_tool_result(self, tool_call_id: str, content: str) -> None:
        self.items.append(
            ChatMessage(role="tool", content=content, tool_call_id=tool_call_id)
        )

    def last(self, role: str | None = None) -> ChatMessage | None:
        for m in reversed(self.items):
            if role is None or m.role == role:
                return m
        return None

    def clear(self) -> None:
        self.items.clear()
