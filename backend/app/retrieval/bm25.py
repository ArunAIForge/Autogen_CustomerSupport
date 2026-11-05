"""BM25 (Best Matching 25) Okapi keyword retrieval engine.

Provides full inverted index calculation, term frequencies, document length
normalization (k1=1.5, b=0.75), and IDF weighting without requiring external
heavy dependencies.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple


ENGLISH_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such",
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're",
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which",
    "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you",
    "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"
}


def tokenize(text: str, remove_stopwords: bool = True) -> List[str]:
    """Tokenize string into lowercase alphanumeric words."""
    words = re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", text.lower())
    if remove_stopwords:
        return [w for w in words if w not in ENGLISH_STOPWORDS]
    return words


class BM25Retriever:
    """Okapi BM25 implementation for indexing and querying text chunks."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lens: List[int] = []
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.documents: List[Dict[str, Any]] = []

    def index(self, documents: List[Dict[str, Any]]) -> None:
        """Index a list of documents. Each document must have 'content' and 'metadata'."""
        self.documents = documents
        self.corpus_size = len(documents)
        if self.corpus_size == 0:
            return

        total_len = 0
        df: Dict[str, int] = {}
        self.doc_lens = []
        self.doc_freqs = []

        for doc in documents:
            tokens = tokenize(doc.get("content", ""))
            doc_len = len(tokens)
            self.doc_lens.append(doc_len)
            total_len += doc_len

            # Calculate term frequencies for this doc
            tf: Dict[str, int] = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_freqs.append(tf)

            # Update document frequencies
            for token in tf.keys():
                df[token] = df.get(token, 0) + 1

        self.avg_doc_len = total_len / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate IDF with floor smoothing
        self.idf = {}
        for token, freq in df.items():
            # Standard Okapi BM25 IDF formula
            numerator = (self.corpus_size - freq + 0.5)
            denominator = (freq + 0.5)
            self.idf[token] = math.log((numerator / denominator) + 1.0)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Dict[str, Any], float]]:
        """Search the indexed documents using BM25 scoring."""
        if self.corpus_size == 0:
            return []

        query_tokens = tokenize(query, remove_stopwords=False)
        scores = [0.0] * self.corpus_size

        for token in query_tokens:
            if token not in self.idf:
                continue

            token_idf = self.idf[token]

            for doc_idx in range(self.corpus_size):
                doc_tf = self.doc_freqs[doc_idx].get(token, 0)
                if doc_tf == 0:
                    continue

                doc_len = self.doc_lens[doc_idx]
                numerator = doc_tf * (self.k1 + 1)
                denominator = doc_tf + self.k1 * (1 - self.b + self.b * (doc_len / (self.avg_doc_len or 1.0)))
                scores[doc_idx] += token_idf * (numerator / denominator)

        ranked_indices = sorted(range(self.corpus_size), key=lambda i: scores[i], reverse=True)
        results: List[Tuple[Dict[str, Any], float]] = []

        for idx in ranked_indices[:top_k]:
            score = scores[idx]
            if score > 0.0:
                results.append((self.documents[idx], score))

        return results
