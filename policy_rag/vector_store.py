"""Where the embeddings live.

Both the indexer and the retriever need the same Chroma collection, so the
choice of backend is made here once rather than in each of them:

``local`` (default)
    A ``chroma_db/`` directory next to the project. No account, no network,
    nothing to expire - the right default for development and for anyone who
    just cloned the repo.
``cloud``
    A hosted Chroma Cloud database. Set ``RAG_VECTOR_BACKEND=cloud`` plus
    ``CHROMA_API_KEY``, ``CHROMA_TENANT`` and ``CHROMA_DATABASE``.

Switching backends is an ingestion-time decision: the embeddings live wherever
they were written, so point at the backend you want and re-run ``ingest``.

What does *not* move is the docstore in ``storage/``. Auto-merging retrieval
reads parent sections from it and BM25 builds its keyword index from its leaf
nodes, so it is required in both modes. It is a few hundred kilobytes and is
rebuilt by ``ingest``, which is why it stays on disk rather than pulling in a
second hosted service.
"""

import shutil

import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore

from policy_rag import config

BACKEND_LOCAL = "local"
BACKEND_CLOUD = "cloud"
BACKENDS = (BACKEND_LOCAL, BACKEND_CLOUD)

# Credentials Chroma Cloud needs, mapped to the config attribute holding each.
_CLOUD_CREDENTIALS = {
    "CHROMA_API_KEY": "CHROMA_API_KEY",
    "CHROMA_TENANT": "CHROMA_TENANT",
    "CHROMA_DATABASE": "CHROMA_DATABASE",
}


def backend() -> str:
    """Returns the configured backend name.

    Returns:
        ``"local"`` or ``"cloud"``.

    Raises:
        ValueError: If ``RAG_VECTOR_BACKEND`` names an unknown backend.
    """
    name = (config.VECTOR_BACKEND or BACKEND_LOCAL).strip().lower()
    if name not in BACKENDS:
        raise ValueError(
            f"RAG_VECTOR_BACKEND={name!r} is not a known backend. "
            f"Use one of: {', '.join(BACKENDS)}."
        )
    return name


def missing_cloud_credentials() -> list:
    """Returns the names of the cloud settings that are not set."""
    return [env for env, attr in _CLOUD_CREDENTIALS.items() if not getattr(config, attr, "")]


def describe() -> str:
    """Returns a one-line description of the active backend, for logs and health."""
    if backend() == BACKEND_CLOUD:
        return f"Chroma Cloud ({config.CHROMA_TENANT or '?'}/{config.CHROMA_DATABASE or '?'})"
    return f"local ({config.CHROMA_DIR})"


def get_client():
    """Opens a Chroma client for the configured backend.

    Returns:
        A ``chromadb`` client.

    Raises:
        RuntimeError: If the cloud backend is selected but credentials are missing.
            Failing here is deliberate: silently falling back to the local store
            would write embeddings somewhere the user did not ask for and make
            the two backends look interchangeable when they are not.
    """
    if backend() == BACKEND_CLOUD:
        missing = missing_cloud_credentials()
        if missing:
            raise RuntimeError(
                "RAG_VECTOR_BACKEND=cloud but these are not set: "
                f"{', '.join(missing)}. Add them to .env, or set "
                "RAG_VECTOR_BACKEND=local to use the on-disk store."
            )
        return chromadb.CloudClient(
            tenant=config.CHROMA_TENANT,
            database=config.CHROMA_DATABASE,
            api_key=config.CHROMA_API_KEY,
        )
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR))


def get_collection(client=None):
    """Returns the policy collection, creating it if it does not exist.

    Args:
        client: An existing client to reuse. One is opened when omitted.

    Returns:
        The Chroma collection named by ``config.COLLECTION_NAME``.
    """
    client = client or get_client()
    return client.get_or_create_collection(config.COLLECTION_NAME)


def get_vector_store(client=None) -> ChromaVectorStore:
    """Returns the llama-index vector store wrapping the policy collection.

    Args:
        client: An existing client to reuse. One is opened when omitted.

    Returns:
        A ``ChromaVectorStore`` bound to the configured backend.
    """
    return ChromaVectorStore(chroma_collection=get_collection(client))


def reset() -> None:
    """Removes the existing embeddings so ingestion starts from nothing.

    Locally this deletes the store directory; on the cloud it drops the
    collection, since there is no directory to remove. Either way the point is
    the same: re-ingesting must not leave last run's nodes behind.
    """
    if backend() == BACKEND_CLOUD:
        client = get_client()
        try:
            client.delete_collection(config.COLLECTION_NAME)
        except Exception:
            # Nothing to drop on a first run - not an error worth failing on.
            pass
        return
    shutil.rmtree(config.CHROMA_DIR, ignore_errors=True)


def is_ready() -> bool:
    """Reports whether the assistant has everything it needs to answer.

    Both halves are checked: the embeddings (wherever they live) and the local
    docstore that auto-merging and BM25 read from.

    Returns:
        True when the index looks usable. For the cloud backend this checks
        that credentials are configured rather than making a network call, so
        it stays cheap enough for a liveness probe.
    """
    docstore_ready = config.STORAGE_DIR.exists()
    if backend() == BACKEND_CLOUD:
        return docstore_ready and not missing_cloud_credentials()
    return docstore_ready and config.CHROMA_DIR.exists()
