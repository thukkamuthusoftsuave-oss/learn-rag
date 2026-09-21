"""Main FastAPI Application Entry Point with Server Lifespan Pre-Warming."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from application.backend.api.routes import api_router
from application.backend.retrieval.engine import hybrid_retriever
from application.backend.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Server lifespan: Pre-warms the ChromaDB collection and BM25 token tables on boot."""
    print(f"[*] Starting {settings.app_name} v{settings.version}...")
    print("[*] Pre-warming ChromaDB HNSW vector index & BM25 sparse matrices...")
    try:
        hybrid_retriever.initialize()
        print(f"[+] Retrieval engine warmed up: {len(hybrid_retriever.chunks)} chunks ready.")
    except Exception as e:
        print(f"[-] Pre-warming notice: {e}")
    yield
    print("[*] Shutting down Policy Assistant backend.")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="Enterprise Policy Assistant Backend: Native ChromaDB HNSW Hybrid RAG, Autonomous ReAct Agent, 4-Layer Defense, and Non-Blocking Telemetry.",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(api_router)


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name} API",
        "version": settings.version,
        "docs": "/docs",
        "health": "/api/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("application.backend.main:app", host="0.0.0.0", port=8000, reload=True)
