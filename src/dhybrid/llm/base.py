"""Tipe dasar LLM: ChatMessage, Usage, ChatResponse, StreamEvent, LLMClient ABC."""

from __future__ import annotations

import base64
import json
import mimetypes
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path


def text_part(text: str) -> dict:
    """Part teks untuk pesan multimodal."""
    return {"type": "text", "text": text}


def image_part(path: str | Path) -> dict:
    """Part gambar (data URI base64) untuk pesan multimodal — format
    OpenAI-compatible; didukung byNara/OpenAI/OpenRouter/Gemini dll."""
    p = Path(path)
    mime = mimetypes.guess_type(str(p))[0] or "image/png"
    data = base64.b64encode(p.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str | list  # str teks, atau list of parts (text_part/image_part)
    tool_calls: list | None = None  # [{"id","name","arguments"(dict)}]
    tool_call_id: str | None = None

    def to_api(self) -> dict:
        """Format OpenAI-compatible. content list (multimodal) diteruskan apa adanya."""
        d: dict = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc["arguments"]),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d


@dataclass
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class ChatResponse:
    message: ChatMessage
    usage: Usage
    model: str
    cache_hit: bool = False
    fallback_tool_call: bool = False  # True = tool call dari blok ```tool (mode teks)


@dataclass
class StreamEvent:
    kind: str  # "delta" | "tool_call" | "done"
    text: str = ""
    tool_call: dict | None = None
    usage: Usage | None = None


class LLMClient(ABC):
    """Kontrak client LLM. Implementasi: OpenAICompatClient, AnthropicClient."""

    @abstractmethod
    def stream(self, messages: list[ChatMessage], **kw) -> Iterator[StreamEvent]: ...

    @abstractmethod
    def complete(self, messages: list[ChatMessage], **kw) -> ChatResponse: ...

    def model_name(self) -> str:
        cfg = getattr(self, "cfg", None)
        if cfg is not None and hasattr(cfg, "model"):
            return cfg.model
        return type(self).__name__


def _parse_arguments(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw}
