"""Append-only trace log for every answer the assistant produces.

A trace is the record of one question passing through the pipeline: what was
asked, what was retrieved, what came back and what it cost. Traces are written
by ``policy_rag.chat.service`` on every answer - whether it came from the web
UI, the CLI or an evaluation suite - so error analysis reads real production
traffic rather than the output of a separate offline script.

Storage is newline-delimited JSON at ``config.TRACE_FILE``: append-only, cheap
to tail, trivially diffable, and readable by any tool without a database.
"""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

from policy_rag import config

# Fields every trace carries. Records written by older versions are normalised
# to this shape on read so historical traces stay loadable.
TRACE_DEFAULTS = {
    "trace_id": "",
    "run_id": "legacy",
    "source": "evaluation",
    "session_id": None,
    "query": "",
    "standalone_query": None,
    "region": None,
    "top_k": config.DEFAULT_TOP_K,
    "hybrid": False,
    "answer": "",
    "is_refusal": False,
    "retrieved_chunks": [],
    "top_sources": [],
    "tokens": {},
    "latency_ms": 0,
    "llm_model": "",
    "embed_model": "",
    "timestamp": "",
    "golden_id": None,
    "expected_type": None,
    "expected_source": None,
    "expected_section": None,
    "label": "UNLABELED",
    "observation": "",
    "retrieval_ok": None,
    "error": None,
}

# Renamed fields, old name -> current name.
_LEGACY_ALIASES = {"correct_source": "expected_source"}


def new_run_id(prefix: str = "run") -> str:
    """Returns a sortable identifier for one evaluation run or chat session.

    Args:
        prefix: Short label placed in front of the timestamp (e.g. ``"run"``).

    Returns:
        A string such as ``run-20260824T101500Z-4f2c``.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:4]}"


def normalise(record: dict) -> dict:
    """Fills in missing fields and renames legacy ones.

    Args:
        record: A raw trace dict read from disk or built in memory.

    Returns:
        A new dict containing every key in ``TRACE_DEFAULTS``.
    """
    merged = dict(TRACE_DEFAULTS)
    for old, new in _LEGACY_ALIASES.items():
        if old in record and new not in record:
            record = {**record, new: record[old]}
    merged.update({k: v for k, v in record.items() if k in TRACE_DEFAULTS})
    if not merged["trace_id"]:
        merged["trace_id"] = uuid.uuid4().hex[:12]
    if not merged["timestamp"]:
        merged["timestamp"] = datetime.now(timezone.utc).isoformat()
    if not merged["top_sources"]:
        merged["top_sources"] = [
            c.get("source_file", "unknown") for c in merged["retrieved_chunks"][:3]
        ]
    return merged


class TraceStore:
    """A JSONL trace log.

    Attributes:
        path: File the traces are appended to.
    """

    def __init__(self, path=None):
        """Initialises the store.

        Args:
            path: Trace file to use. Defaults to ``config.TRACE_FILE``.
        """
        self.path = path or config.TRACE_FILE

    def append(self, record: dict) -> dict:
        """Writes one trace to the log.

        Args:
            record: Trace fields; missing ones are defaulted by ``normalise``.

        Returns:
            The normalised record that was written.
        """
        normalised = normalise(record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(normalised, ensure_ascii=False) + "\n")
        return normalised

    def read(self, limit: int = None, run_id: str = None, source: str = None) -> list:
        """Reads traces oldest-first, optionally filtered.

        Args:
            limit: Return at most this many traces, keeping the most recent.
            run_id: Only traces from this run.
            source: Only traces from this origin (``"chat"`` or ``"evaluation"``).

        Returns:
            List of normalised trace dicts.
        """
        if not self.path.exists():
            return []
        traces = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(normalise(json.loads(line)))
                except json.JSONDecodeError:
                    # A partially written final line must not break reading.
                    continue
        if run_id:
            traces = [t for t in traces if t["run_id"] == run_id]
        if source:
            traces = [t for t in traces if t["source"] == source]
        if limit is not None:
            traces = traces[-limit:]
        return traces

    def latest_run_id(self, source: str = "evaluation") -> str:
        """Returns the run id of the most recent run from ``source``, or None."""
        traces = self.read(source=source)
        return traces[-1]["run_id"] if traces else None

    def latest_run(self, source: str = "evaluation") -> list:
        """Returns every trace belonging to the most recent run from ``source``."""
        run_id = self.latest_run_id(source=source)
        return self.read(run_id=run_id) if run_id else []

    def count(self) -> int:
        """Returns the number of traces currently stored."""
        return len(self.read())

    def clear(self) -> int:
        """Deletes the trace log.

        Returns:
            How many traces were removed.
        """
        removed = self.count()
        if self.path.exists():
            os.remove(self.path)
        return removed

    def prune(self, keep: int) -> int:
        """Trims the log to its most recent traces.

        Args:
            keep: Number of traces to retain.

        Returns:
            How many traces were dropped.
        """
        traces = self.read()
        if len(traces) <= keep:
            return 0
        kept = traces[-keep:]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a sibling temp file and replace, so an interrupted prune
        # cannot leave a half-written log behind.
        fd, tmp_path = tempfile.mkstemp(dir=str(self.path.parent), suffix=".jsonl")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            for trace in kept:
                handle.write(json.dumps(trace, ensure_ascii=False) + "\n")
        os.replace(tmp_path, self.path)
        return len(traces) - len(kept)


default_store = TraceStore()
