"""Knowledge base indexer with vector search."""

from typing import Optional

import numpy as np

from agenteval.models.knowledge import Document, KnowledgeBase
from agenteval.knowledge.parser import DocumentChunker


class KnowledgeIndexer:
    """Index knowledge base for semantic search."""

    def __init__(self, embedding_dim: int = 384):
        """Initialize indexer.

        Args:
            embedding_dim: Dimension of embedding vectors.
        """
        self.embedding_dim = embedding_dim
        self.chunks: list[dict] = []
        self.embeddings: Optional[np.ndarray] = None
        self._index = None
        self._chunker = DocumentChunker()

    def index(self, kb: KnowledgeBase) -> None:
        """Index all documents in the knowledge base."""
        self.chunks = []

        for doc in kb.documents:
            doc_chunks = self._chunker.chunk(doc)
            self.chunks.extend(doc_chunks)

        if not self.chunks:
            return

        # Generate embeddings for all chunks
        texts = [chunk["content"] for chunk in self.chunks]
        self.embeddings = self._generate_embeddings(texts)

        # Build FAISS index
        self._build_index()

    def search(self, query: str, k: int = 5) -> list[dict]:
        """Search for relevant chunks.

        Args:
            query: Search query.
            k: Number of results to return.

        Returns:
            List of relevant chunks with scores.
        """
        if not self.chunks or self.embeddings is None:
            return []

        # Generate query embedding
        query_embedding = self._generate_embeddings([query])[0]

        # Search using FAISS if available, otherwise brute force
        if self._index is not None:
            return self._search_faiss(query_embedding, k)
        else:
            return self._search_brute_force(query_embedding, k)

    def _generate_embeddings(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts.

        Uses a simple bag-of-words approach as fallback if sentence-transformers
        is not available.
        """
        try:
            # Try to use sentence-transformers if available
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts, convert_to_numpy=True)
            return embeddings
        except ImportError:
            # Fallback to simple TF-IDF-like embeddings
            return self._simple_embeddings(texts)

    def _simple_embeddings(self, texts: list[str]) -> np.ndarray:
        """Generate simple embeddings using word frequency."""
        # Build vocabulary from all texts
        vocab: dict[str, int] = {}
        for text in texts:
            words = text.lower().split()
            for word in words:
                if word not in vocab:
                    vocab[word] = len(vocab)

        # Limit vocabulary size
        vocab_size = min(len(vocab), self.embedding_dim)

        # Generate embeddings
        embeddings = np.zeros((len(texts), vocab_size), dtype=np.float32)

        for i, text in enumerate(texts):
            words = text.lower().split()
            word_counts: dict[str, int] = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1

            for word, count in word_counts.items():
                if word in vocab and vocab[word] < vocab_size:
                    # TF-IDF-like weighting
                    tf = count / len(words) if words else 0
                    embeddings[i, vocab[word]] = tf

            # Normalize
            norm = np.linalg.norm(embeddings[i])
            if norm > 0:
                embeddings[i] /= norm

        return embeddings

    def _build_index(self) -> None:
        """Build FAISS index."""
        try:
            import faiss

            dim = self.embeddings.shape[1]
            self._index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity for normalized vectors)

            # Normalize embeddings for cosine similarity
            normalized = self.embeddings / np.linalg.norm(
                self.embeddings, axis=1, keepdims=True
            )
            self._index.add(normalized.astype(np.float32))
        except ImportError:
            # FAISS not available, will use brute force search
            self._index = None

    def _search_faiss(self, query_embedding: np.ndarray, k: int) -> list[dict]:
        """Search using FAISS index."""
        # Normalize query
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        query_norm = query_norm.reshape(1, -1).astype(np.float32)

        k = min(k, len(self.chunks))
        scores, indices = self._index.search(query_norm, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0:
                chunk = self.chunks[idx].copy()
                chunk["score"] = float(score)
                results.append(chunk)

        return results

    def _search_brute_force(self, query_embedding: np.ndarray, k: int) -> list[dict]:
        """Search using brute force cosine similarity."""
        # Normalize
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        embeddings_norm = self.embeddings / np.linalg.norm(
            self.embeddings, axis=1, keepdims=True
        )

        # Compute similarities
        similarities = np.dot(embeddings_norm, query_norm)

        # Get top k
        k = min(k, len(self.chunks))
        top_indices = np.argsort(similarities)[-k:][::-1]

        results = []
        for idx in top_indices:
            chunk = self.chunks[idx].copy()
            chunk["score"] = float(similarities[idx])
            results.append(chunk)

        return results

    def get_document_chunks(self, doc_path: str) -> list[dict]:
        """Get all chunks from a specific document."""
        return [c for c in self.chunks if c["document_path"] == doc_path]

    def get_all_facts(self) -> list[str]:
        """Extract all facts from the knowledge base for test generation."""
        facts = []
        for chunk in self.chunks:
            # Split chunk into sentences as potential facts
            content = chunk["content"]
            sentences = self._split_sentences(content)
            for sentence in sentences:
                sentence = sentence.strip()
                if len(sentence) > 20 and len(sentence) < 500:  # Filter noise
                    facts.append(sentence)
        return facts

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re

        # Simple sentence splitting
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

