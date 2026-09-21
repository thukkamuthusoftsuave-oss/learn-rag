"""Week 3: Dense Vector Indexing with ChromaDB and HuggingFace Embeddings.

Demonstrates building a vector store with BAAI/bge-small-en-v1.5 embeddings
using LlamaIndex and ChromaDB.
"""

from pathlib import Path
from typing import List
import chromadb
from llama_index.core import Document, VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding


def build_vector_index(documents: List[Document], persist_dir: Path, collection_name: str = "policy_vectors") -> VectorStoreIndex:
    """Builds and persists a ChromaDB vector index."""
    embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    # Initialize Chroma client
    persist_dir.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(persist_dir))
    chroma_collection = chroma_client.get_or_create_collection(collection_name)
    
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=False,
    )
    return index
