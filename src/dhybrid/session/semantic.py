"""SemanticMemory — memori semantik (embeddings + FAISS) untuk "relevant facts".

Fase 2.2 roadmap: inject fakta yang RELEVAN (berdasarkan makna) ke prompt,
bukan sekadar FTS keyword. Modul ini menyimpan dokumen (fakta proyek, body
skill, ringkasan sesi) beserta embedding-nya, lalu `relevant_facts(query, k)`
mengembalikan top-k dokumen untuk di-inject.

Graceful: bila sentence-transformers / faiss tidak terpasang, `available=False`
dan `relevant_facts()` mengembalikan `""` — pemanggil tetap bisa memakai
fallback keyword (MemoryStore.digest).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover
    SentenceTransformer = None

try:
    import faiss
except ImportError:  # pragma: no cover
    faiss = None

# Cache model global (hindari reload berulang antar instance).
_MODEL_CACHE: dict[str, SentenceTransformer] = {}
_MODEL_LOCK = threading.Lock()

DEFAULT_MODEL = "all-MiniLM-L6-v2"
DEFAULT_DIM = 384


class SemanticMemory:
    """Index dokumen + retrieval semantik untuk injeksi fakta relevan."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        embedding_dim: int = DEFAULT_DIM,
        index_path: str | Path | None = None,
    ):
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.index_path = Path(index_path) if index_path else None
        self._model: Any | None = None
        self._index: Any | None = None
        self._docs: list[dict[str, str]] = []  # {source, text}

    # ---------- availability & model ----------

    @property
    def available(self) -> bool:
        """Baik sentence-transformers maupun faiss tersedia?"""
        return SentenceTransformer is not None and faiss is not None

    def _get_model(self):
        if self._model is None:
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")
            with _MODEL_LOCK:
                if self.model_name not in _MODEL_CACHE:
                    _MODEL_CACHE[self.model_name] = SentenceTransformer(self.model_name)
                self._model = _MODEL_CACHE[self.model_name]
        return self._model

    def _get_index(self):
        if self._index is None:
            if faiss is None:
                raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")
            self._index = faiss.IndexFlatIP(self.embedding_dim)
        return self._index

    # ------------------------------------------------------------------
    # indexing
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Kosongkan index & dokumen."""
        self._index = None
        self._docs = []

    def index_docs(self, docs: list[dict[str, str]]) -> int:
        """Index daftar dokumen `[{"source": ..., "text": ...}]`.

        Hanya menambahkan teks non-kosong. Return jumlah teks yang di-index.
        Mengabaikan (dan di-skip) bila embedding tidak tersedia.
        """
        if not docs:
            return 0
        texts, sources = [], []
        for d in docs:
            t = (d.get("text") or "").strip()
            if not t:
                continue
            texts.append(t)
            sources.append(d.get("source") or "memory")
        if not texts:
            return 0
        model = self._get_model()
        emb = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        index = self._get_index()
        index.add(emb.astype(np.float32))
        for text, src in zip(texts, sources):
            self._docs.append({"source": src, "text": text})
        return len(texts)

    # ------------------------------------------------------------------
    # retrieval
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top-k dokumen menyerupai query (score menurun).

        Return: [{"source", "text", "score"}]. Empty bila index kosong / lib hilang.
        """
        if not self.available or not self._docs or not query:
            return []
        model = self._get_model()
        q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        index = self._get_index()
        k = min(top_k, len(self._docs))
        scores, indices = index.search(q_emb.astype(np.float32), k)
        out = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._docs):
                out.append(
                    {
                        "source": self._docs[int(idx)]["source"],
                        "text": self._docs[int(idx)]["text"],
                        "score": float(score),
                    }
                )
        return out

    def relevant_facts(self, query: str, top_k: int = 5, max_len: int = 220) -> str:
        """Format top-k fakta relevansisebagai teks siap-inject.

        Return "" bila tidak tersedia/tidak cocok (pemanggil boleh fallback).
        """
        results = self.search(query, top_k)
        if not results:
            return ""
        lines = []
        for r in results:
            text = r["text"]
            if len(text) > max_len:
                text = text[:max_len] + "…"
            src = r["source"]
            lines.append(f"• ({src}: {r['score']:.2f}) {text}")
        return "\n".join(lines)


def build_relevant_facts(
    query: str,
    *,
    docs: list[dict[str, str]] | None = None,
    mem: Any | None = None,
    skills: list[Any] | None = None,
    top_k: int = 5,
) -> str:
    """Fasilitas: kumpulkan dokumen (memori + skill + ekstra) lalu _search_.

    - `docs`: daftar `[{"source", "text"}]` ekstra (mis. summary sesi).
    - `mem`: `MemoryStore` → baca fakta (key, value) jangka panjang.
    - `skills`: daftar objek dengan atribut `.body`/`.name` (dipakai bila dibutuhkan).
    Return "" bila tak ada dokumen / model embedding tak tersedia (fallback aman).
    """
    collected: list[dict[str, str]] = list(docs or [])
    if mem is not None:
        from dhybrid.session.memory import MemoryStore

        if isinstance(mem, MemoryStore):
            for key, value in _memory_kv_pairs(mem):
                collected.append({"source": f"memory:{key}", "text": value})
    if skills:
        for sk in skills:
            body = getattr(sk, "body", "") or ""
            name = getattr(sk, "name", "?")
            collected.append({"source": f"skill:{name}", "text": body[:400]})
    if not collected:
        return ""
    sm = SemanticMemory()
    if not sm.available:
        return ""
    sm.index_docs(collected)
    return sm.relevant_facts(query, top_k=top_k)


def _memory_kv_pairs(mem) -> list[tuple[str, str]]:
    """Fakta memori jangka panjang via API publik (bukan SQL internal)."""
    getter = getattr(mem, "all_facts", None)
    if callable(getter):
        try:
            return getter(limit=200)
        except Exception:  # noqa: BLE001 — store apapun harus aman di-call
            return []
    return []