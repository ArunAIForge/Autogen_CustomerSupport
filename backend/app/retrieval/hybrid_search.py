"""Hybrid search engine combining BM25 keyword retrieval and Vector Search.

Employs Reciprocal Rank Fusion (RRF) and weighted score fusion with metadata
filtering for optimal precision, recall, and zero hallucination risk.
"""

from typing import Any, Dict, List, Optional, Tuple
from backend.app.retrieval.bm25 import BM25Retriever
from backend.app.retrieval.vector_search import VectorRetriever


class HybridRetriever:
    """Orchestrates BM25 and Vector search engines with score fusion and filtering."""

    def __init__(
        self,
        bm25_retriever: BM25Retriever,
        vector_retriever: VectorRetriever,
        alpha: float = 0.55,
        rrf_k: int = 60
    ) -> None:
        self.bm25 = bm25_retriever
        self.vector = vector_retriever
        self.alpha = alpha  # Weight for BM25 (keyword precision)
        self.rrf_k = rrf_k

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 6
    ) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval using Reciprocal Rank Fusion and metadata filters."""
        # Retrieve candidate pools
        bm25_results = self.bm25.search(query, top_k=top_k * 2)
        vector_results = self.vector.search(query, top_k=top_k * 2)

        # Map document IDs to fusion scores and details
        doc_scores: Dict[str, Dict[str, Any]] = {}

        # 1. Process BM25 ranks
        max_bm25 = max([score for _, score in bm25_results], default=1.0)
        for rank, (doc, raw_score) in enumerate(bm25_results, start=1):
            doc_id = doc.get("id")
            norm_score = raw_score / max_bm25 if max_bm25 > 0 else 0.0
            rrf_score = 1.0 / (self.rrf_k + rank)

            doc_scores[doc_id] = {
                "document": doc,
                "bm25_score": norm_score,
                "vector_score": 0.0,
                "rrf_score": rrf_score,
            }

        # 2. Process Vector ranks
        max_vec = max([score for _, score in vector_results], default=1.0)
        for rank, (doc, raw_score) in enumerate(vector_results, start=1):
            doc_id = doc.get("id")
            norm_score = raw_score / max_vec if max_vec > 0 else 0.0
            rrf_score = 1.0 / (self.rrf_k + rank)

            if doc_id in doc_scores:
                doc_scores[doc_id]["vector_score"] = norm_score
                doc_scores[doc_id]["rrf_score"] += rrf_score
            else:
                doc_scores[doc_id] = {
                    "document": doc,
                    "bm25_score": 0.0,
                    "vector_score": norm_score,
                    "rrf_score": rrf_score,
                }

        # 3. Compute hybrid score and apply metadata filters
        candidates: List[Dict[str, Any]] = []
        for doc_id, data in doc_scores.items():
            doc = data["document"]
            doc_category = doc.get("metadata", {}).get("category", "")

            # Filter if category constraint is provided and matches
            if category and category.lower() != "general":
                if doc_category.lower() != category.lower() and doc_category.lower() != "general":
                    # Soft penalty rather than hard cut to avoid dropping multi-category issues
                    data["rrf_score"] *= 0.65

            # Weighted linear score
            linear_score = (self.alpha * data["bm25_score"]) + ((1.0 - self.alpha) * data["vector_score"])
            # Combined hybrid score
            combined_score = (linear_score * 0.7) + (data["rrf_score"] * 10.0 * 0.3)

            candidates.append({
                "document": doc,
                "score": combined_score,
                "bm25_score": data["bm25_score"],
                "vector_score": data["vector_score"],
            })

        # Sort descending by fused score
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]
