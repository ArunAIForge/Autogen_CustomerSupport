"""Contextual and cross-encoder-style reranker for ClothesSpot.

Re-evaluates top-k candidate passages from hybrid search using deep
lexical and contextual alignment scores.
"""

import re
from typing import Any, Dict, List, Set, Tuple
from backend.app.retrieval.bm25 import ENGLISH_STOPWORDS

GENERIC_WORDS = {
    "sell", "want", "know", "help", "please", "like", "need", "tell",
    "custom", "company", "service", "item", "items", "good", "get", "got", "look", "looking"
}


class PassageReranker:
    """Reranks candidate knowledge passages using query-document cross-scoring."""

    def __init__(self) -> None:
        pass

    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Rerank candidates based on keyword coverage, density, and contextual fit."""
        if not candidates:
            return []

        q_lower = query.lower()
        all_tokens = re.findall(r"\b[a-zA-Z0-9_\-]{3,}\b", q_lower)
        # Content tokens excluding stopwords
        content_tokens = [t for t in all_tokens if t not in ENGLISH_STOPWORDS]
        # Specific domain topic tokens excluding generic modifiers (custom, company, etc.)
        topic_tokens = [t for t in content_tokens if t not in GENERIC_WORDS]

        if not topic_tokens:
            topic_tokens = content_tokens
        if not topic_tokens:
            topic_tokens = all_tokens

        scored_candidates: List[Tuple[Dict[str, Any], float]] = []

        for item in candidates:
            doc = item.get("document", {})
            base_score = float(item.get("score", 0.0))
            content = doc.get("content", "").lower()
            metadata = doc.get("metadata", {})
            title = metadata.get("title", "").lower()
            section = metadata.get("section", "").lower()

            doc_text = f"{title} {section} {content}"

            # Check coverage of specific topic tokens
            matched_topic_terms = [t for t in topic_tokens if t in doc_text]
            topic_coverage = len(matched_topic_terms) / len(topic_tokens) if topic_tokens else 0.0

            # Check coverage of all content tokens
            matched_content_terms = [t for t in content_tokens if t in doc_text]
            content_coverage = len(matched_content_terms) / len(content_tokens) if content_tokens else 0.0

            phrase_bonus = 0.0
            for t in matched_topic_terms:
                if t in section or t in title:
                    phrase_bonus += 0.15
                else:
                    phrase_bonus += 0.08

            # If no core topic token matched (e.g. spacesuits, astronaut), this passage does not answer the inquiry
            if len(matched_topic_terms) == 0:
                rerank_score = 0.05
            else:
                raw_score = (base_score * 0.3) + (topic_coverage * 0.5) + min(0.2, phrase_bonus)
                # Penalize low coverage
                rerank_score = raw_score * max(0.4, topic_coverage)

            scored_item = {
                "chunk_id": doc.get("id"),
                "file_name": metadata.get("source_file"),
                "title": metadata.get("title"),
                "section": metadata.get("section"),
                "category": metadata.get("category"),
                "content": doc.get("content"),
                "score": round(rerank_score, 4),
                "matched_terms": matched_topic_terms or matched_content_terms,
            }
            scored_candidates.append((scored_item, rerank_score))

        # Sort descending by rerank_score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        return [item[0] for item in scored_candidates[:top_k]]
