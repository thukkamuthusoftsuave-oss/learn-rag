"""HR-207 Policy RAG — a retrieval-augmented policy assistant.

The package is layered so each concern has exactly one home:

``policy_rag.corpus``
    Source documents: the generator that writes ``data/`` and the chunkers.
``policy_rag.indexing``
    Turns the corpus into the ChromaDB vector store plus the docstore.
``policy_rag.retrieval``
    Builds query engines (vector-only or BM25 + vector fused with RRF).
``policy_rag.chat``
    The assistant itself: multi-turn sessions and the answer service that
    every interface (CLI, HTTP API, evaluation suites) calls.
``policy_rag.observability``
    The trace log every answer is written to, and the error taxonomy used to
    label those traces.
``policy_rag.evaluation``
    Offline suites that run the assistant and score it: retrieval quality,
    chunking strategy, answer quality and end-to-end smoke checks.
``policy_rag.api``
    FastAPI application serving the web UI and the JSON endpoints.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
