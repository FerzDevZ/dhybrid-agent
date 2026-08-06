"""Semantic code search using sentence embeddings."""

from __future__ import annotations

from pathlib import Path
import threading

import numpy as np

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    import faiss
except ImportError:
    faiss = None


# Global model cache to avoid reloading across calls
_global_model_cache: dict[str, SentenceTransformer] = {}
_model_cache_lock = threading.Lock()


class SemanticSearch:
    """Semantic code search using sentence embeddings and FAISS index."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", index_path: str | None = None):
        """Initialize semantic search.

        Args:
            model_name: Sentence transformer model to use
            index_path: Optional path to persist FAISS index
        """
        self.model_name = model_name
        self.index_path = Path(index_path) if index_path else None
        self._model: SentenceTransformer | None = None
        self._index: faiss.Index | None = None
        self._file_paths: list[str] = []
        self._file_contents: dict[str, str] = {}
        self._embeddings: np.ndarray | None = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy load the sentence transformer model (cached globally)."""
        if self._model is None:
            with _model_cache_lock:
                if self.model_name not in _global_model_cache:
                    if SentenceTransformer is None:
                        raise RuntimeError("sentence-transformers not installed. Run: pip install sentence-transformers")
                    _global_model_cache[self.model_name] = SentenceTransformer(self.model_name)
                self._model = _global_model_cache[self.model_name]
        return self._model

    def _get_index(self, dimension: int) -> faiss.Index:
        """Get or create FAISS index."""
        if self._index is None:
            if faiss is None:
                raise RuntimeError("faiss-cpu not installed. Run: pip install faiss-cpu")
            self._index = faiss.IndexFlatIP(dimension)  # Inner product for cosine similarity
        return self._index

    def index(self, files: dict[str, str]) -> None:
        """Index a set of files for semantic search.

        Args:
            files: Dict mapping file paths to source code content
        """
        if not files:
            return

        model = self._get_model()
        
        # Prepare texts for embedding
        new_paths = list(files.keys())
        new_contents = [files[path] for path in new_paths]
        
        # Generate embeddings
        new_embeddings = model.encode(new_contents, convert_to_numpy=True, normalize_embeddings=True)
        
        # Add to existing index or create new
        if self._embeddings is not None and len(self._file_paths) > 0:
            # Append new embeddings
            self._embeddings = np.vstack([self._embeddings, new_embeddings])
            self._file_paths.extend(new_paths)
            for path in new_paths:
                self._file_contents[path] = files[path]
            # Rebuild index
            index = self._get_index(self._embeddings.shape[1])
            index.reset()
            index.add(self._embeddings.astype(np.float32))
        else:
            # First time indexing
            self._embeddings = new_embeddings
            self._file_paths = new_paths
            self._file_contents = dict(files)
            index = self._get_index(self._embeddings.shape[1])
            index.add(self._embeddings.astype(np.float32))

    def search(self, query: str, top_k: int = 5) -> list[tuple[str, float, str]]:
        """Search for files semantically similar to query.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of (file_path, score, snippet) tuples sorted by relevance
        """
        if self._embeddings is None or len(self._file_paths) == 0:
            return []

        model = self._get_model()
        query_embedding = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)

        index = self._get_index(self._embeddings.shape[1])
        scores, indices = index.search(query_embedding.astype(np.float32), min(top_k, len(self._file_paths)))

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self._file_paths):
                path = self._file_paths[idx]
                content = self._file_contents.get(path, "")
                # Extract first 200 chars as snippet
                snippet = content[:200].replace("\n", " ")
                results.append((path, float(score), snippet))

        return results

    def remove(self, file_path: str) -> None:
        """Remove a file from the index (requires rebuild)."""
        if file_path in self._file_contents:
            del self._file_contents[file_path]
            # Rebuild from remaining files
            remaining_files = {p: self._file_contents[p] for p in self._file_paths if p != file_path}
            self.clear()
            self.index(remaining_files)

    def clear(self) -> None:
        """Clear the index."""
        self._index = None
        self._file_paths = []
        self._file_contents = {}
        self._embeddings = None

    def save(self) -> None:
        """Save index to disk."""
        if self.index_path and self._embeddings is not None:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            # Save FAISS index
            if self._index:
                faiss.write_index(self._index, str(self.index_path) + ".faiss")
            # Save metadata
            import json
            meta = {
                "model_name": self.model_name,
                "file_paths": self._file_paths,
                "file_contents": self._file_contents,
            }
            (self.index_path.with_suffix(".json")).write_text(json.dumps(meta))

    def load(self) -> bool:
        """Load index from disk."""
        if not self.index_path:
            return False
        
        faiss_path = self.index_path.with_suffix(".faiss")
        json_path = self.index_path.with_suffix(".json")
        
        if not faiss_path.exists() or not json_path.exists():
            return False

        try:
            import json
            meta = json.loads(json_path.read_text())
            
            self.model_name = meta["model_name"]
            self._file_paths = meta["file_paths"]
            self._file_contents = meta["file_contents"]
            
            # Load FAISS index
            if faiss is None:
                raise RuntimeError("faiss-cpu not installed")
            self._index = faiss.read_index(str(faiss_path))
            
            # Rebuild embeddings from file contents
            if self._file_contents:
                model = self._get_model()
                contents = [self._file_contents[p] for p in self._file_paths]
                self._embeddings = model.encode(contents, convert_to_numpy=True, normalize_embeddings=True)
            
            return True
        except (OSError, json.JSONDecodeError, RuntimeError):
            return False


def semantic_search_tool(query: str, workspace: str, top_k: int = 5, index_path: str | None = None) -> str:
    """Search code semantically in a workspace.

    Args:
        query: Search query (natural language)
        workspace: Path to workspace directory
        top_k: Number of results to return
        index_path: Optional path to persist/load FAISS index
    """
    from pathlib import Path
    
    ws_path = Path(workspace)
    if not ws_path.is_dir():
        return f"ERROR: workspace not found: {workspace}"

    # Collect source files
    ext_to_lang = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".cs": "c_sharp",
        ".php": "php",
        ".rb": "ruby",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }

    files = {}
    for ext in ext_to_lang:
        for f in ws_path.rglob(f"*{ext}"):
            if f.is_file():
                try:
                    rel = f.relative_to(ws_path)
                    content = f.read_text(encoding="utf-8", errors="replace")
                    if content.strip():  # Skip empty files
                        files[str(rel)] = content
                except (OSError, UnicodeDecodeError):
                    pass

    if not files:
        return "ERROR: no source files found in workspace"

    ss = SemanticSearch(index_path=index_path)
    ss.index(files)
    results = ss.search(query, top_k=top_k)

    if not results:
        return "No results found."

    lines = [f"Semantic search results for: \"{query}\" (top {top_k}):"]
    for path, score, snippet in results:
        lines.append(f"  {path} (score: {score:.3f})")
        lines.append(f"    {snippet[:150]}...")
    return "\n".join(lines)


def register(reg, max_chars: int = 8000) -> None:
    reg.register(
        "semantic_search",
        "Semantic code search (sentence embeddings + FAISS): find code by meaning, not keywords. "
        "Searches workspace for semantically similar code snippets.",
        {"query": {"type": "string", "required": True}, "workspace": {"type": "string", "required": True}, 
         "top_k": {"type": "integer"}, "index_path": {"type": "string"}},
        semantic_search_tool,
    )