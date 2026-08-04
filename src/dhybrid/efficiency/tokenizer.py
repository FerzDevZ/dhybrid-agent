"""Token counting akurat per model via tiktoken + fallback heuristic.

Kontrak:
- tiktoken tersedia (gpt-*, gemini-*): encoding_for_model → akurat.
- model tidak dikenal non-Claude (mis. "totally-bogus-model-9000"):
  fallback ke cl100k_base via tiktoken (tiktoken tetap dipakai, tidak crashed).
- Claude ("claude-*"): tiktoken gagal → heuristic len(text)//4 + api_errors++.
- tiktoken tidak terpasang sama sekali → heuristic + api_errors++.
- integer input (usage.prompt_tokens) passed through unchanged.
- cache per model di _enc_cache (lookup sama → object reuse).
"""
from __future__ import annotations

from dhybrid.efficiency.metrics import api_errors

try:
    import tiktoken  # type: ignore

    _HAS_TIKTOKEN = True
except ImportError:  # pragma: no cover
    tiktoken = None  # type: ignore
    _HAS_TIKTOKEN = False

# cache per (model -> encoding object)
_enc_cache: dict[str, object] = {}

# Claude models selalu pakai heuristic (tiktoken tidak punya tokenizernya)
_CLAUDE_PREFIX = "claude"


def _heuristic_count(text: str) -> int:
    return len(text) // 4 if text else 0


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _get_encoding(model: str):
    """Return cached tiktoken.Encoding untuk model, atau None bila tak tersedia."""
    if model in _enc_cache:
        return _enc_cache[model]
    if not _HAS_TIKTOKEN or tiktoken is None:
        return None
    enc = None
    # Claude tidak didukung tiktoken → None (heuristic)
    if model.lower().startswith(_CLAUDE_PREFIX):
        enc = None
    else:
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # model tak dikenal non-claude → fallback cl100k_base
            try:
                enc = tiktoken.get_encoding("cl100k_base")
            except Exception:  # noqa: BLE001 — tiktoken error (mis. model tak dikenal)
                enc = None
    if enc is None and not model.lower().startswith(_CLAUDE_PREFIX) and _HAS_TIKTOKEN:
        # sudah coba cl100k_base di atas; hanya cache bila berhasil
        pass
    _enc_cache[model] = enc  # type: ignore[assignment]
    return enc


def _token_count(text_or_int, model: str = "gpt-3.5-turbo") -> int:
    """Hitung token: akurat via tiktoken (atau cl100k fallback), heuristic bila gagal total.

    Integer input (usage.prompt_tokens) passed through unchanged.
    """
    # int passthrough (Budget.add tetap terima int)
    if _is_int(text_or_int):
        return int(text_or_int)
    if not isinstance(text_or_int, str):
        text_or_int = str(text_or_int)
    text = text_or_int
    if not text:
        return 0
    # Claude → heuristic + api_errors
    if model.lower().startswith(_CLAUDE_PREFIX):
        api_errors.inc()
        return max(1, _heuristic_count(text))
    # tiktoken tidak tersedia
    if not _HAS_TIKTOKEN:
        api_errors.inc()
        return max(1, _heuristic_count(text))
    enc = _get_encoding(model)
    if enc is not None:
        try:
            return max(1, len(enc.encode(text)) if hasattr(enc, "encode") else _heuristic_count(text))  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 — tiktoken encode error (mis. unicode tak dikenal)
            api_errors.inc()
            return max(1, _heuristic_count(text))
    # _get_encoding None tapi tiktoken ada + non-claude → sudah dicoba cl100k_base di atas
    api_errors.inc()
    return max(1, _heuristic_count(text))


def approx_count_tokens(text_or_int, model: str = "gpt-3.5-turbo") -> int:
    """API publik: hitung token akurat bila mungkin, heuristic kalau perlu."""
    return _token_count(text_or_int, model)
