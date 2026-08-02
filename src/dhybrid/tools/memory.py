"""Tool memory — akses memori jangka panjang dari agent."""

from __future__ import annotations

from dhybrid.session.memory import MemoryStore


def register(reg, max_chars: int = 8000, store: MemoryStore | None = None) -> None:
    mem = store or MemoryStore()

    def memory_set(key: str, value: str) -> str:
        return mem.remember(key, value)

    def memory_get(key: str) -> str:
        return mem.recall(key)

    def memory_search(query: str) -> str:
        return mem.search(query)

    reg.register(
        "memory_set",
        "Simpan fakta jangka panjang (konvensi proyek, keputusan arsitektur).",
        {"key": {"type": "string"}, "value": {"type": "string"}},
        memory_set,
    )
    reg.register(
        "memory_get",
        "Ambil fakta jangka panjang berdasarkan key.",
        {"key": {"type": "string"}},
        memory_get,
    )
    reg.register(
        "memory_search",
        "Cari memori jangka panjang (FTS).",
        {"query": {"type": "string"}},
        memory_search,
    )
