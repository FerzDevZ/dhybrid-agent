from dhybrid.efficiency.cache import PromptCache, SemanticCache
from dhybrid.llm.base import ChatMessage


def test_cache_roundtrip_and_ttl(tmp_path):
    c = PromptCache(db_path=tmp_path / "c.sqlite", ttl=3600)
    msgs = [ChatMessage(role="user", content="klasifikasi: fix bug kecil")]
    assert c.get("m", msgs) is None
    c.set("m", msgs, "small")
    assert c.get("m", msgs) == "small"


def test_cache_misses_on_different_prompt(tmp_path):
    c = PromptCache(db_path=tmp_path / "c.sqlite")
    c.set("m", [ChatMessage(role="user", content="a")], "x")
    assert c.get("m", [ChatMessage(role="user", content="b")]) is None


def test_semantic_cache_fuzzy():
    c = SemanticCache(threshold=0.9)
    m1 = [ChatMessage(role="user", content="jalankan pytest untuk proyek ini sekarang")]
    m2 = [ChatMessage(role="user", content="jalankan pytest untuk proyek ini segera")]
    c.set("m", m1, "small")
    assert c.get("m", m2) == "small"
    assert c.get("m", [ChatMessage(role="user", content="desain ulang arsitektur besar")]) is None
