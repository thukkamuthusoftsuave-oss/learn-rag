# Enterprise Policy Assistant — Python FastAPI Backend

This is the production backend for the Enterprise Policy Assistant, integrating all RAG and Agent capabilities into a clean, modern architecture without academic or week-based references.

---

## 1. System Architecture

```
application/backend/
├── core/                        # Central Pydantic settings and environment management
├── ingestion/                   # Structure-aware document parsing & ChromaDB hierarchical indexing
├── retrieval/                   # Hybrid retrieval (Dense BGE + Sparse BM25 + Reciprocal Rank Fusion)
├── agent/                       # Autonomous ReAct agent + high-speed deterministic DAG workflow
├── security/                    # 4-Layer Defense-in-Depth against prompt injections
├── chat/                        # Multi-turn conversational session with query condensation & citations
├── observability/               # Telemetry, trace logging (traces.jsonl), and error taxonomy
├── api/                         # FastAPI router and JSON schemas
└── main.py                      # ASGI application server entrypoint
```

---

## 2. API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | System health check and active configuration |
| `POST` | `/api/chat` | Conversational query with query condensation and source citations |
| `POST` | `/api/agent/run` | Execute autonomous ReAct reasoning agent with step-by-step trajectory |
| `POST` | `/api/workflow/run` | Execute deterministic fixed DAG workflow for entitlement resolution |
| `POST` | `/api/security/scan` | Test input against the 4-layer prompt injection defense |
| `GET` | `/api/traces` | Query execution traces and error taxonomy analytics |
| `POST` | `/api/admin/reindex` | Trigger corpus re-indexing and vector store update |

---

## 3. How to Run

```powershell
# From repository root
python -m uvicorn application.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API documentation will be available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
