"""Operator endpoints: system status, index building and evaluation runs.

These sit behind the admin console at ``/admin``, deliberately apart from the
chat UI: rebuilding an index or spending twenty LLM calls is not something a
person asking about their leave entitlement should be able to trip over.

**These endpoints are not authenticated.** Rebuilding the index and clearing
the trace log are destructive, so both require an explicit ``confirm`` flag,
and the whole router can be switched off with ``RAG_ADMIN_ENABLED=false``
before putting this anywhere but localhost.

Long operations run synchronously - an ingest takes minutes on a cold model
cache, and an answer-quality run takes longer still. The console warns before
starting one.
"""

import json

from fastapi import APIRouter, HTTPException

from policy_rag import __version__, config
from policy_rag.api.schemas import (
    IngestRequest,
    QualityEvalRequest,
    RetrievalEvalRequest,
    TraceClearRequest,
)

router = APIRouter(tags=["admin"])


def _fail(exc: Exception) -> HTTPException:
    """Wraps an internal error as a 500 with the exception text preserved."""
    return HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")


def _require_confirmation(confirmed: bool, action: str) -> None:
    """Rejects a destructive call that did not explicitly opt in.

    Args:
        confirmed: The request's ``confirm`` flag.
        action: What would have happened, quoted back in the error.

    Raises:
        HTTPException: 400 when confirmation is missing.
    """
    if not confirmed:
        raise HTTPException(
            status_code=400,
            detail=f'This {action} is destructive. Send {{"confirm": true}} to proceed.',
        )


# --- Status ----------------------------------------------------------------

def _docstore_node_count() -> int:
    """Returns how many nodes the persisted docstore holds, or -1 if unknown.

    Reads the JSON directly rather than constructing a StorageContext, so the
    status call stays cheap and does not drag in llama-index.
    """
    path = config.STORAGE_DIR / "docstore.json"
    if not path.exists():
        return -1
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return len(data.get("docstore/data", {}))
    except (json.JSONDecodeError, OSError):
        return -1


def _vector_count() -> int:
    """Returns the number of embedded chunks, or -1 when it cannot be read."""
    from policy_rag import vector_store

    try:
        return vector_store.get_collection().count()
    except Exception:
        # A misconfigured or unreachable backend must not break the status page;
        # is_ready and the warnings below already say something is wrong.
        return -1


@router.get("/api/admin/status")
def status():
    """Reports everything an operator needs before touching anything.

    Returns:
        Dict describing the vector store, docstore, corpus, models, trace log
        and any warnings worth acting on. Credentials are reported as
        configured or not - never echoed back.
    """
    from policy_rag import vector_store
    from policy_rag.observability.traces import default_store
    from policy_rag.retrieval import engine

    try:
        traces = default_store.read()
        by_source = {}
        for trace in traces:
            by_source[trace["source"]] = by_source.get(trace["source"], 0) + 1

        corpus_files = sorted(p.name for p in config.DATA_DIR.glob("*.txt")) \
            if config.DATA_DIR.exists() else []

        backend = vector_store.backend()
        missing_credentials = (
            vector_store.missing_cloud_credentials()
            if backend == vector_store.BACKEND_CLOUD else []
        )

        warnings = []
        if not config.openrouter_api_key():
            warnings.append("No OPENROUTER_API_KEY: answers come from a mock LLM and are not real.")
        if missing_credentials:
            warnings.append(
                "Cloud backend selected but missing: " + ", ".join(missing_credentials)
            )
        if not vector_store.is_ready():
            warnings.append("Index is not ready. Run a rebuild before asking questions.")
        if not corpus_files:
            warnings.append("No corpus files. Regenerate the corpus first.")

        return {
            "version": __version__,
            "vector_store": {
                "backend": backend,
                "description": vector_store.describe(),
                "collection": config.COLLECTION_NAME,
                "location": str(config.CHROMA_DIR) if backend == "local" else "Chroma Cloud",
                "tenant": config.CHROMA_TENANT or None,
                "database": config.CHROMA_DATABASE or None,
                "credentials_configured": not missing_credentials,
                "missing_credentials": missing_credentials,
                "embedded_chunks": _vector_count(),
                "ready": vector_store.is_ready(),
            },
            "docstore": {
                "path": str(config.STORAGE_DIR),
                "exists": config.STORAGE_DIR.exists(),
                "nodes": _docstore_node_count(),
            },
            "corpus": {
                "path": str(config.DATA_DIR),
                "files": corpus_files,
                "count": len(corpus_files),
            },
            "models": {
                "llm": engine.active_llm_name(),
                "embed": config.EMBED_MODEL_NAME,
                "mocked": engine.llm_is_mocked(),
            },
            "retrieval": {
                "hybrid_default": config.DEFAULT_HYBRID,
                "top_k_default": config.DEFAULT_TOP_K,
                "regions": config.REGIONS,
            },
            "traces": {
                "path": str(config.TRACE_FILE),
                "total": len(traces),
                "by_source": by_source,
                "latest_evaluation_run": default_store.latest_run_id("evaluation"),
            },
            "evaluation": {
                "pause_seconds": config.EVAL_PAUSE_SECONDS,
                "retries": config.EVAL_RETRIES,
            },
            "warnings": warnings,
        }
    except Exception as exc:
        raise _fail(exc)


# --- Index management ------------------------------------------------------

@router.post("/api/admin/corpus")
def regenerate_corpus():
    """Rewrites the corpus files from the generator.

    Returns:
        Dict with the files written.
    """
    from policy_rag.corpus.generator import write_corpus

    try:
        written = write_corpus()
        return {"written": [str(p) for p in written], "count": len(written)}
    except Exception as exc:
        raise _fail(exc)


@router.post("/api/admin/ingest")
def rebuild_index(request: IngestRequest):
    """Rebuilds the vector index and docstore from the corpus.

    Slow: the embedding model has to load, and every leaf node is embedded.
    A fresh rebuild deletes the existing embeddings first, which is why it
    needs confirmation.

    Args:
        request: ``keep`` to append instead of rebuilding, ``confirm`` to
            acknowledge that a rebuild discards the current index.

    Returns:
        The ingestion summary plus which backend was written to.
    """
    from policy_rag import vector_store
    from policy_rag.indexing import run_ingestion

    if not request.keep:
        _require_confirmation(request.confirm, "index rebuild")
    try:
        summary = run_ingestion(fresh=not request.keep)
        return {
            "summary": summary,
            "vector_store": vector_store.describe(),
            "mode": "append" if request.keep else "rebuild",
        }
    except Exception as exc:
        raise _fail(exc)


# --- Evaluation ------------------------------------------------------------

@router.post("/api/evaluation/retrieval")
def run_retrieval_benchmark(request: RetrievalEvalRequest = None):
    """Runs the retrieval benchmark: vector-only versus hybrid.

    Makes no LLM calls. The first request pays the embedding-model load;
    later ones reuse the cache.
    """
    from policy_rag.evaluation.retrieval import evaluate_retrieval

    request = request or RetrievalEvalRequest()
    try:
        return evaluate_retrieval(top_k=request.top_k)
    except Exception as exc:
        raise _fail(exc)


@router.post("/api/evaluation/chunking")
def run_chunking_evaluation():
    """Runs the chunking bake-off: naive versus structure-aware.

    Reads the corpus straight from disk, so it works before anything is
    ingested and makes no LLM calls.
    """
    from policy_rag.evaluation.chunking import evaluate_chunking

    try:
        return evaluate_chunking()
    except Exception as exc:
        raise _fail(exc)


@router.post("/api/evaluation/smoke")
def run_smoke_checks_endpoint():
    """Runs the three end-to-end checks: refusal, region filter, edge case.

    Spends three LLM calls.
    """
    from policy_rag.evaluation.smoke import run_smoke_checks

    try:
        results = run_smoke_checks(verbose=False)
        return {
            "results": results,
            "passed": sum(1 for r in results if r["passed"]),
            "total": len(results),
        }
    except Exception as exc:
        raise _fail(exc)


@router.post("/api/evaluation/quality")
def run_quality_evaluation(request: QualityEvalRequest = None):
    """Runs the answer-quality suite through the live assistant.

    One LLM call per question, paced to stay under the provider's rate limit,
    so expect several minutes. Traces are written as they complete, which
    means a run interrupted halfway is still readable afterwards.
    """
    from policy_rag.evaluation.quality import evaluate_answer_quality

    request = request or QualityEvalRequest()
    try:
        return evaluate_answer_quality(
            region_override=request.region,
            hybrid=request.hybrid,
            top_k=request.top_k,
            progress=False,
        )
    except Exception as exc:
        raise _fail(exc)


@router.get("/api/evaluation/quality")
def latest_quality_report(run_id: str = None):
    """Rebuilds the answer-quality report from stored traces, with no LLM calls.

    Args:
        run_id: Specific run to load. Defaults to the most recent one.

    Returns:
        The report dict.

    Raises:
        HTTPException: 404 when no evaluation run has been recorded yet.
    """
    from policy_rag.evaluation.quality import load_latest_report

    try:
        report = load_latest_report(run_id=run_id)
    except Exception as exc:
        raise _fail(exc)
    if not report["traces"]:
        raise HTTPException(
            status_code=404,
            detail="No evaluation traces stored yet. Run the answer-quality suite first.",
        )
    return report


# --- Traces ----------------------------------------------------------------

@router.get("/api/traces")
def list_traces(limit: int = 50, source: str = None):
    """Returns recent traces with their taxonomy.

    Args:
        limit: Maximum number of traces, most recent kept.
        source: Optional filter - ``"chat"`` for live traffic, ``"evaluation"``
            for suite runs.

    Returns:
        Dict with ``traces``, ``taxonomy`` and ``summary``.
    """
    from policy_rag.observability import taxonomy
    from policy_rag.observability.traces import default_store

    try:
        traces = default_store.read(limit=limit, source=source)
        return {
            "traces": traces,
            "taxonomy": taxonomy.build_taxonomy(traces),
            "summary": taxonomy.summarise(traces),
        }
    except Exception as exc:
        raise _fail(exc)


@router.delete("/api/traces")
def clear_traces(request: TraceClearRequest = None):
    """Deletes every stored trace.

    Args:
        request: Must carry ``confirm`` - the trace log is the only record of
            what the assistant has been asked and how it answered.

    Returns:
        Dict with the number of traces removed.
    """
    from policy_rag.observability.traces import default_store

    _require_confirmation((request or TraceClearRequest()).confirm, "trace deletion")
    try:
        return {"removed": default_store.clear()}
    except Exception as exc:
        raise _fail(exc)
