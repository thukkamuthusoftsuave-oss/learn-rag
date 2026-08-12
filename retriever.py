"""Query-side retrieval and answer generation for the HR-207 RAG pipeline.

Loads the persisted ChromaDB vector store (``./chroma_db``) and docstore
(``./storage``) produced by ``ingest.py``, retrieves with an
``AutoMergingRetriever`` (child hits merged into parent context), and answers
with Gemini under a citation-enforcing prompt.

``query_rag`` is the public entry point. With ``detailed=False`` (default) it
returns just the answer string (this keeps ``api.py`` working unchanged); with
``detailed=True`` it returns the full observability envelope consumed by the
CLI: answer, retrieval parameters, token usage, latency and source chunks.
"""

import os
import time
from datetime import datetime, timezone

import chromadb
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, StorageContext, Settings, PromptTemplate
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.retrievers import AutoMergingRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.gemini import Gemini
from llama_index.vector_stores.chroma import ChromaVectorStore

load_dotenv()

CHROMA_DIR = "./chroma_db"
STORAGE_DIR = "./storage"
COLLECTION_NAME = "hr_policies"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
LLM_MODEL_NAME = "models/gemini-flash-latest"
DEFAULT_TOP_K = 5

# Must stay in sync with the refusal sentence in QA_PROMPT_TEMPLATE below.
REFUSAL_SENTINEL = "I'm sorry, I cannot answer that question based on the provided documents."

QA_PROMPT_TEMPLATE = (
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given the context information and not prior knowledge, answer the query.\n"
    "If the answer is not in the context, say exactly: 'I'm sorry, I cannot answer that question based on the provided documents.'\n"
    "When you provide an answer, you MUST append a citation pointing to the chunk_id and source_file. Format: [[Policy Section]](chunk_id:SOURCE_FILE_NAME)\n"
    "Query: {query_str}\n"
    "Answer: "
)


def _configure_settings() -> None:
    """Configures the global embedding model, LLM and token counter.

    Falls back to ``MockLLM`` when ``GEMINI_API_KEY`` is absent so the query
    path never crashes, but prints a warning because mock answers are not real.
    The ``TokenCountingHandler`` on the callback manager is what makes token
    usage observable per query; counts are tiktoken-based estimates unless the
    LLM response carries provider usage metadata.
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        Settings.llm = Gemini(model_name=LLM_MODEL_NAME, api_key=api_key)
    else:
        print("WARNING: GEMINI_API_KEY not found. Using MockLLM; answers are not real.")
        from llama_index.core.llms import MockLLM
        Settings.llm = MockLLM(max_tokens=256)

    Settings.callback_manager = CallbackManager([TokenCountingHandler()])


def get_query_engine(region_filter: str = None, top_k: int = DEFAULT_TOP_K) -> RetrieverQueryEngine:
    """Builds a query engine over the persisted index.

    Args:
        region_filter: Optional region code (e.g. ``"US"``); when set, an
            exact-match metadata filter restricts retrieval to that region.
        top_k: Number of leaf chunks the base retriever fetches before
            auto-merging.

    Returns:
        A configured ``RetrieverQueryEngine``.
    """
    _configure_settings()

    # Load docstore (needed by AutoMergingRetriever to reach parent nodes).
    storage_context = StorageContext.from_defaults(persist_dir=STORAGE_DIR)

    db = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = db.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    index = VectorStoreIndex.from_vector_store(
        vector_store,
        embed_model=Settings.embed_model,
    )

    from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters

    filters = None
    if region_filter:
        filters = MetadataFilters(filters=[ExactMatchFilter(key="region", value=region_filter)])

    base_retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)

    retriever = AutoMergingRetriever(
        base_retriever,
        storage_context,
        verbose=False,
    )

    return RetrieverQueryEngine.from_args(
        retriever=retriever,
        text_qa_template=PromptTemplate(QA_PROMPT_TEMPLATE),
    )


def _collect_token_usage(response) -> dict:
    """Builds the token-usage block of the observability envelope.

    Args:
        response: The llama-index response object from a completed query.

    Returns:
        Dict with ``prompt``, ``completion`` and ``total`` token counts and a
        ``method`` field that honestly labels the counts as tiktoken estimates
        (the Gemini integration does not reliably surface provider usage).
    """
    for handler in Settings.callback_manager.handlers:
        if isinstance(handler, TokenCountingHandler):
            return {
                "prompt": handler.prompt_llm_token_count,
                "completion": handler.completion_llm_token_count,
                "total": handler.total_llm_token_count,
                "method": "estimated-tiktoken",
            }
    return {"prompt": 0, "completion": 0, "total": 0, "method": "unavailable"}


def _collect_source_chunks(response) -> list:
    """Extracts retrieved chunk references from a query response.

    Args:
        response: The llama-index response object from a completed query.

    Returns:
        List of dicts with ``node_id``, ``score`` and ``source_file`` for each
        retrieved (post-merge) chunk.
    """
    chunks = []
    for node_with_score in getattr(response, "source_nodes", []) or []:
        node = node_with_score.node
        chunks.append({
            "node_id": node.node_id,
            "score": round(node_with_score.score, 4) if node_with_score.score is not None else None,
            "source_file": (node.metadata or {}).get("source_file", "unknown"),
        })
    return chunks


def query_rag(query: str, region: str = None, top_k: int = DEFAULT_TOP_K, detailed: bool = False):
    """Answers a question against the HR-207 corpus.

    Args:
        query: Natural-language question.
        region: Optional region metadata filter (e.g. ``"US"``).
        top_k: Number of leaf chunks retrieved before auto-merging.
        detailed: When False (default) returns only the answer string; when
            True returns the full observability envelope dict.

    Returns:
        The answer string, or (when ``detailed=True``) a dict with keys
        ``answer``, ``is_refusal``, ``region``, ``top_k``,
        ``retrieved_chunks``, ``tokens``, ``latency_ms``, ``llm_model``,
        ``embed_model`` and ``timestamp``.
    """
    engine = get_query_engine(region_filter=region, top_k=top_k)

    for handler in Settings.callback_manager.handlers:
        if isinstance(handler, TokenCountingHandler):
            handler.reset_counts()

    start = time.perf_counter()
    response = engine.query(query)
    latency_ms = round((time.perf_counter() - start) * 1000)

    answer = str(response)
    if not detailed:
        return answer

    llm_model = LLM_MODEL_NAME if os.getenv("GEMINI_API_KEY") else "MockLLM (no GEMINI_API_KEY)"
    return {
        "answer": answer,
        "is_refusal": REFUSAL_SENTINEL in answer,
        "region": region,
        "top_k": top_k,
        "retrieved_chunks": _collect_source_chunks(response),
        "tokens": _collect_token_usage(response),
        "latency_ms": latency_ms,
        "llm_model": llm_model,
        "embed_model": EMBED_MODEL_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
