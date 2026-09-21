# Enterprise Policy Assistant (Production Application)

This directory contains the production-grade **Enterprise Policy Assistant** built with **Next.js** and **Python FastAPI**. It seamlessly integrates all concepts mastered throughout the curriculum into a cohesive, production-ready system with **zero academic or week-based references**.

---

## Directory Architecture

```
application/
├── backend/                             # Python FastAPI Production Service
│   ├── core/                            # Configuration, settings, and environment management
│   ├── ingestion/                       # Structure-aware hierarchical parsing & ChromaDB vector store
│   ├── retrieval/                       # Hybrid retrieval (Dense BGE + Sparse BM25 + Reciprocal Rank Fusion)
│   ├── agent/                           # ReAct autonomous reasoning engine & deterministic DAG workflow
│   ├── security/                        # 4-layer defense-in-depth against prompt injection
│   ├── chat/                            # Multi-turn conversation, query condensation & citations
│   ├── observability/                   # Telemetry, trace logging (traces.jsonl) & error taxonomy
│   ├── api/                             # FastAPI routes & Pydantic schemas
│   ├── main.py                          # ASGI application entrypoint
│   └── requirements.txt                 # Backend dependencies
│
└── frontend/                            # Next.js Modern React Application
    ├── src/
    │   ├── app/                         # App Router (unified tabs: Chat, Agent, Security, Analytics)
    │   └── styles/                      # Glassmorphism dark mode design tokens
    ├── package.json
    └── tsconfig.json
```

---

## Running the Application

### 1. Launch Backend (Python FastAPI)
```powershell
# From the repository root
python -m uvicorn application.backend.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation: `http://localhost:8000/docs`

### 2. Launch Frontend (Next.js)
```powershell
cd application/frontend
npm run dev
```
Web Application: `http://localhost:3000`
