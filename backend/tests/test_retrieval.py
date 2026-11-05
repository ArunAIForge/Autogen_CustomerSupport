"""Unit and integration tests for knowledge base retrieval mechanism."""

try:
    import pytest
except ImportError:
    pytest = None
import bootstrap  # noqa: F401
from backend.app.retrieval.bm25 import BM25Retriever
from backend.app.retrieval.vector_search import VectorRetriever
from backend.app.retrieval.query_expansion import QueryTransformer
from backend.app.retrieval.reranker import PassageReranker
from backend.app.retrieval.kb_manager import get_kb_manager


def test_bm25_retrieval():
    retriever = BM25Retriever()
    docs = [
        {"id": "doc1", "content": "Our return window for footwear and shoes is 30 days."},
        {"id": "doc2", "content": "Orders are shipped within 3 to 5 business days."},
        {"id": "doc3", "content": "Click forgot password to reset your login credentials."}
    ]
    retriever.index(docs)
    
    res = retriever.search("footwear return shoes", top_k=2)
    assert len(res) > 0
    assert res[0][0]["id"] == "doc1"


def test_vector_similarity_search():
    v_retriever = VectorRetriever(dim=128)
    docs = [
        {"id": "v1", "content": "Standard delivery takes 3 to 5 business days.", "metadata": {"title": "Shipping", "section": "Delivery"}},
        {"id": "v2", "content": "Broken or damaged blenders can be replaced in 14 days.", "metadata": {"title": "Product", "section": "Replacements"}},
    ]
    v_retriever.index(docs)

    res = v_retriever.search("blender replacement broken", top_k=1)
    assert len(res) > 0
    assert res[0][0]["id"] == "v2"


def test_query_expansion():
    transformer = QueryTransformer()
    expanded = transformer.expand_query("shoes return")
    assert "footwear" in expanded or "30 days" in expanded or "refund" in expanded


def test_kb_manager_comprehensive():
    km = get_kb_manager()
    assert km.is_indexed is True
    assert len(km.chunks) >= 4

    # Test shipping match
    res_ship = km.search_kb("Where is my order? It was supposed to arrive yesterday.")
    assert res_ship["found"] is True
    assert "shipping_policy.md" in res_ship["sources"]

    # Test refund match
    res_ref = km.search_kb("I want to return the shoes I bought last week.")
    assert res_ref["found"] is True
    assert "refund_policy.md" in res_ref["sources"]

    # Test password match
    res_pwd = km.search_kb("I forgot my password and can't log in.")
    assert res_pwd["found"] is True
    assert "account_and_login.md" in res_pwd["sources"]
