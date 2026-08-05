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
    ):
        """Initialize episodic memory.

        Args:
            db_path: Path to SQLite database
            model_name: Sentence transformer model for embeddings
            embedding_dim: Dimension of embeddings (384 for all-MiniLM-L6-v2)
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self._model: SentenceTransformer | None = None
        self._index: faiss.Index | None = None
        self._memory_ids: list[int] = []
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
        """Get or create FAISS index."""
        if self._index is None:
            if faiss is None:
                raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")
            self._index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
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
            index.add(np.vstack(embeddings).astype(np.float32))

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
            # Update existing
            self._conn.execute(
                "UPDATE episodic_memory SET content=?, tags=?, timestamp=?, embedding=? WHERE id=?",
                (content, tags_json, timestamp, emb_blob, existing[0])
            )
            # Update FAISS index - rebuild (simple approach)
            self._rebuild_index()
        else:
            # Insert new
            cursor = self._conn.execute(
                "INSERT INTO episodic_memory (key, content, tags, timestamp, embedding) VALUES (?,?,?,?,?)",
                (key, content, tags_json, timestamp, emb_blob)
            )
            self._memory_ids.append(cursor.lastrowid)
            # Add to FAISS index
            index = self._get_index()
            index.add(embedding.reshape(1, -1).astype(np.float32))
        
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
        
        scores, indices = self._index.search(query_embedding.astype(np.float32), min(limit, self._index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._memory_ids):
                memory_id = self._memory_ids[idx]
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
            if mem_id in self._memory_ids:
                self._memory_ids.remove(mem_id)
        
        self._conn.commit()
        self._rebuild_index()
        return f"OK: dihapus ({key})"

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from database."""
        if faiss is None:
            return
        
        self._index = faiss.IndexFlatIP(self.embedding_dim)
        self._memory_ids = []
        
        rows = self._conn.execute(
            "SELECT id, embedding FROM episodic_memory WHERE embedding IS NOT NULL"
        ).fetchall()
        
        embeddings = []
        for row_id, emb_blob in rows:
            if emb_blob:
                emb = np.frombuffer(emb_blob, dtype=np.float32)
                if emb.shape[0] == self.embedding_dim:
                    embeddings.append(emb)
                    self._memory_ids.append(row_id)
        
        if embeddings:
            self._index.add(np.vstack(embeddings).astype(np.float32))

    def close(self) -> None:
        """Close database connection."""
        self._conn.close()