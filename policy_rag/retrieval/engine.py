"""Retriever and query-engine construction.

Everything the assistant needs to *find* policy text lives here; generating the
answer and recording the trace is ``policy_rag.chat.service``'s job.

Two retrieval modes are supported and both end in an ``AutoMergingRetriever``
so child-chunk hits are returned with their parent section's full context:

- **vector** - the biencoder alone.
- **hybrid** (default, see ``config.DEFAULT_HYBRID``) - BM25 keyword search
  fused with the vector retriever by Reciprocal Rank Fusion, so exact terms
  the biencoder blurs together (region codes, service thresholds such as
  "5 years" versus "10 years") get a literal match as well as a semantic one.
  Fusion is a trade, not a free win: a document BM25 does not rank at all can
  be pushed down by it, which is what the retrieval benchmark measures.

Built engines are cached per ``(region, top_k, hybrid)`` because loading the
docstore and the 300 MB embedding model costs far more than answering a
question. ``reset_engine_cache`` clears the cache after re-ingestion.
"""

import functools

from llama_index.core import PromptTemplate, Settings, StorageContext, VectorStoreIndex
from llama_index.core.base.llms.types import LLMMetadata
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
from llama_index.core.node_parser import get_leaf_nodes
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import AutoMergingRetriever, QueryFusionRetriever
from llama_index.core.vector_stores import ExactMatchFilter, MetadataFilters
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.openai import OpenAI

from policy_rag import config
from policy_rag import vector_store as vector_store_backend

# The BGE model takes ~100 s to load the first time; a long-running server
# process must pay that once, not once per request.
_EMBED_MODEL = None

# One long-lived token counter, reset per query. It cannot be recreated per
# query: cached engines hold a reference to the callback manager they were
# built with, and a replacement would never receive their events.
_TOKEN_COUNTER = None


class OpenRouterLLM(OpenAI):
    """OpenAI client pointed at OpenRouter, with explicit generic-model metadata.

    LlamaIndex's ordinary OpenAI adapter infers chat capability and context size
    from a fixed list of OpenAI model names. OpenRouter model slugs such as
    ``google/gemini-2.5-flash-lite`` are intentionally not on that list, even
    though OpenRouter provides the standard chat-completions endpoint. This
    small adapter keeps the OpenAI client's request format while supplying the
    metadata the query engine needs for any OpenRouter chat model.
    """

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=config.LLM_CONTEXT_WINDOW,
            num_output=self.max_tokens or -1,
            is_chat_model=True,
            is_function_calling_model=False,
            model_name=self.model,
        )


def configure_settings() -> None:
    """Configures the global embedding model, LLM and token counter.

    Falls back to ``MockLLM`` when ``OPENROUTER_API_KEY`` is absent, which keeps
    retrieval-only work (indexing, the retrieval benchmark) runnable without
    a key.
    """
    global _EMBED_MODEL, _TOKEN_COUNTER
    if _EMBED_MODEL is None:
        _EMBED_MODEL = HuggingFaceEmbedding(model_name=config.EMBED_MODEL_NAME)
    Settings.embed_model = _EMBED_MODEL

    api_key = config.openrouter_api_key()
    if api_key:
        # OpenRouter implements OpenAI's chat-completions API. OpenRouterLLM
        # keeps that client while supporting generic ``provider/model`` slugs.
        Settings.llm = OpenRouterLLM(
            model=config.LLM_MODEL_NAME,
            api_base=config.OPENROUTER_BASE_URL,
            api_key=api_key,
            context_window=config.LLM_CONTEXT_WINDOW,
            max_tokens=config.LLM_MAX_TOKENS,
            is_chat_model=True,
            is_function_calling_model=False,
        )
    else:
        print("WARNING: OPENROUTER_API_KEY not found. Using MockLLM; answers are not real.")
        from llama_index.core.llms import MockLLM
        Settings.llm = MockLLM(max_tokens=256)

    if _TOKEN_COUNTER is None:
        _TOKEN_COUNTER = TokenCountingHandler()
        Settings.callback_manager = CallbackManager([_TOKEN_COUNTER])


def token_counter() -> TokenCountingHandler:
    """Returns the process-wide token counter, configuring settings if needed."""
    if _TOKEN_COUNTER is None:
        configure_settings()
    return _TOKEN_COUNTER


def llm_is_mocked() -> bool:
    """Returns True when no API key is configured and answers are not real."""
    return not config.openrouter_api_key()


def active_llm_name() -> str:
    """Returns the LLM identifier recorded on traces and answer envelopes."""
    return config.LLM_MODEL_NAME if config.openrouter_api_key() else "MockLLM (no OPENROUTER_API_KEY)"


def _load_storage_context() -> StorageContext:
    """Loads the persisted docstore that auto-merging retrieval depends on."""
    return StorageContext.from_defaults(persist_dir=str(config.STORAGE_DIR))


def _load_index() -> VectorStoreIndex:
    """Opens the embedded collection as a vector index.

    Where that collection lives - a local directory or Chroma Cloud - is
    ``policy_rag.vector_store``'s decision, not this module's.
    """
    return VectorStoreIndex.from_vector_store(
        vector_store_backend.get_vector_store(),
        embed_model=Settings.embed_model,
    )


def _build_bm25_retriever(storage_context: StorageContext, region: str, top_k: int):
    """Builds a BM25 retriever over the same leaf nodes the vector store holds.

    Args:
        storage_context: Loaded docstore containing every parsed node.
        region: Optional region code. BM25 has no native metadata filter, so
            the vector retriever's ``ExactMatchFilter`` is mirrored in Python.
        top_k: Number of chunks BM25 contributes to the fusion.

    Returns:
        A configured ``BM25Retriever``.
    """
    from llama_index.retrievers.bm25 import BM25Retriever

    leaf_nodes = get_leaf_nodes(list(storage_context.docstore.docs.values()))
    if region:
        leaf_nodes = [n for n in leaf_nodes if (n.metadata or {}).get("region") == region]
    return BM25Retriever.from_defaults(nodes=leaf_nodes, similarity_top_k=top_k)


def build_retriever(region: str = None, top_k: int = None, hybrid: bool = None):
    """Builds the retriever used for a query, without the generation step.

    Used directly by the retrieval benchmark, which measures ranking quality
    and must not spend LLM calls.

    Args:
        region: Optional region code (e.g. ``"US"``) applied as an exact-match
            metadata filter.
        top_k: Leaf chunks fetched before auto-merging. Defaults to
            ``config.DEFAULT_TOP_K``.
        hybrid: Whether to fuse BM25 with vector search. Defaults to
            ``config.DEFAULT_HYBRID``.

    Returns:
        An ``AutoMergingRetriever`` wrapping the configured base retriever.
    """
    top_k = config.DEFAULT_TOP_K if top_k is None else top_k
    hybrid = config.DEFAULT_HYBRID if hybrid is None else hybrid

    configure_settings()
    storage_context = _load_storage_context()
    index = _load_index()

    filters = None
    if region:
        filters = MetadataFilters(filters=[ExactMatchFilter(key="region", value=region)])
    vector_retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)

    if hybrid:
        # Reciprocal Rank Fusion: each list contributes 1/(k + rank).
        # num_queries=1 stops QueryFusionRetriever from spending an LLM call on
        # generated query variations - the fusion here is BM25 + vector only.
        base_retriever = QueryFusionRetriever(
            retrievers=[
                vector_retriever,
                _build_bm25_retriever(storage_context, region, top_k),
            ],
            similarity_top_k=top_k,
            mode="reciprocal_rerank",
            num_queries=1,
        )
    else:
        base_retriever = vector_retriever

    return AutoMergingRetriever(base_retriever, storage_context, verbose=False)


@functools.lru_cache(maxsize=32)
def _cached_query_engine(region: str, top_k: int, hybrid: bool) -> RetrieverQueryEngine:
    """Builds (and memoises) one query engine per retrieval configuration."""
    return RetrieverQueryEngine.from_args(
        retriever=build_retriever(region=region, top_k=top_k, hybrid=hybrid),
        text_qa_template=PromptTemplate(config.QA_PROMPT_TEMPLATE),
    )


def build_query_engine(region: str = None, top_k: int = None, hybrid: bool = None) -> RetrieverQueryEngine:
    """Returns a query engine for the given retrieval configuration.

    Args:
        region: Optional region metadata filter.
        top_k: Leaf chunks fetched before auto-merging.
        hybrid: Whether to fuse BM25 with vector search.

    Returns:
        A cached ``RetrieverQueryEngine`` bound to the citation-enforcing prompt.
    """
    top_k = config.DEFAULT_TOP_K if top_k is None else top_k
    hybrid = config.DEFAULT_HYBRID if hybrid is None else hybrid
    configure_settings()
    return _cached_query_engine(region, top_k, hybrid)


def reset_engine_cache() -> None:
    """Drops every cached query engine (call after rebuilding the index)."""
    _cached_query_engine.cache_clear()
