"""The assistant's answer service - the one path every question takes.

``answer`` is called by the web UI, the CLI and every evaluation suite, so
there is a single definition of what "asking the assistant a question" means:
condense the follow-up, retrieve, generate under the citation-enforcing prompt,
label the result and write a trace.

Because evaluation goes through the same function as live traffic, the error
analysis is reading the real system rather than a parallel implementation of it.
"""

import time
import uuid
from datetime import datetime, timezone

from policy_rag import config
from policy_rag.chat.session import condense_question
from policy_rag.observability import taxonomy
from policy_rag.observability.traces import default_store, new_run_id
from policy_rag.retrieval import engine

# Failures that look like a rate limit.
_RATE_LIMIT_MARKERS = ("429", "quota", "resourceexhausted", "rate limit")

# ...of which these are the ones waiting cannot fix. A per-minute ceiling
# clears in a minute; a daily allowance does not clear until tomorrow, so
# retrying it just spends the next request on a guaranteed failure.
_EXHAUSTED_MARKERS = ("perday", "per day", "requestsperday", "daily limit")


def _is_rate_limited(message: str) -> bool:
    """Returns True when an error message looks like a rate limit of any kind."""
    lowered = (message or "").lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


def is_quota_exhausted(message: str) -> bool:
    """Returns True when the failure is a daily allowance, not a momentary limit.

    Callers running a batch use this to stop early: once the day's quota is
    gone, every remaining question would be recorded as a failure of the
    assistant when it is really a failure to ask.
    """
    lowered = (message or "").lower()
    return _is_rate_limited(lowered) and any(m in lowered for m in _EXHAUSTED_MARKERS)


def _is_retryable(message: str) -> bool:
    """Returns True when waiting and trying again could plausibly succeed."""
    return _is_rate_limited(message) and not is_quota_exhausted(message)


def _collect_token_usage() -> dict:
    """Returns the token-usage block for the current query.

    Counts come from llama-index's tiktoken-based handler and are labelled as
    estimates: the Gemini integration does not reliably surface provider usage,
    and reporting an estimate as ground truth would be a lie in the envelope.
    """
    counter = engine.token_counter()
    if counter is None:
        return {"prompt": 0, "completion": 0, "total": 0, "method": "unavailable"}
    return {
        "prompt": counter.prompt_llm_token_count,
        "completion": counter.completion_llm_token_count,
        "total": counter.total_llm_token_count,
        "method": "estimated-tiktoken",
    }


def _collect_source_chunks(response) -> list:
    """Extracts the retrieved chunks from a query response.

    Args:
        response: The llama-index response object from a completed query.

    Returns:
        List of dicts with ``rank``, ``node_id``, ``score``, ``source_file``,
        ``region``, ``section`` and a short text preview per retrieved chunk.
    """
    chunks = []
    for rank, scored_node in enumerate(getattr(response, "source_nodes", None) or [], start=1):
        node = scored_node.node
        metadata = node.metadata or {}
        chunks.append({
            "rank": rank,
            "node_id": node.node_id,
            "score": round(scored_node.score, 4) if scored_node.score is not None else None,
            "source_file": metadata.get("source_file", "unknown"),
            "region": metadata.get("region", "unknown"),
            "section": metadata.get("section", metadata.get("policy_id", "")),
            "text_preview": (node.text or "")[:160].replace("\n", " "),
        })
    return chunks


def answer(
    query: str,
    region: str = None,
    top_k: int = None,
    hybrid: bool = None,
    history: list = None,
    session_id: str = None,
    run_id: str = "live",
    source: str = "chat",
    expectation: dict = None,
    trace: bool = True,
    retries: int = 0,
    retry_delay: float = 5.0,
) -> dict:
    """Answers a policy question and records a trace of how it went.

    Args:
        query: The user's question.
        region: Optional region metadata filter (e.g. ``"US"``).
        top_k: Leaf chunks retrieved before auto-merging.
        hybrid: Whether to fuse BM25 with vector retrieval.
        history: Prior conversation turns; when present the question is
            condensed into a standalone one before retrieval.
        session_id: Conversation this question belongs to.
        run_id: Groups traces produced together (an evaluation run).
        source: Trace origin - ``"chat"`` for real traffic, ``"evaluation"``
            for suite runs.
        expectation: Gold data (``expected_type``, ``expected_source``,
            ``expected_section``) used to label the trace. Live traffic has none.
        trace: Set False to answer without writing to the trace log.
        retries: Retry attempts for rate-limited LLM calls.
        retry_delay: Seconds before the first retry; grows linearly.

    Returns:
        The answer envelope: ``answer``, ``is_refusal``, ``retrieved_chunks``,
        ``tokens``, ``latency_ms``, model names, the retrieval settings used,
        the label assigned by the taxonomy and the ``trace_id``.
    """
    top_k = config.DEFAULT_TOP_K if top_k is None else top_k
    hybrid = config.DEFAULT_HYBRID if hybrid is None else hybrid
    expectation = expectation or {}
    # Live traffic always belongs to a conversation, so a caller that did not
    # supply one gets an id back to continue with.
    if session_id is None and source == "chat":
        session_id = new_run_id("chat")

    standalone = condense_question(query, history)
    was_condensed = standalone != query

    error = None
    response = None
    latency_ms = 0
    start = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            query_engine = engine.build_query_engine(region=region, top_k=top_k, hybrid=hybrid)
            engine.token_counter().reset_counts()
            start = time.perf_counter()
            response = query_engine.query(standalone)
            latency_ms = round((time.perf_counter() - start) * 1000)
            error = None
            break
        except Exception as exc:  # noqa: BLE001 - surfaced in the trace, not swallowed
            error = f"{type(exc).__name__}: {exc}"
            latency_ms = round((time.perf_counter() - start) * 1000)
            if attempt < retries and _is_retryable(str(exc)):
                # Exponential, not linear: rate limits are enforced over a
                # window, so each retry has to wait meaningfully longer than
                # the last to have a chance of landing outside it.
                time.sleep(retry_delay * (2 ** attempt))
                continue
            break

    answer_text_value = "" if response is None else str(response)
    envelope = {
        "trace_id": uuid.uuid4().hex[:12],
        "run_id": run_id,
        "source": source,
        "session_id": session_id,
        "query": query,
        "standalone_query": standalone if was_condensed else None,
        "region": region,
        "top_k": top_k,
        "hybrid": hybrid,
        "answer": answer_text_value,
        "is_refusal": config.REFUSAL_SENTINEL in answer_text_value,
        "retrieved_chunks": _collect_source_chunks(response),
        "tokens": _collect_token_usage() if response is not None else {},
        "latency_ms": latency_ms,
        "llm_model": engine.active_llm_name(),
        "embed_model": config.EMBED_MODEL_NAME,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "golden_id": expectation.get("golden_id"),
        "expected_type": expectation.get("expected_type"),
        "expected_source": expectation.get("expected_source"),
        "expected_section": expectation.get("expected_section"),
        "error": error,
    }

    verdict = taxonomy.classify(envelope, expectation=expectation)
    envelope.update(verdict)

    if trace:
        default_store.append(envelope)
    return envelope


def answer_text(query: str, region: str = None, top_k: int = None, hybrid: bool = None) -> str:
    """Answers a question and returns only the answer string.

    Args:
        query: The user's question.
        region: Optional region metadata filter.
        top_k: Leaf chunks retrieved before auto-merging.
        hybrid: Whether to fuse BM25 with vector retrieval.

    Returns:
        The answer text.
    """
    return answer(query, region=region, top_k=top_k, hybrid=hybrid)["answer"]
