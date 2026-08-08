"""Tests untuk SemanticMemory (Fase 2.2) — relevant facts via embeddings."""
import pytest

from dhybrid.session.memory import MemoryStore
from dhybrid.session.semantic import SemanticMemory, build_relevant_facts

# Model mini-MiniLM kecil & CPU; test dipisah agar tidak memblokir suite.
# Test yang butuh model nyata ditandai dan akan di-skip bila tak tersedia.


def test_available_reflects_libs():
    sm = SemanticMemory()
    # available = sentence_transformers AND faiss terpasang; tidak boleh crash.
    assert isinstance(sm.available, bool)


def test_empty_index_returns_empty():
    sm = SemanticMemory()
    assert sm.search("apapun") == []
    assert sm.relevant_facts("apapun") == ""


def test_reset_clears_docs():
    sm = SemanticMemory()
    # tanpa index nyata, reset tetap aman
    sm.reset()
    assert sm._docs == []


def test_index_docs_skips_empty():
    sm = SemanticMemory()
    n = sm.index_docs([{"source": "a", "text": ""}, {"source": "b", "text": "   "}])
    assert n == 0
    assert sm._docs == []


def test_build_relevant_facts_empty_when_no_docs(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    out = build_relevant_facts("cara setup redis", mem=mem, skills=[])
    # tanpa dokumen → kosong (fallback aman, tidak boleh exception)
    assert out == ""


def test_memory_store_all_facts_public_api(tmp_path):
    from dhybrid.session.memory import MemoryStore as MS

    mem = MS(tmp_path / "m.sqlite")
    assert mem.all_facts() == []
    mem.remember("pokok A", "konvensi proyek")
    assert mem.all_facts() == [("pokok A", "konvensi proyek")]


def test_build_relevant_facts_with_memory_facts(tmp_path):
    mem = MemoryStore(tmp_path / "m.sqlite")
    mem.remember("redis", "Proyek ini pakai redis sebagai cache, port 6379")
    sm = SemanticMemory()
    if not sm.available:
        pytest.skip("sentence-transformers/faiss tidak tersedia")
    out = build_relevant_facts("cara setup redis cache", mem=mem)
    assert "redis" in out


def test_relevant_facts_roundtrip_with_model():
    sm = SemanticMemory()
    if not sm.available:
        pytest.skip("sentence-transformers/faiss tidak tersedia")
    sm.index_docs(
        [
            {"source": "memory:redis", "text": "redis cache port 6379 untuk auth"},
            {"source": "skill:tdd", "text": "tulis test dulu sebelum implementasi"},
        ]
    )
    results = sm.search("redis cache setup", top_k=2)
    assert len(results) == 2
    # yang paling relevan dgn "redis cache" harus di urutan pertama
    assert results[0]["source"] == "memory:redis"
    text = sm.relevant_facts("redis cache", top_k=1)
    assert "memory:redis" in text
    assert "0." in text  # score desimal