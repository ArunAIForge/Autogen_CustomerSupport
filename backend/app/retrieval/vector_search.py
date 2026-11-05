"""Vector and Semantic Similarity Search Engine.

Implements dense semantic representation and cosine similarity retrieval.
Uses deterministic token and character n-gram hashing with the Python standard
library and does not require external embedding services.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple

def _hash_token(token: str, dim: int = 128) -> int:
    """Deterministic hash for token feature hashing."""
    h = 2166136261
    for char in token:
        h = (h ^ ord(char)) * 16777619
    return h % dim


def _compute_dense_representation(text: str, dim: int = 256) -> List[float]:
    """Compute dense semantic embedding vector for text using standard library."""
    vec = [0.0] * dim
    tokens = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())

    if not tokens:
        return vec

    # Word and character 3-gram feature hashing with positional weighting
    for idx, token in enumerate(tokens):
        # Word hash
        h_word = _hash_token(token, dim)
        weight = 1.0 + (1.0 / (idx + 1))
        vec[h_word] += weight

        # Char 3-grams for subword semantics (e.g., return, refund, broken, blender)
        if len(token) >= 3:
            for i in range(len(token) - 2):
                ngram = token[i:i + 3]
                h_ngram = _hash_token(ngram, dim)
                vec[h_ngram] += 0.5

    # L2 normalize
    norm_sq = sum(v * v for v in vec)
    if norm_sq > 1e-18:
        inv_norm = 1.0 / math.sqrt(norm_sq)
        vec = [v * inv_norm for v in vec]

    return vec


def _dot_product(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute dot product of two vectors."""
    return sum(a * b for a, b in zip(vec_a, vec_b))


class VectorRetriever:
    """In-memory Vector Search engine supporting dense semantic similarity."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.documents: List[Dict[str, Any]] = []
        self.vectors: List[List[float]] = []

    def index(self, documents: List[Dict[str, Any]]) -> None:
        """Index a list of documents by computing and storing their dense embeddings."""
        self.documents = documents
        self.vectors = []
        if not documents:
            return

        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            title = metadata.get("title", "")
            section = metadata.get("section", "")
            full_text = f"{title} {section} {content}"
            emb = _compute_dense_representation(full_text, self.dim)
            self.vectors.append(emb)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Perform semantic cosine similarity search."""
        if not self.vectors or len(self.documents) == 0:
            return []

        q_vec = _compute_dense_representation(query, self.dim)
        q_norm = math.sqrt(sum(v * v for v in q_vec))
        if q_norm < 1e-9:
            return []

        # Cosine similarity is dot product because vectors are L2-normalized
        scored_docs: List[Tuple[int, float]] = []
        for idx, doc_vec in enumerate(self.vectors):
            sim = _dot_product(doc_vec, q_vec)
            if sim > 0.05:
                scored_docs.append((idx, float(sim)))

        # Rank by score descending
        scored_docs.sort(key=lambda x: x[1], reverse=True)

        results: List[Tuple[Dict[str, Any], float]] = []
        for idx, sim in scored_docs[:top_k]:
            results.append((self.documents[idx], sim))

        return results
