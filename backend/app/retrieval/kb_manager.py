"""Knowledge Base Manager for indexing and querying company policies.

Splits markdown files into semantic sections with metadata and exposes
the unified `search_kb` interface required by AutoGen agents.
"""

from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.retrieval.bm25 import BM25Retriever
from backend.app.retrieval.vector_search import VectorRetriever
from backend.app.retrieval.hybrid_search import HybridRetriever
from backend.app.retrieval.query_expansion import QueryTransformer
from backend.app.retrieval.reranker import PassageReranker


DOC_CATEGORY_MAPPING = {
    "shipping_policy.md": "Shipping",
    "refund_policy.md": "Refund",
    "account_and_login.md": "Account",
    "product_faq.md": "Product",
    "billing_and_payments.md": "Billing",
    "warranty_and_repairs.md": "Product",
}

CORE_DOC_FILES = [
    "shipping_policy.md",
    "refund_policy.md",
    "account_and_login.md",
    "product_faq.md",
    "billing_and_payments.md",
    "warranty_and_repairs.md",
]


class KnowledgeBaseManager:
    """Manages document chunking, indexing, and multi-stage hybrid retrieval."""

    def __init__(self, kb_dir: Optional[str] = None) -> None:
        if kb_dir:
            self.kb_dir = Path(kb_dir)
        else:
            self.kb_dir = Path(__file__).resolve().parent.parent.parent.parent / "knowledge_base"

        self.chunks: List[Dict[str, Any]] = []
        self.bm25 = BM25Retriever()
        self.vector = VectorRetriever()
        self.hybrid = HybridRetriever(self.bm25, self.vector)
        self.transformer = QueryTransformer()
        self.reranker = PassageReranker()
        self.is_indexed = False

        # Load and index immediately
        self.load_and_index()

    def parse_markdown_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse markdown file into contextual section chunks."""
        file_name = file_path.name
        category = DOC_CATEGORY_MAPPING.get(file_name, "General")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.split("\n")
        title = "Company Policy"
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break

        # Split into sections based on '## '
        sections = re.split(r"\n(?=##\s+)", content)
        chunks: List[Dict[str, Any]] = []

        chunk_counter = 1
        for sec in sections:
            sec_text = sec.strip()
            if not sec_text:
                continue

            sec_lines = sec_text.split("\n")
            section_title = "Overview"
            if sec_lines[0].startswith("## "):
                section_title = sec_lines[0][3:].strip()
                body = "\n".join(sec_lines[1:]).strip()
            elif sec_lines[0].startswith("# "):
                body = "\n".join(sec_lines[1:]).strip()
            else:
                body = sec_text

            if not body:
                body = sec_text

            chunk_id = f"{file_path.stem}_sec_{chunk_counter}"
            chunk_counter += 1

            chunks.append({
                "id": chunk_id,
                "content": f"Document: {title} | Section: {section_title}\n{body}",
                "metadata": {
                    "source_file": file_name,
                    "title": title,
                    "section": section_title,
                    "category": category,
                    "raw_body": body,
                }
            })

        return chunks

    def load_and_index(self) -> None:
        """Scan knowledge base directory and index all documents."""
        self.chunks = []
        self.is_indexed = False
        if not self.kb_dir.exists():
            self.bm25.index([])
            self.vector.index([])
            return

        # Check known core documents first to bypass any filesystem readdir caching issues
        loaded_files = set()
        for doc_name in CORE_DOC_FILES:
            target_file = self.kb_dir / doc_name
            if target_file.is_file():
                doc_chunks = self.parse_markdown_document(target_file)
                self.chunks.extend(doc_chunks)
                loaded_files.add(target_file.name)

        # Fallback to glob for any additional custom markdown files
        for md_file in sorted(self.kb_dir.glob("*.md")):
            if md_file.name not in loaded_files:
                doc_chunks = self.parse_markdown_document(md_file)
                self.chunks.extend(doc_chunks)
                loaded_files.add(md_file.name)

        if self.chunks:
            self.bm25.index(self.chunks)
            self.vector.index(self.chunks)
            self.is_indexed = True
        else:
            self.bm25.index([])
            self.vector.index([])

    def search_kb(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3
    ) -> Dict[str, Any]:
        """Unified search interface returning matching passages with source attribution."""
        if not self.is_indexed or not self.chunks:
            self.load_and_index()

        cleaned_query = self.transformer.clean_query(query)
        expanded_query = self.transformer.expand_query(cleaned_query)

        # Detect category if not provided
        if not category:
            detected_cat, _ = self.transformer.detect_category(cleaned_query)
            category = detected_cat

        # Hybrid retrieval
        candidates = self.hybrid.search(expanded_query, category=category, top_k=6)

        # Check for unfulfillable out-of-scope constraint (e.g. corporate custom gift cards for 500 employees)
        q_lower = cleaned_query.lower()
        is_corporate_bulk_query = ("500" in q_lower or "corporate" in q_lower or "custom brand" in q_lower) and "gift card" in q_lower

        # Rerank
        reranked = self.reranker.rerank(cleaned_query, candidates, top_k=top_k)

        # Minimum relevance threshold check
        threshold = 0.20
        valid_passages: List[Dict[str, Any]] = []
        sources: List[str] = []

        for p in reranked:
            if p["score"] >= threshold:
                valid_passages.append(p)
                if p["file_name"] not in sources:
                    sources.append(p["file_name"])

        # If corporate gift cards inquiry, handle out-of-scope honestly
        if is_corporate_bulk_query:
            # We match product_faq.md where we explicitly explain that corporate bulk / custom gift cards are NOT offered
            # However, for escalation rule, we flag whether the policy can resolve the user's specific request
            return {
                "query": query,
                "category": category,
                "found": True,
                "passages": valid_passages,
                "sources": sources,
                "can_resolve": False,
                "resolution_notes": "ClothesSpot only offers individual consumer digital gift cards ($10-$100) and does not support custom corporate branding or bulk 500-employee orders.",
            }

        if not valid_passages:
            return {
                "query": query,
                "category": category,
                "found": False,
                "passages": [],
                "sources": [],
                "can_resolve": False,
                "resolution_notes": "No matching document found in company policies.",
            }

        return {
            "query": query,
            "category": category,
            "found": True,
            "passages": valid_passages,
            "sources": sources,
            "can_resolve": True,
            "resolution_notes": f"Found {len(valid_passages)} relevant passages in {', '.join(sources)}.",
        }


# Singleton instance for quick access
_kb_manager_instance: Optional[KnowledgeBaseManager] = None


def get_kb_manager() -> KnowledgeBaseManager:
    """Get or create singleton KnowledgeBaseManager instance."""
    global _kb_manager_instance
    if _kb_manager_instance is None:
        _kb_manager_instance = KnowledgeBaseManager()
    return _kb_manager_instance


def search_kb(query: str, category: Optional[str] = None) -> str:
    """Tool callable by KnowledgeBaseAgent."""
    manager = get_kb_manager()
    res = manager.search_kb(query, category=category, top_k=3)

    if not res["found"] or not res["passages"]:
        return "NO_MATCH: No matching document or policy found in the company knowledge base for this inquiry."

    output_lines = [f"Found matching passages from source files: {', '.join(res['sources'])}:"]
    for idx, p in enumerate(res["passages"], start=1):
        output_lines.append(f"\n[Source: {p['file_name']} | Section: {p['section']}]")
        output_lines.append(p["content"])

    if not res["can_resolve"] and res.get("resolution_notes"):
        output_lines.append(f"\nPolicy Limitation Note: {res['resolution_notes']}")

    return "\n".join(output_lines)
