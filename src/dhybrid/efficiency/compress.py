"""Compactor — ringkas percakapan lama via model murah."""

from __future__ import annotations

from dhybrid.llm.base import ChatMessage, LLMClient

COMPACT_PROMPT = (
    "Ringkas percakapan agent-coding berikut menjadi catatan padat (max 200 token) "
    "berisi: (1) tujuan user, (2) file yang disentuh, (3) keputusan/status, "
    "(4) hal yang BELUM selesai. Hanya fakta, tanpa basa-basi. "
    "Bahasa: ikuti bahasa user."
)


def compact_conversation(client: LLMClient, messages: list[ChatMessage]) -> str:
    resp = client.complete(
        [ChatMessage(role="system", content=COMPACT_PROMPT)] + messages,
        max_tokens=250,
        temperature=0.0,
    )
    return resp.message.content.strip()
