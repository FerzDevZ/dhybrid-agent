"""Integration test 0.9.5: metrics + token counting + checkpoint + routing."""
from pathlib import Path

from dhybrid.config import Config, ModelConfig
from dhybrid.efficiency.metrics import api_calls, tokens_prompt
from dhybrid.efficiency.prometheus_exporter import export_metrics
from dhybrid.efficiency.tokenizer import _token_count
from dhybrid.llm.litellm_client import LiteLLMClient
from dhybrid.llm.providers import make_client
from dhybrid.session.context import SessionContext
from dhybrid.session.store import SessionStore


def test_metrics_counters_increment(tmp_path):
    tokens_prompt.reset()
    api_calls.reset()
    tokens_prompt.inc(100)
    api_calls.inc(3)
    assert tokens_prompt.value == 100
    assert api_calls.value == 3
    # export prometheus format valid
    out = export_metrics()
    assert "tokens_prompt 100" in out
    assert "# TYPE api_calls counter" in out


def test_tokenizer_akurat(tmp_path):
    # gpt-4o via tiktoken
    tok = _token_count("hello world", "gpt-4o")
    assert tok == 2
    # claude fallback heuristic
    assert _token_count("abcdefgh", "claude-3-5-sonnet-20241022") == 2  # 8//4


def test_checkpoint_roundtrip(tmp_path):
    cfg = Config(workspace=Path(tmp_path / "ws"), model=ModelConfig(provider="openai", model="gpt-4o-mini"))
    store = SessionStore(db_path=tmp_path / "s.sqlite")
    ctx = SessionContext(cfg=cfg, store=store, cwd=str(tmp_path))
    ctx.run_count = 9
    ctx.fallback_uses = 4
    ctx.save_checkpoint()

    ctx2 = SessionContext(cfg=cfg, store=store, cwd=str(tmp_path), sid=ctx.sid)
    assert ctx2.run_count == 9
    assert ctx2.fallback_uses == 4


def test_make_client_litellm(tmp_path):
    mc = ModelConfig(provider="litellm", model="openai/gpt-4o-mini", api_key_env="OPENAI_API_KEY", base_url="https://api.openai.com/v1")
    c = make_client(mc)
    assert isinstance(c, LiteLLMClient)
    # punya interface LLMClient yang sama
    assert hasattr(c, "complete") and hasattr(c, "stream")


def test_tiktoken_importable():
    import tiktoken
    assert tiktoken is not None
