"""High-Performance Document Ingestion & ChromaDB HNSW Indexing Pipeline."""

import re
from pathlib import Path
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings as ChromaSettings
from llama_index.core import Document
from application.backend.core.config import settings


def parse_policy_document(file_path: Path) -> List[Document]:
    """Parses regional policy text into cohesive semantic section documents with rich metadata."""
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    region_match = re.search(r"Region:\s*([A-Za-z]+)", text)
    effective_match = re.search(r"Effective Date:\s*([0-9\-]+)", text)
    region = region_match.group(1).strip() if region_match else "unknown"
    effective_date = effective_match.group(1).strip() if effective_match else "unknown"

    section_pattern = re.compile(r"(HR-207\s+Section\s+\d+\.\d+[^\n]*)", re.IGNORECASE)
    parts = section_pattern.split(text)

    docs = []
    # Preamble header
    if parts and parts[0].strip():
        docs.append(Document(
            text=parts[0].strip(),
            doc_id=f"{region}_header",
            metadata={
                "policy_id": "HR-207",
                "region": region,
                "effective_date": effective_date,
                "section": "Header",
                "filename": file_path.name,
            }
        ))

    # Sections
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
        sec_num_match = re.search(r"Section\s+(\d+\.\d+)", header)
        sec_num = sec_num_match.group(1) if sec_num_match else "unknown"

        docs.append(Document(
            text=f"{header}\n{body}".strip(),
            doc_id=f"{region}_sec_{sec_num.replace('.', '_')}",
            metadata={
                "policy_id": "HR-207",
                "region": region,
                "effective_date": effective_date,
                "section": f"HR-207 Section {sec_num}",
                "filename": file_path.name,
            }
        ))

    return docs


def load_all_policy_documents(corpus_dir: Path = None) -> List[Document]:
    """Loads all policy addenda files."""
    corpus_path = corpus_dir or settings.corpus_dir
    if not corpus_path.exists():
        # Fallback to alternate path if necessary
        corpus_path = settings.base_dir / "data_and_benchmarks" / "files_to_learn" / "synthetic_corpus"

    documents = []
    for f in sorted(corpus_path.glob("addendum_*.txt")):
        docs = parse_policy_document(f)
        documents.extend(docs)
    return documents


def get_chroma_client():
    """Initializes and returns a persistent ChromaDB client."""
    settings.chroma_db_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(settings.chroma_db_dir),
        settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True)
    )


def run_ingestion_pipeline(fresh: bool = True) -> Dict[str, Any]:
    """Ingests, chunks, and persists documents directly into the persistent ChromaDB collection."""
    documents = load_all_policy_documents()
    if not documents:
        raise RuntimeError("No policy documents found to index.")

    client = get_chroma_client()
    collection_name = "policy_rag_production"

    if fresh:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    ids = [d.doc_id for d in documents]
    texts = [d.text for d in documents]
    metadatas = [d.metadata for d in documents]

    # Batch add into ChromaDB collection with automatic default/configured embeddings
    collection.upsert(
        ids=ids,
        documents=texts,
        metadatas=metadatas
    )

    return {
        "status": "success",
        "documents_count": len(documents),
        "collection_name": collection_name,
        "indexed_chunks": collection.count(),
        "storage_path": str(settings.chroma_db_dir)
    }
