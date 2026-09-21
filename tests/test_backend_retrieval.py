"""Tests for application.backend.retrieval and document ingestion."""

from application.backend.ingestion.pipeline import load_all_policy_documents
from application.backend.retrieval.engine import hybrid_retriever


def test_document_parsing():
    docs = load_all_policy_documents()
    assert len(docs) > 0
    # Every doc must have metadata
    for d in docs:
        assert "region" in d.metadata
        assert "section" in d.metadata
        assert "policy_id" in d.metadata
        assert d.metadata["policy_id"] == "HR-207"


def test_hybrid_retrieval_and_filtering():
    # Test US retrieval
    us_results = hybrid_retriever.retrieve(
        query="What is the carry-over cap for a regular employee?",
        region="US",
        top_k=3,
        hybrid=True
    )
    assert len(us_results) > 0
    for r in us_results:
        assert r["region"] == "US"

    # Test UK retrieval
    uk_results = hybrid_retriever.retrieve(
        query="Who is eligible for sabbatical?",
        region="UK",
        top_k=3,
        hybrid=True
    )
    assert len(uk_results) > 0
    for r in uk_results:
        assert r["region"] == "UK"
