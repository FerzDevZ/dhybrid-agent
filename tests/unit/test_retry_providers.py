"""TDD test tenacity retry pada provider HTTP."""
from unittest.mock import Mock, patch

import httpx
import pytest

from dhybrid.config import ModelConfig
from dhybrid.llm.providers import AnthropicClient, OpenAICompatClient


def _mc(provider="anthropic", model="claude-3-5-sonnet-20241022"):
    return ModelConfig(
        provider=provider,
        model=model,
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.test",
    )


def test_openai_compat_retry_then_success():
    """httpx.post raise 2x → retry succeed ke call ke-3."""
    with patch("dhybrid.llm.providers.httpx.post") as mock_post:
        # 2 exception, lalu success
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok", "tool_calls": None}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "gpt-4o-mini",
        }
        mock_post.side_effect = [
            httpx.RequestError("conn error 1"),
            httpx.RequestError("conn error 2"),
            mock_resp,
        ]

        cfg = ModelConfig(provider="openai", model="gpt-4o-mini", base_url="https://api.test")
        client = OpenAICompatClient(cfg)

        from dhybrid.llm.base import ChatMessage
        resp = client.complete([ChatMessage(role="user", content="hi")])

        assert resp.message.content == "ok"
        assert mock_post.call_count == 3  # 2 retry + 1 success


def test_anthropic_retry_then_success():
    with patch("dhybrid.llm.providers.httpx.post") as mock_post:
        mock_resp = Mock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "content": [{"type": "text", "text": "anthropic ok"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "claude-3-5-sonnet-20241022",
        }
        mock_post.side_effect = [
            httpx.RequestError("conn error 1"),
            httpx.RequestError("conn error 2"),
            mock_resp,
        ]

        cfg = ModelConfig(provider="anthropic", model="claude-3-5-sonnet-20241022", base_url="https://api.anthropic.com")
        client = AnthropicClient(cfg)

        from dhybrid.llm.base import ChatMessage
        resp = client.complete([ChatMessage(role="user", content="hi")])

        assert "ok" in resp.message.content
        assert mock_post.call_count == 3


def test_retry_exhausted_raises():
    """Setelah RETRIES kali gagal → raise last error."""
    with patch("dhybrid.llm.providers.httpx.post") as mock_post:
        mock_post.side_effect = httpx.RequestError("permanent failure")

        cfg = ModelConfig(provider="openai", model="gpt-4o-mini", base_url="https://api.test")
        client = OpenAICompatClient(cfg)

        from dhybrid.llm.base import ChatMessage
        with pytest.raises(httpx.RequestError):
            client.complete([ChatMessage(role="user", content="hi")])


def test_api_errors_incremented_on_retry_failure(monkeypatch):
    """api_errors counter naik saat retry gagal permanent."""
    from dhybrid.efficiency.metrics import api_errors
    api_errors.reset()
    before = api_errors.get()

    with patch("dhybrid.llm.providers.httpx.post") as mock_post:
        mock_post.side_effect = httpx.RequestError("permanent")

        cfg = ModelConfig(provider="openai", model="gpt-4o-mini", base_url="https://api.test")
        client = OpenAICompatClient(cfg)

        from dhybrid.llm.base import ChatMessage
        try:
            client.complete([ChatMessage(role="user", content="hi")])
        except httpx.RequestError:
            pass

    # 3 attempt (RETRIES=3) → api_errors naik 3
    assert api_errors.get() == before + 3