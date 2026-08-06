"""EpisodicMemory — persistent episodic memory with SQLite + vector embeddings for semantic recall."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import faiss
except ImportError:
    faiss = None


class EpisodicMemory:
    """Persistent episodic memory with semantic search via embeddings.

    Stores memories with:
    - content: the memory text
    - tags: list of tags for categorization
    - timestamp: when memory was created
    - embedding: vector embedding for semantic search
    """

    def __init__(
        self,
        db_path: str | Path,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
        rebuild_threshold: int = 100,
    ):
        """Initialize episodic memory.

        Args:
            db_path: Path to SQLite database
            model_name: Sentence transformer model for embeddings
            embedding_dim: Dimension of embeddings (384 for all-MiniLM-L6-v2)
            rebuild_threshold: Number of deletions before triggering index rebuild
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self.rebuild_threshold = rebuild_threshold
        self._model: SentenceTransformer | None = None
        self._index: faiss.Index | None = None
        self._memory_ids: list[int] = []
        self._deleted_ids: set[int] = set()
        self._deletions_since_rebuild = 0
        self._conn = sqlite3.connect(self.db_path)
        self._init_db()
        self._load_existing_embeddings()

    def _get_model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model."""
        if self._model is None:
            if SentenceTransformer is None:
                raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _get_index(self) -> faiss.Index:
        """Get or create FAISS index with ID mapping for efficient deletion."""
        if self._index is None:
            if faiss is None:
                raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")
            # Use IndexIDMap to support removal by ID
            base_index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
            self._index = faiss.IndexIDMap(base_index)
        return self._index

    def _init_db(self) -> None:
        """Initialize database schema."""
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS episodic_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,  -- JSON array
                timestamp TEXT NOT NULL,
                embedding BLOB  -- serialized numpy array
            );
            CREATE INDEX IF NOT EXISTS idx_timestamp ON episodic_memory(timestamp);
            CREATE INDEX IF NOT EXISTS idx_key ON episodic_memory(key);
        """)
        self._conn.commit()

    def _load_existing_embeddings(self) -> None:
        """Load existing embeddings from database into FAISS index."""
        rows = self._conn.execute(
            "SELECT id, embedding FROM episodic_memory WHERE embedding IS NOT NULL"
        ).fetchall()
        
        if not rows:
            return
        
        embeddings = []
        ids = []
        for row_id, emb_blob in rows:
            if emb_blob:
                emb = np.frombuffer(emb_blob, dtype=np.float32)
                if emb.shape[0] == self.embedding_dim:
                    embeddings.append(emb)
                    ids.append(row_id)
        
        if embeddings:
            self._memory_ids = ids
            index = self._get_index()
            # Add with IDs for IndexIDMap
            np_ids = np.array(ids, dtype=np.int64)
            np_embeddings = np.vstack(embeddings).astype(np.float32)
            index.add_with_ids(np_embeddings, np_ids)

    def _maybe_rebuild_index(self) -> None:
        """Rebuild index if deletions exceed threshold."""
        if self._deletions_since_rebuild >= self.rebuild_threshold:
            self._rebuild_index()

    def remember(
        self,
        key: str,
        content: str,
        tags: list[str] | None = None,
    ) -> str:
        """Store a memory with semantic embedding.

        Args:
            key: Unique identifier for the memory
            content: Memory content
            tags: Optional tags for categorization

        Returns:
            Confirmation message
        """
        # Check if key exists and update
        existing = self._conn.execute(
            "SELECT id FROM episodic_memory WHERE key=?", (key,)
        ).fetchone()
        
        timestamp = datetime.now(UTC).isoformat()
        tags_json = json.dumps(tags or [])
        
        # Generate embedding
        model = self._get_model()
        embedding = model.encode([content], convert_to_numpy=True, normalize_embeddings=True)[0]
        emb_blob = embedding.astype(np.float32).tobytes()
        
        if existing:
            # Update existing - update both DB and FAISS index incrementally
            mem_id = existing[0]
            self._conn.execute(
                "UPDATE episodic_memory SET content=?, tags=?, timestamp=?, embedding=? WHERE id=?",
                (content, tags_json, timestamp, emb_blob, mem_id)
            )
            # Update FAISS index: remove old, add new with same ID
            index = self._get_index()
            try:
                index.remove_ids(np.array([mem_id], dtype=np.int64))
            except RuntimeError:
                pass  # ID might not be in index
            index.add_with_ids(embedding.reshape(1, -1).astype(np.float32), np.array([mem_id], dtype=np.int64))
        else:
            # Insert new
            cursor = self._conn.execute(
                "INSERT INTO episodic_memory (key, content, tags, timestamp, embedding) VALUES (?,?,?,?,?)",
                (key, content, tags_json, timestamp, emb_blob)
            )
            mem_id = cursor.lastrowid
            self._memory_ids.append(mem_id)
            # Add to FAISS index with ID
            index = self._get_index()
            index.add_with_ids(embedding.reshape(1, -1).astype(np.float32), np.array([mem_id], dtype=np.int64))
        
        self._conn.commit()
        return f"OK: disimpan ({key})"

    def recall(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Recall memories semantically similar to query.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of memory dicts with keys: id, content, tags, timestamp, score
        """
        if self._index is None or self._index.ntotal == 0:
            return []
        
        model = self._get_model()
        query_embedding = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
        
        # Search with extra to account for deleted entries
        search_limit = min(limit + len(self._deleted_ids), self._index.ntotal)
        scores, indices = self._index.search(query_embedding.astype(np.float32), search_limit)
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx not in self._deleted_ids:
                memory_id = int(idx)
                row = self._conn.execute(
                    "SELECT id, content, tags, timestamp FROM episodic_memory WHERE id=?",
                    (memory_id,)
                ).fetchone()
                if row:
                    results.append({
                        "id": row[0],
                        "content": row[1],
                        "tags": json.loads(row[2]) if row[2] else [],
                        "timestamp": row[3],
                        "score": float(score),
                    })
                if len(results) >= limit:
                    break
        
        return results

    def get_recent(self, limit: int = 8) -> list[dict[str, Any]]:
        """Get most recent memories."""
        rows = self._conn.execute(
            "SELECT id, content, tags, timestamp FROM episodic_memory ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        
        return [
            {
                "id": row[0],
                "content": row[1],
                "tags": json.loads(row[2]) if row[2] else [],
                "timestamp": row[3],
            }
            for row in rows
        ]

    def forget(self, key: str) -> str:
        """Delete a memory by key."""
        rows = self._conn.execute(
            "SELECT id FROM episodic_memory WHERE key=?", (key,)
        ).fetchall()
        
        if not rows:
            return f"(tidak ada memori untuk {key!r})"
        
        for (mem_id,) in rows:
            self._conn.execute("DELETE FROM episodic_memory WHERE id=?", (mem_id,))
            # Mark as deleted in FAISS index (lazy deletion)
            self._deleted_ids.add(mem_id)
            if mem_id in self._memory_ids:
                self._memory_ids.remove(mem_id)
            self._deletions_since_rebuild += 1
        
        self._conn.commit()
        self._maybe_rebuild_index()
        return f"OK: dihapus ({key})"

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from database (clean up deleted entries)."""
        if faiss is None:
            return
        
        self._index = faiss.IndexIDMap(faiss.IndexFlatIP(self.embedding_dim))
        self._memory_ids = []
        self._deleted_ids.clear()
        self._deletions_since_rebuild = 0
        
        rows = self._conn.execute(
            "SELECT id, embedding FROM episodic_memory WHERE embedding IS NOT NULL"
        ).fetchall()
        
        embeddings = []
        ids = []
        for row_id, emb_blob in rows:
            if emb_blob:
                emb = np.frombuffer(emb_blob, dtype=np.float32)
                if emb.shape[0] == self.embedding_dim:
                    embeddings.append(emb)
                    ids.append(row_id)
        
        if embeddings:
            self._memory_ids = ids
            index = self._get_index()
            np_ids = np.array(ids, dtype=np.int64)
            np_embeddings = np.vstack(embeddings).astype(np.float32)
            index.add_with_ids(np_embeddings, np_ids)

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()