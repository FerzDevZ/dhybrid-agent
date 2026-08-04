"""TDD tests for unified LLM routing via make_client + litellm."""
import pytest

from dhybrid.config import ModelConfig
from dhybrid.llm.litellm_client import LiteLLMClient
from dhybrid.llm.providers import (
    AnthropicClient,
    OpenAICompatClient,
    make_client,
)


def _mc(provider, model, api_key_env="OPENAI_API_KEY", base_url="https://api.test"):
    return ModelConfig(provider=provider, model=model, api_key_env=api_key_env, base_url=base_url)


def test_make_client_openai_returns_compat():
    c = make_client(_mc("openai", "gpt-4o"))
    assert isinstance(c, OpenAICompatClient)


def test_make_client_anthropic_returns_anthropic():
    c = make_client(_mc("anthropic", "claude-3-5-sonnet-20241022"))
    assert isinstance(c, AnthropicClient)


def test_make_client_litellm_preset():
    c = make_client(_mc("litellm", "openai/gpt-4o"))
    assert isinstance(c, LiteLLMClient)


def test_make_client_litellm_gemini_prefix():
    c = make_client(_mc("litellm", "gemini/gemini-2.0-flash"))
    assert isinstance(c, LiteLLMClient)


def test_make_client_unknown_provider_raises():
    with pytest.raises((KeyError, ValueError, NotImplementedError)):
        make_client(_mc("totally-bogus", "x"))


def test_litellm_client_has_complete_and_stream():
    c = make_client(_mc("litellm", "openai/gpt-4o-mini"))
    assert hasattr(c, "complete")
    assert hasattr(c, "stream")
