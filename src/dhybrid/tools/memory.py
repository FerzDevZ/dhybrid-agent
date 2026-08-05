"""Tool memory — akses memori jangka panjang dari agent."""

from __future__ import annotations

from dhybrid.session.episodic_memory import EpisodicMemory
from dhybrid.session.memory import MemoryStore


def register(reg, max_chars: int = 8000, store: MemoryStore | None = None) -> None:
    mem = store or MemoryStore()
    from dhybrid.config import Config
    cfg = Config.load()
    episodic_db = cfg.workspace / "episodic.sqlite"
    episodic = EpisodicMemory(episodic_db)

    def memory_set(key: str, value: str) -> str:
        return mem.remember(key, value)

    def memory_get(key: str) -> str:
        return mem.recall(key)

    def memory_search(query: str) -> str:
        return mem.search(query)

    def episodic_remember(key: str, content: str, tags: str = "") -> str:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        return episodic.remember(key, content, tag_list)

    def episodic_recall(query: str, limit: int = 5) -> str:
        results = episodic.recall(query, limit)
        if not results:
            return "(tidak ada memori episodic cocok)"
        return "\n".join(
            f"[{r['score']:.3f}] {r['key']}: {r['content'][:200]} (tags: {', '.join(r['tags'])})"
            for r in results
        )

    def episodic_recent(limit: int = 8) -> str:
        results = episodic.get_recent(limit)
        if not results:
            return "(tidak ada memori episodic)"
        return "\n".join(
            f"[{r['timestamp']}] {r['key']}: {r['content'][:200]}"
            for r in results
        )

    def episodic_forget(key: str) -> str:
        return episodic.forget(key)

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
    reg.register(
        "episodic_remember",
        "Simpan memori episodic dengan embedding semantik untuk recall berdasarkan makna.",
        {"key": {"type": "string"}, "content": {"type": "string"}, "tags": {"type": "string"}},
        episodic_remember,
    )
    reg.register(
        "episodic_recall",
        "Cari memori episodic secara semantik (berdasarkan makna, bukan keyword).",
        {"query": {"type": "string"}, "limit": {"type": "integer"}},
        episodic_recall,
    )
    reg.register(
        "episodic_recent",
        "Lihat memori episodic terbaru.",
        {"limit": {"type": "integer"}},
        episodic_recent,
    )
    reg.register(
        "episodic_forget",
        "Hapus memori episodic berdasarkan key.",
        {"key": {"type": "string"}},
        episodic_forget,
    )
