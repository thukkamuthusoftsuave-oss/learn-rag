"""Builds the search index the assistant answers from.

Reads the addenda in ``config.DATA_DIR``, parses them into a hierarchical node
tree (parent sections, child chunks), embeds the leaf nodes into the configured
vector store, and persists the docstore that ``AutoMergingRetriever`` needs at
query time to merge child hits back into their parent's context.

Artifacts produced (both derived — always reproducible from ``data/``):

- the vector store  — embeddings for every leaf node, written to whichever
                      backend ``policy_rag.vector_store`` resolves (a local
                      ``chroma_db/`` directory by default, or Chroma Cloud)
- ``config.STORAGE_DIR`` — llama-index docstore / index store (all nodes), always
                      local: auto-merging and BM25 both read from it
"""

import os
import shutil

from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from policy_rag import config
from policy_rag import vector_store as vector_store_backend


def extract_metadata(filepath: str) -> dict:
    """Extracts policy metadata from an addendum's header lines.

    Args:
        filepath: Path to an ``addendum_*.txt`` file whose first lines follow
            the ``Region:`` / ``Effective Date:`` header contract.

    Returns:
        Metadata dict with ``region``, ``effective_date``, ``policy_id`` and
        ``source_file`` keys; ``"unknown"`` for headers that are not found.
    """
    region = "unknown"
    effective_date = "unknown"
    with open(filepath, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("Region:"):
                region = line.split(":", 1)[1].strip()
            elif line.startswith("Effective Date:"):
                effective_date = line.split(":", 1)[1].strip()
    return {
        "region": region,
        "effective_date": effective_date,
        "policy_id": "HR-207",
        "source_file": os.path.basename(filepath),
    }


def run_ingestion(fresh: bool = True) -> dict:
    """Builds the vector index and docstore from the corpus.

    Args:
        fresh: When True (default), clears the existing embeddings and docstore
            before rebuilding so repeated ingestion is idempotent and never
            duplicates nodes. When False, nodes are appended to the existing
            stores.

    Returns:
        Summary dict with ``documents``, ``total_nodes`` and ``leaf_nodes``.
    """
    print(f"Vector store: {vector_store_backend.describe()}")

    if fresh:
        # Both stores are derived artifacts; wiping them makes re-ingestion
        # reproducible instead of appending duplicate nodes with fresh ids.
        vector_store_backend.reset()
        shutil.rmtree(config.STORAGE_DIR, ignore_errors=True)

    print("Initializing embedding model...")
    Settings.embed_model = HuggingFaceEmbedding(model_name=config.EMBED_MODEL_NAME)
    Settings.llm = None  # No LLM is needed for ingestion.

    print("Loading documents...")
    reader = SimpleDirectoryReader(
        input_dir=str(config.DATA_DIR),
        file_extractor={},
        file_metadata=extract_metadata,
    )
    documents = reader.load_data()

    print("Setting up hierarchical parser...")
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=config.CHUNK_SIZES,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)
    print(f"Created {len(nodes)} total nodes and {len(leaf_nodes)} leaf (child) nodes.")

    print("Connecting to the vector store and initializing storage context...")
    storage_context = StorageContext.from_defaults(
        vector_store=vector_store_backend.get_vector_store()
    )
    storage_context.docstore.add_documents(nodes)

    print("Indexing nodes into vector store...")
    # Constructing the index embeds every leaf node into the vector store;
    # the returned object itself is not needed afterwards.
    VectorStoreIndex(leaf_nodes, storage_context=storage_context)

    # Persisting the docstore is what makes auto-merging retrieval possible.
    storage_context.persist(persist_dir=str(config.STORAGE_DIR))

    # Any query engine cached in this process now points at a stale index.
    from policy_rag.retrieval.engine import reset_engine_cache
    reset_engine_cache()

    summary = {
        "documents": len(documents),
        "total_nodes": len(nodes),
        "leaf_nodes": len(leaf_nodes),
    }
    print(
        f"Ingestion complete. Embeddings in {vector_store_backend.describe()}, "
        f"docstore at {config.STORAGE_DIR}. Summary: {summary}"
    )
    return summary


def main() -> None:
    """Runs a fresh (wipe-and-rebuild) ingestion."""
    run_ingestion(fresh=True)


if __name__ == "__main__":
    main()
