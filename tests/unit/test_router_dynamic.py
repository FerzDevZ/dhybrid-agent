"""Unit tests untuk dynamic router (complexity-aware)."""

from __future__ import annotations

from dhybrid.agent.router import (
    HybridRouter,
    RouterConfig,
    classify_task,
    estimate_complexity,
)
from dhybrid.efficiency.cache import PromptCache
from dhybrid.llm.base import LLMClient


class FakeClient(LLMClient):
    def __init__(self, name):
        self.name = name

    def stream(self, messages, **kw):
        yield from []

    def complete(self, messages, **kw):
        from dhybrid.llm.base import ChatMessage, ChatResponse, Usage
        return ChatResponse(message=ChatMessage(role="assistant", content="ok"), usage=Usage(), model=self.name)

    def model_name(self):
        return self.name


def test_classify_mechanical_small():
    assert classify_task("jalankan pytest dan cek hasilnya") == "small"


def test_classify_reasoning_big():
    assert classify_task("jelaskan arsitektur dan desain sistemnya") == "big"


def test_classify_default_length():
    assert classify_task("pendek") == "small"
    assert classify_task("x" * 300) == "big"


def test_estimate_complexity_build_with_domains():
    c = estimate_complexity("buatkan login register dengan database dan jwt")
    assert 0 <= c <= 10
    assert c >= 2  # build + keyword domain


def test_estimate_complexity_simple_low():
    assert estimate_complexity("cara pakai grep") <= 2


def test_router_routes_small_for_simple():
    small, big = FakeClient("s"), FakeClient("b")
    router = HybridRouter(big, small)
    assert router.route("jalankan pytest dan lihat hasil") is small
    assert router.stats["small"] == 1


def test_router_routes_big_for_complex_build():
    small, big = FakeClient("s"), FakeClient("b")
    router = HybridRouter(big, small)
    prompt = "buatkan login register lengkap dengan database migration, jwt auth, docker deployment"
    assert router.route(prompt) is big
    assert router.stats["big"] == 1


def test_router_force_big():
    small, big = FakeClient("s"), FakeClient("b")
    router = HybridRouter(big, small)
    assert router.route("halo", force="big") is big


def test_router_config_threshold_controls_routing():
    small, big = FakeClient("s"), FakeClient("b")
    cfg = RouterConfig(big_threshold=0.99)  # hampir tidak pernah big
    router = HybridRouter(big, small, config=cfg)
    assert router.route("x" * 500) is small  # complexity tinggi tapi threshold tinggi


def test_router_cache_consistency(tmp_path):
    small, big = FakeClient("s"), FakeClient("b")
    cache = PromptCache(tmp_path / "cache.sqlite")
    router = HybridRouter(big, small, cache=cache)
    p = "buatkan api crud lengkap"
    r1 = router.route(p)
    r2 = router.route(p)
    assert r1 is r2  # cache konsisten
