"""FastAPI application: the chat UI, the admin console, and the JSON API.

Two surfaces, deliberately separate:

**Chat** - what a person asking about their leave entitlement uses.
    ``GET  /``            The chat UI.
    ``GET  /api/health``  Liveness probe plus the active configuration.
    ``POST /api/chat``    Ask a question; returns the full envelope.

**Admin** - what an operator uses: index rebuilds, evaluation runs, traces.
    ``GET  /admin``       The admin console.
    ``/api/admin/*`` and ``/api/evaluation/*``, defined in
    ``policy_rag.api.admin`` and mounted only when ``RAG_ADMIN_ENABLED`` is on.

``POST /chat`` and ``GET /health`` are kept as thin aliases so older clients
keep working.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from policy_rag import __version__, config
from policy_rag.api.schemas import ChatRequest

app = FastAPI(title="HR-207 Policy Assistant", version=__version__)

if config.ADMIN_ENABLED:
    from policy_rag.api.admin import router as admin_router

    app.include_router(admin_router)


def _fail(exc: Exception) -> HTTPException:
    """Wraps an internal error as a 500 with the exception text preserved."""
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def _serve_page(filename: str) -> HTMLResponse:
    """Serves one of the static pages.

    Args:
        filename: File inside ``config.STATIC_DIR``.

    Returns:
        The page as HTML.

    Raises:
        HTTPException: 404 when the file is missing.
    """
    page = config.STATIC_DIR / filename
    if not page.exists():
        raise HTTPException(status_code=404, detail=f"Page not found at {page}")
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Serves the chat UI.

    The chat page is the assistant and nothing else. Benchmarks, the
    answer-quality run and the trace log live in the admin console, reachable
    from the gear icon, not as screens a person chatting has to walk past.
    """
    return _serve_page("index.html")


@app.get("/admin", response_class=HTMLResponse)
def serve_admin():
    """Serves the admin console.

    Raises:
        HTTPException: 404 when admin is disabled, so a disabled deployment
            does not advertise a console it will not serve.
    """
    if not config.ADMIN_ENABLED:
        raise HTTPException(status_code=404, detail="Admin console is disabled (RAG_ADMIN_ENABLED).")
    return _serve_page("admin.html")


@app.get("/api/health")
def health():
    """Reports liveness and the settings the server is running with."""
    from policy_rag import vector_store
    from policy_rag.retrieval import engine

    return {
        "status": "healthy",
        "version": __version__,
        "llm": engine.active_llm_name(),
        "embed_model": config.EMBED_MODEL_NAME,
        "vector_store": vector_store.describe(),
        "hybrid_default": config.DEFAULT_HYBRID,
        "top_k_default": config.DEFAULT_TOP_K,
        "index_ready": vector_store.is_ready(),
        "admin_enabled": config.ADMIN_ENABLED,
        "regions": config.REGIONS,
    }


@app.post("/api/chat")
def chat(request: ChatRequest):
    """Answers a question and records a trace.

    Args:
        request: Question, retrieval settings and the conversation so far.

    Returns:
        The answer envelope, including retrieved chunks, token usage and latency.
    """
    from policy_rag.chat.service import answer

    try:
        return answer(
            request.query,
            region=request.region,
            top_k=request.top_k,
            hybrid=request.hybrid,
            history=[{"role": turn.role, "content": turn.content} for turn in request.history],
            session_id=request.session_id,
        )
    except Exception as exc:
        raise _fail(exc)


# --- Legacy aliases --------------------------------------------------------

@app.get("/health")
def legacy_health():
    """Alias for ``GET /api/health``."""
    return health()


@app.post("/chat")
def legacy_chat(request: ChatRequest):
    """Alias for ``POST /api/chat`` that returns only the answer string."""
    return {"answer": chat(request)["answer"]}


def run(host: str = None, port: int = None, reload: bool = False) -> None:
    """Starts the development server.

    Args:
        host: Interface to bind. Defaults to ``config.API_HOST``.
        port: Port to bind. Defaults to ``config.API_PORT``.
        reload: Enable uvicorn's auto-reload.
    """
    import uvicorn

    uvicorn.run(
        "policy_rag.api.app:app" if reload else app,
        host=host or config.API_HOST,
        port=port or config.API_PORT,
        reload=reload,
    )


if __name__ == "__main__":
    run()
