"""Ingestion pipeline for the HR-207 policy RAG index.

Reads the addenda from ``data/``, parses them into a hierarchical node tree
(parent/child chunks), embeds the leaf nodes with a local HuggingFace model
into ChromaDB, and persists the docstore that ``AutoMergingRetriever`` needs
at query time to merge child hits back into parent context.

Artifacts produced:
- ``./chroma_db``   — ChromaDB persistent store, collection ``hr_policies``
- ``./storage``     — llama-index docstore/index store (all nodes)
"""

import os
import shutil

import chromadb
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext, Settings
from llama_index.core.node_parser import HierarchicalNodeParser, get_leaf_nodes
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

DATA_DIR = "data"
CHROMA_DIR = "./chroma_db"
STORAGE_DIR = "./storage"
COLLECTION_NAME = "hr_policies"
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
CHUNK_SIZES = [512, 128]
CHUNK_OVERLAP = 20


def extract_metadata(filepath: str) -> dict:
    """Extracts policy metadata from an addendum's header lines.

    Args:
        filepath: Path to an ``addendum_*.txt`` file whose first lines follow
            the ``Region:`` / ``Effective Date:`` header contract.

    Returns:
        Metadata dict with ``region``, ``effective_date``, ``policy_id`` and
        ``source_file`` keys; ``"unknown"`` for headers that are not found.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        region = "unknown"
        effective_date = "unknown"
        for line in lines:
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
    """Builds the vector index and docstore from the ``data/`` corpus.

    Args:
        fresh: When True (default), deletes ``./chroma_db`` and ``./storage``
            before rebuilding so repeated ingestion is idempotent and never
            duplicates nodes. When False, nodes are appended to the existing
            stores.

    Returns:
        Summary dict with ``documents``, ``total_nodes`` and ``leaf_nodes``.
    """
    if fresh:
        # Both stores are derived artifacts; wiping them makes re-ingestion
        # reproducible instead of appending duplicate nodes with fresh ids.
        for path in (CHROMA_DIR, STORAGE_DIR):
            shutil.rmtree(path, ignore_errors=True)

    print("Initializing embedding model...")
    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
    Settings.embed_model = embed_model
    Settings.llm = None  # No LLM is needed for ingestion.

    print("Loading documents...")
    reader = SimpleDirectoryReader(
        input_dir=DATA_DIR,
        file_extractor={},
        file_metadata=extract_metadata,
    )
    documents = reader.load_data()

    print("Setting up hierarchical parser...")
    node_parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=CHUNK_SIZES,
        chunk_overlap=CHUNK_OVERLAP,
    )

    nodes = node_parser.get_nodes_from_documents(documents)
    leaf_nodes = get_leaf_nodes(nodes)

    print(f"Created {len(nodes)} total nodes and {len(leaf_nodes)} leaf (child) nodes.")

    print("Connecting to ChromaDB and initializing storage context...")
    db = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = db.get_or_create_collection(COLLECTION_NAME)
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    storage_context.docstore.add_documents(nodes)

    print("Indexing nodes into vector store...")
    # Constructing the index embeds every leaf node into the vector store;
    # the returned object itself is not needed afterwards.
    VectorStoreIndex(
        leaf_nodes,
        storage_context=storage_context,
    )

    # Persist the docstore (important for hierarchical retrieval).
    storage_context.persist(persist_dir=STORAGE_DIR)

    summary = {
        "documents": len(documents),
        "total_nodes": len(nodes),
        "leaf_nodes": len(leaf_nodes),
    }
    print(f"Ingestion complete. ChromaDB at {CHROMA_DIR}, docstore at {STORAGE_DIR}. Summary: {summary}")
    return summary


def main() -> None:
    """Runs a fresh (wipe-and-rebuild) ingestion."""
    run_ingestion(fresh=True)


if __name__ == "__main__":
    main()
