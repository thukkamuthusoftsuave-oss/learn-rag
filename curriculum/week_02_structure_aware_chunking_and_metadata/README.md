# Week 2: Structure-Aware Chunking & Metadata Extraction

## 1. Learning Objectives
- Implement **Structure-Aware Chunking** by splitting documents on semantic section headers (`HR-207 Section X.Y`).
- Extract and attach structured metadata (`region`, `policy_id`, `effective_date`, `section`) to chunks.
- Explore **Hierarchical Parent-Child Parsing** using LlamaIndex's `HierarchicalNodeParser`.
- Benchmark Structure-Aware chunking against Naive chunking (Hit-in-Top-5 jumps from 1/8 to **8/8 (100%)**).
- Quantify the impact of exact **Metadata Filtering** on rank quality.

---

## 2. Theoretical Background

### Why Header Awareness Matters
In regulatory, HR, or compliance documents, policies are written in structured sections (e.g. Section 4.1 Eligibility, Section 4.2 Carry-over Cap). Tables and qualifying conditions must remain intact within a single chunk. Splitting by arbitrary line numbers separates the employee category definitions from the actual day caps.

Structure-aware chunking enforces:
1. **Semantic Atomicity**: Every chunk represents a complete rule or table.
2. **Metadata Inheritance**: Chunks inherit document headers such as Jurisdiction and Effective Date.

### Metadata Filtering
When multiple regions share identical terminology (e.g. probationary employees, carry-over caps), dense embeddings often rank chunks from unintended regions at the top. Adding an exact metadata filter (e.g., `region == "US"`) eliminates 100% of out-of-jurisdiction false positives before scoring.

---

## 3. Code Architecture

- [`structure_chunker.py`](file:///d:/learn-rag/curriculum/week_02_structure_aware_chunking_and_metadata/structure_chunker.py): Regex-driven section parser with automatic document-level metadata extraction.
- [`hierarchical_parser.py`](file:///d:/learn-rag/curriculum/week_02_structure_aware_chunking_and_metadata/hierarchical_parser.py): Parent-child chunking utilizing LlamaIndex for multi-resolution indexing.
- [`run_eval.py`](file:///d:/learn-rag/curriculum/week_02_structure_aware_chunking_and_metadata/run_eval.py): Direct comparison of structure-aware retrieval vs naive baseline, plus metadata filtering demo.

---

## 4. How to Run

```powershell
python curriculum/week_02_structure_aware_chunking_and_metadata/run_eval.py
```
