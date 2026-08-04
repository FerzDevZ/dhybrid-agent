"""TDD tests for tiktoken-based per-model token counting.

Written FIRST (RED); implementation follows in
src/dhybrid/efficiency/tokenizer.py.

Contract (Task 2):
  (a) tiktoken available -> count akurat (matches tiktoken.encode exactly)
  (b) unknown / claude model -> heuristic fallback (len(text) // 4)
  (c) cache works (lookup sama -> same encoding object reused)
  plus: api_errors metric incremented on fallback, and Budget.add uses
  _token_count without changing its signature.

metrics api_errors reuses the shared dhybrid.efficiency.metrics module.
"""

from __future__ import annotations

import pytest

from dhybrid.efficiency.metrics import api_errors
from dhybrid.efficiency.tokenizer import (
    _enc_cache,
    _get_encoding,
    _heuristic_count,
    _token_count,
    approx_count_tokens,
)


# ---------------------------------------------------------------------------
# (a) tiktoken available -> count akurat
# ---------------------------------------------------------------------------
def test_tiktoken_available_count_accurate():
    import tiktoken

    text = "hello world, this is a test of token counting"
    expected = len(tiktoken.encoding_for_model("gpt-3.5-turbo").encode(text))
    assert approx_count_tokens(text, "gpt-3.5-turbo") == expected


def test_gpt4_count_accurate():
    import tiktoken

    text = "The quick brown fox jumps over the lazy dog." * 3
    enc = tiktoken.encoding_for_model("gpt-4")
    expected = len(enc.encode(text))
    assert approx_count_tokens(text, "gpt-4") == expected


def test_token_count_matches_public_api():
    """_token_count (private) and approx_count_tokens (public) agree for GPT."""
    text = "consistency check between private and public helpers"
    assert _token_count(text, "gpt-3.5-turbo") == approx_count_tokens(
        text, "gpt-3.5-turbo"
    )


def test_int_passthrough():
    """int input (already a token count, e.g. usage.prompt_tokens) is passed
    through untouched so Budget.add keeps working with API usage ints."""
    assert _token_count(123, "gpt-3.5-turbo") == 123
    assert approx_count_tokens(456, "gpt-3.5-turbo") == 456


# ---------------------------------------------------------------------------
# (b) unknown / claude model -> heuristic (len(text) // 4)
# ---------------------------------------------------------------------------
def test_claude_model_uses_heuristic():
    text = "claude-3-opus-20240229 uses a different tokenizer"
    assert approx_count_tokens(text, "claude-3-opus-20240229") == len(text) // 4


def test_unknown_model_cl100k_fallback():
    """A non-claude unknown model falls back to the cl100k_base encoding (still
    tiktoken) per requirement #1, so it must NOT raise and must return a sane
    non-negative int."""
    text = "totally-bogus-model-9000 should fall back to cl100k_base via tiktoken"
    result = approx_count_tokens(text, "totally-bogus-model-9000")
    assert isinstance(result, int) and result >= 0


def test_tiktoken_unavailable_uses_heuristic(monkeypatch):
    """When the tiktoken library is missing, _token_count falls back to the
    len(text)//4 heuristic."""
    import dhybrid.efficiency.tokenizer as tok_mod

    monkeypatch.setattr(tok_mod, "_HAS_TIKTOKEN", False)
    monkeypatch.setattr(tok_mod, "tiktoken", None)
    text = "no tiktoken available at all in this test"
    assert _token_count(text, "gpt-3.5-turbo") == len(text) // 4


def test_heuristic_count_helper():
    assert _heuristic_count("abcdefgh") == 2  # 8 // 4
    assert _heuristic_count("") == 0


# ---------------------------------------------------------------------------
# api_errors metric incremented on heuristic fallback
# ---------------------------------------------------------------------------
def test_api_errors_incremented_on_claude():
    api_errors.reset()
    before = api_errors.value
    approx_count_tokens("some claude text here with words", "claude-3-sonnet-20240229")
    assert api_errors.value == before + 1


def test_api_errors_incremented_when_tiktoken_missing(monkeypatch):
    import dhybrid.efficiency.tokenizer as tok_mod

    api_errors.reset()
    before = api_errors.value
    monkeypatch.setattr(tok_mod, "_HAS_TIKTOKEN", False)
    monkeypatch.setattr(tok_mod, "tiktoken", None)
    _token_count("tiktoken is gone for this test", "gpt-3.5-turbo")
    assert api_errors.value == before + 1


# ---------------------------------------------------------------------------
# (c) cache works (lookup sama -> same encoding object reused)
# ---------------------------------------------------------------------------
def test_cache_returns_same_encoding_object():
    _enc_cache.clear()
    e1 = _get_encoding("gpt-3.5-turbo")
    e2 = _get_encoding("gpt-3.5-turbo")
    assert e1 is not None
    assert e1 is e2  # same object: lookup sama
    assert _enc_cache["gpt-3.5-turbo"] is e1  # cached under model key


def test_cache_populated_on_first_use():
    _enc_cache.clear()
    assert "gpt-4" not in _enc_cache
    _get_encoding("gpt-4")
    assert "gpt-4" in _enc_cache


def test_cache_miss_count_stable():
    """Repeated calls don't grow the cache."""
    _enc_cache.clear()
    _get_encoding("gpt-3.5-turbo")
    _get_encoding("gpt-3.5-turbo")
    _get_encoding("gpt-3.5-turbo")
    assert len(_enc_cache) == 1


def test_get_encoding_none_when_tiktoken_missing(monkeypatch):
    import dhybrid.efficiency.tokenizer as tok_mod

    _enc_cache.clear()
    monkeypatch.setattr(tok_mod, "_enc_cache", _enc_cache)
    monkeypatch.setattr(tok_mod, "_HAS_TIKTOKEN", False)
    monkeypatch.setattr(tok_mod, "tiktoken", None)
    assert _get_encoding("gpt-3.5-turbo") is None


# ---------------------------------------------------------------------------
# Integration: Budget.add uses _token_count without changing signature
# ---------------------------------------------------------------------------
def test_budget_add_uses_token_count():
    """Budget.add still accepts ints; counting stays identical for ints."""
    from dhybrid.efficiency.budget import TokenBudget

    b = TokenBudget(soft=10**9, hard=10**9)
    b.add(60, 40, tag="t1")
    assert b.used == 100  # 60 + 40 still holds for int inputs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
