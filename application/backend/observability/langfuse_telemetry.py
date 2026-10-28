"""Langfuse v5 tracing + durable local flow store (SQLite).

One primitive for every pipeline: `trace()` opens a request, `span()` times a step inside it,
`event()` marks a point in time, `score()` attaches an evaluation. Everything is measured for real
and lands in two places at once:
1. Langfuse (live, nested OTel observations + scores) when LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are set
2. storage/traces.db: every trace with its full span tree, inputs, outputs, errors and scores

Outside a `trace()` the helpers are no-ops, so instrumented code still runs untraced (CLI evals, tests).
Callers must pass already-redacted input/output: whatever goes in a span goes to telemetry.
"""

import contextvars
import json
import os
import sqlite3
import subprocess
import threading
import time
import traceback
import uuid
from contextlib import ExitStack, contextmanager
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

import numpy as np

from application.backend.core.config import settings  # loads .env before we read LANGFUSE_*

try:
    from langfuse import Langfuse, propagate_attributes
except ImportError:
    Langfuse = None

PII_KEYS = ("grade", "base_salary", "leave_balances", "salary", "ssn", "vacation_balance")
REDACTED = "[REDACTED_PII]"

_current_trace: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("current_trace", default=None)
_current_parent: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("current_parent", default=None)

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY, name TEXT, session_id TEXT, user_id TEXT, status TEXT, route TEXT,
    started_at REAL, latency_ms REAL, tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL, body TEXT
);
CREATE INDEX IF NOT EXISTS traces_started ON traces(started_at);
CREATE INDEX IF NOT EXISTS traces_session ON traces(session_id);
CREATE TABLE IF NOT EXISTS scores (
    score_id TEXT PRIMARY KEY, trace_id TEXT, name TEXT, value REAL, source TEXT, comment TEXT, created_at REAL
);
CREATE INDEX IF NOT EXISTS scores_trace ON scores(trace_id);
"""


def redact(obj: Any) -> Any:
    """Masks PII keys anywhere in a nested structure before it is logged."""
    if isinstance(obj, dict):
        return {k: (REDACTED if k in PII_KEYS else redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    return obj


def _now_iso() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int(t * 1000) % 1000:03d}Z"


def _git_sha() -> Optional[str]:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=settings.base_dir,
                              capture_output=True, text=True, timeout=3).stdout.strip() or None
    except Exception:
        return None


class Observation:
    """Handle yielded by trace()/span(): `update()` writes locally and to the Langfuse observation."""

    def __init__(self, local: Dict[str, Any], lf: Any, service: "GoldStandardTelemetryService"):
        self.local, self._lf, self._svc = local, lf, service

    def update(
        self,
        output: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        usage: Optional[Dict[str, int]] = None,
        model: Optional[str] = None,
        model_parameters: Optional[Dict[str, Any]] = None,
        level: Optional[str] = None,
        status_message: Optional[str] = None,
    ) -> None:
        if output is not None:
            self.local["output"] = output
        if metadata:
            self.local["attributes"].update(metadata)
        if usage:
            self.local["tokens"] = {"in": usage.get("input", 0), "out": usage.get("output", 0)}
        if model:
            self.local["attributes"]["model"] = model
        if model_parameters:
            self.local["attributes"]["model_parameters"] = model_parameters
        if level:
            self.local["level"] = level
        if status_message:
            self.local["status_message"] = status_message
        if self._lf is not None:
            try:
                self._lf.update(output=output, metadata=metadata, usage_details=usage, model=model,
                                model_parameters=model_parameters, level=level, status_message=status_message)
            except Exception as e:
                self._svc._last_langfuse_error = f"update failed: {e}"


class GoldStandardTelemetryService:
    """Langfuse sync plus local flow storage, query, waterfall, metrics, scores and export."""

    def __init__(self, db_path: Optional[Path] = None):
        self.langfuse_client: Optional[Any] = None
        self._langfuse_sync_count = 0
        self._last_langfuse_error: Optional[str] = None
        self._lock = threading.Lock()
        self.release = _git_sha()
        self.open_store(db_path or settings.base_dir / "application" / "backend" / "storage" / "traces.db")
        self._init_langfuse()

    def open_store(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = path
        self._db = sqlite3.connect(path, check_same_thread=False)
        # WAL + NORMAL: a commit costs microseconds instead of an fsync per write
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.executescript(SCHEMA)

    # ------------------------------------------------------------------ Langfuse

    def _init_langfuse(self, **client_kwargs: Any) -> None:
        """Connects when keys are set. client_kwargs lets tests inject e.g. span_exporter."""
        self.langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        self.langfuse_host = (os.getenv("LANGFUSE_HOST") or os.getenv("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com").strip()
        if Langfuse is None:
            self._last_langfuse_error = "Langfuse SDK not installed (pip install langfuse)."
            return
        if not (self.langfuse_public_key and os.getenv("LANGFUSE_SECRET_KEY", "").strip()):
            self._last_langfuse_error = "Credentials not set (local-only tracing)."
            return
        try:
            self.langfuse_client = Langfuse(host=self.langfuse_host, release=self.release, **client_kwargs)
            if not client_kwargs and not self.langfuse_client.auth_check():
                self._last_langfuse_error = "Auth check failed: invalid public or secret key."
                self.langfuse_client = None
                return
            self._last_langfuse_error = None
            print(f"[+] Langfuse tracing active -> {self.langfuse_host}")
        except Exception as e:
            self.langfuse_client = None
            self._last_langfuse_error = str(e)
            print(f"[-] Langfuse init error: {e}")

    def get_langfuse_status(self) -> Dict[str, Any]:
        try:
            sdk_version = version("langfuse")
        except PackageNotFoundError:
            sdk_version = None
        key = self.langfuse_public_key
        active = self.langfuse_client is not None
        return {
            "sdk_available": Langfuse is not None,
            "sdk_version": sdk_version,
            "is_configured": bool(key),
            "is_active": active,
            "host": self.langfuse_host,
            "public_key_masked": f"{key[:6]}...{key[-4:]}" if len(key) > 10 else ("Set" if key else "Not Configured"),
            "traces_synced": self._langfuse_sync_count,
            "last_notice": self._last_langfuse_error,
            "mode": "Langfuse + Local" if active else "Local only",
            "store": str(self.db_path),
            "release": self.release,
        }

    def flush(self) -> None:
        if self.langfuse_client is not None:
            self.langfuse_client.flush()

    # ------------------------------------------------------------------ tracing

    @contextmanager
    def trace(
        self,
        name: str,
        *,
        input: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Observation]:
        """Root of one request. The trace id is a 32-hex OTel id, identical locally and in Langfuse."""
        trace_id = uuid.uuid4().hex
        rec: Dict[str, Any] = {
            "trace_id": trace_id,
            "root_span_id": f"root-{trace_id[:8]}",
            "name": name,
            "timestamp_start": _now_iso(),
            "started_at": time.time(),
            "status": "SUCCESS",
            "route": None,
            "release": self.release,
            "request": {"requester_id": user_id, "session_id": session_id, "input": input},
            "attributes": dict(metadata or {}),
            "tags": tags or [],
            "spans": [],
        }
        t0 = time.perf_counter()
        rec["_t0"] = t0
        trace_tok = _current_trace.set(rec)
        parent_tok = _current_parent.set(rec["root_span_id"])
        try:
            with ExitStack() as stack:
                lf = None
                if self.langfuse_client is not None:
                    try:
                        lf = stack.enter_context(self.langfuse_client.start_as_current_observation(
                            trace_context={"trace_id": trace_id}, name=name, as_type="agent",
                            input=input, metadata=metadata,
                        ))
                        stack.enter_context(propagate_attributes(
                            user_id=user_id, session_id=session_id, tags=tags, trace_name=name,
                        ))
                    except Exception as e:
                        self._last_langfuse_error = f"trace start failed: {e}"
                root = Observation(rec, lf, self)
                try:
                    yield root
                except Exception as e:
                    rec["status"] = "PIPELINE_ERROR"
                    rec["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
                    root.update(level="ERROR", status_message=str(e))
                    raise
        finally:
            _current_parent.reset(parent_tok)
            _current_trace.reset(trace_tok)
            rec["total_latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
            rec["timestamp_end"] = _now_iso()
            if self.langfuse_client is not None:
                self._langfuse_sync_count += 1
            self._store(rec)

    @contextmanager
    def span(self, name: str, as_type: str = "span", input: Any = None, metadata: Optional[Dict[str, Any]] = None) -> Iterator[Observation]:
        """Times one step. as_type follows Langfuse: span|tool|retriever|generation|guardrail|chain|agent|evaluator."""
        rec = _current_trace.get()
        if rec is None:
            yield Observation({"attributes": {}}, None, self)
            return

        t = time.perf_counter()
        local: Dict[str, Any] = {
            "span_id": uuid.uuid4().hex[:16],
            "parent_span_id": _current_parent.get(),
            "name": name,
            "type": as_type,
            "start_time_offset_ms": round((t - rec["_t0"]) * 1000, 3),
            "latency_ms": 0.0,
            "tokens": {"in": 0, "out": 0},
            "cost_usd": 0.0,
            "input": input,
            "attributes": dict(metadata or {}),
        }
        rec["spans"].append(local)
        parent_tok = _current_parent.set(local["span_id"])
        try:
            with ExitStack() as stack:
                lf = None
                if self.langfuse_client is not None:
                    try:
                        lf = stack.enter_context(self.langfuse_client.start_as_current_observation(
                            name=name, as_type=as_type, input=input, metadata=metadata,
                        ))
                    except Exception as e:
                        self._last_langfuse_error = f"span start failed: {e}"
                obs = Observation(local, lf, self)
                try:
                    yield obs
                except Exception as e:
                    local["error"] = {"type": type(e).__name__, "message": str(e), "traceback": traceback.format_exc()}
                    obs.update(level="ERROR", status_message=str(e))
                    raise
        finally:
            local["latency_ms"] = round((time.perf_counter() - t) * 1000, 3)
            _current_parent.reset(parent_tok)

    def event(self, name: str, input: Any = None, output: Any = None, metadata: Optional[Dict[str, Any]] = None,
              level: Optional[str] = None) -> None:
        """A point-in-time marker (cache hit, fallback taken, reasoning step) inside the current span."""
        rec = _current_trace.get()
        if rec is None:
            return
        rec["spans"].append({
            "span_id": uuid.uuid4().hex[:16],
            "parent_span_id": _current_parent.get(),
            "name": name,
            "type": "event",
            "start_time_offset_ms": round((time.perf_counter() - rec["_t0"]) * 1000, 3),
            "latency_ms": 0.0,
            "tokens": {"in": 0, "out": 0},
            "cost_usd": 0.0,
            "input": input,
            "output": output,
            "attributes": dict(metadata or {}),
            **({"level": level} if level else {}),
        })
        if self.langfuse_client is not None:
            try:
                self.langfuse_client.create_event(name=name, input=input, output=output, metadata=metadata, level=level)
            except Exception as e:
                self._last_langfuse_error = f"event failed: {e}"

    def score(self, name: str, value: float, comment: Optional[str] = None) -> None:
        """Automatic evaluation score for the current trace; written together with the trace."""
        rec = _current_trace.get()
        if rec is None:
            return
        rec.setdefault("_pending_scores", []).append(self._score_entry(rec["trace_id"], name, value, comment, "auto"))
        self._send_score(rec["trace_id"], name, value, comment, "auto")

    def current_trace_id(self) -> Optional[str]:
        rec = _current_trace.get()
        return rec["trace_id"] if rec else None

    # ------------------------------------------------------------------ storage

    def _store(self, rec: Dict[str, Any]) -> None:
        rec.pop("_t0", None)
        pending = rec.pop("_pending_scores", [])
        rec["total_tokens_in"] = sum(s["tokens"]["in"] for s in rec["spans"])
        rec["total_tokens_out"] = sum(s["tokens"]["out"] for s in rec["spans"])
        rec["total_cost_usd"] = round(sum(s["cost_usd"] for s in rec["spans"]), 7)
        rec["pii_audit_status"] = self._audit_pii(rec)
        rec["langfuse_url"] = None
        if self.langfuse_client is not None:
            try:
                rec["langfuse_url"] = self.langfuse_client.get_trace_url(trace_id=rec["trace_id"])
            except Exception:
                pass
        row = (rec["trace_id"], rec["name"], rec["request"].get("session_id"), rec["request"].get("requester_id"),
               rec["status"], rec.get("route"), rec["started_at"], rec["total_latency_ms"],
               rec["total_tokens_in"], rec["total_tokens_out"], rec["total_cost_usd"], json.dumps(rec, default=str))
        try:
            with self._lock, self._db:
                self._db.execute("INSERT OR REPLACE INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", row)
                self._db.executemany("INSERT INTO scores VALUES (?,?,?,?,?,?,?)", [tuple(e.values()) for e in pending])
        except sqlite3.Error as e:
            print(f"[-] Failed to store trace {rec['trace_id']}: {e}")

    def _audit_pii(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Walks every span's input/output/attributes; any unredacted PII key is a violation."""
        leaks: List[str] = []

        def walk(node: Any, where: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in PII_KEYS and v != REDACTED:
                        leaks.append(f"{k} unmasked in {where}")
                    walk(v, where)
            elif isinstance(node, list):
                for v in node:
                    walk(v, where)

        for s in rec["spans"]:
            walk([s.get("input"), s.get("output"), s.get("attributes")], f"span {s['name']}")
        return {
            "policy_enforced": "LEAST_PRIVILEGE_PII_REDACTION_v2",
            "redacted_fields": list(PII_KEYS),
            "is_compliant": not leaks,
            "violations": leaks,
        }

    # ------------------------------------------------------------------ scores

    def score_trace(self, trace_id: str, name: str, value: float, comment: Optional[str] = None,
                    source: str = "user") -> Dict[str, Any]:
        """Persists a score (human feedback or automatic evaluator) and mirrors it to Langfuse."""
        entry = self._score_entry(trace_id, name, value, comment, source)
        with self._lock, self._db:
            self._db.execute("INSERT INTO scores VALUES (?,?,?,?,?,?,?)", tuple(entry.values()))
        self._send_score(trace_id, name, value, comment, source)
        return entry

    @staticmethod
    def _score_entry(trace_id: str, name: str, value: float, comment: Optional[str], source: str) -> Dict[str, Any]:
        return {
            "score_id": uuid.uuid4().hex[:12],
            "trace_id": trace_id,
            "name": name,
            "value": float(value),
            "source": source,
            "comment": comment or "",
            "created_at": time.time(),
        }

    def _send_score(self, trace_id: str, name: str, value: float, comment: Optional[str], source: str) -> None:
        if self.langfuse_client is None:
            return
        try:
            self.langfuse_client.create_score(trace_id=trace_id, name=name, value=float(value), comment=comment,
                                              metadata={"source": source})
        except Exception as e:
            self._last_langfuse_error = f"score failed: {e}"

    def _scores_for(self, trace_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
        if not trace_ids:
            return {}
        cur = self._db.execute(
            f"SELECT score_id, trace_id, name, value, source, comment, created_at FROM scores "
            f"WHERE trace_id IN ({','.join('?' * len(trace_ids))}) ORDER BY created_at", trace_ids)
        out: Dict[str, List[Dict[str, Any]]] = {}
        for sid, tid, name, value, source, comment, created in cur:
            out.setdefault(tid, []).append({"score_id": sid, "name": name, "value": value, "source": source,
                                            "comment": comment, "created_at": created})
        return out

    # ------------------------------------------------------------------ queries

    def get_traces(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
        name: Optional[str] = None,
        employee_id: Optional[str] = None,
        search_query: Optional[str] = None,
        session_id: Optional[str] = None,
        route: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Newest-first, filtered, paginated traces with scores attached."""
        where, args = [], []
        for col, val in (("status", status), ("name", name), ("user_id", employee_id),
                         ("session_id", session_id), ("route", route)):
            if val and val.upper() != "ALL":
                where.append(f"{col} = ?")
                args.append(val)
        if search_query:
            where.append("body LIKE ?")
            args.append(f"%{search_query}%")
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        total = self._db.execute(f"SELECT COUNT(*) FROM traces {clause}", args).fetchone()[0]
        rows = self._db.execute(f"SELECT body FROM traces {clause} ORDER BY started_at DESC LIMIT ? OFFSET ?",
                                [*args, limit, offset]).fetchall()
        traces = [json.loads(r[0]) for r in rows]
        scores = self._scores_for([t["trace_id"] for t in traces])
        for t in traces:
            t["scores"] = scores.get(t["trace_id"], [])
        return {"total": total, "limit": limit, "offset": offset, "traces": traces}

    def get_trace_by_id(self, trace_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute("SELECT body FROM traces WHERE trace_id = ?", (trace_id,)).fetchone()
        if not row:
            return None
        trace = json.loads(row[0])
        trace["scores"] = self._scores_for([trace_id]).get(trace_id, [])
        return trace

    def get_trace_waterfall(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Gantt segments with tree depth, from measured span offsets/latencies."""
        trace = self.get_trace_by_id(trace_id)
        if not trace:
            return None
        total = max(float(trace.get("total_latency_ms") or 0.0), 0.001)
        depth = {trace.get("root_span_id"): -1}
        segments = []
        for s in trace.get("spans", []):
            depth[s["span_id"]] = depth.get(s.get("parent_span_id"), -1) + 1
            left = min(s["start_time_offset_ms"] / total * 100, 99.5)
            segments.append({
                "span_id": s["span_id"],
                "parent_span_id": s.get("parent_span_id"),
                "depth": depth[s["span_id"]],
                "name": s["name"],
                "category": s.get("type", "span"),
                "start_offset_ms": s["start_time_offset_ms"],
                "latency_ms": s["latency_ms"],
                "left_pct": round(left, 2),
                "width_pct": round(max(min(s["latency_ms"] / total * 100, 100.0 - left), 0.4), 2),
                "cost_usd": s.get("cost_usd", 0.0),
                "tokens": s.get("tokens", {"in": 0, "out": 0}),
                "level": s.get("level"),
                "error": s.get("error"),
                "input": s.get("input"),
                "output": s.get("output"),
                "attributes": s.get("attributes", {}),
            })
        return {
            "trace_id": trace_id,
            "total_latency_ms": trace.get("total_latency_ms"),
            "total_tokens_in": trace.get("total_tokens_in", 0),
            "total_tokens_out": trace.get("total_tokens_out", 0),
            "total_cost_usd": trace.get("total_cost_usd", 0.0),
            "spans_count": len(segments),
            "segments": segments,
        }

    def get_metrics_summary(self, name: Optional[str] = None) -> Dict[str, Any]:
        """Latency percentiles, tokens, cost, PII compliance, and distributions by status/route/failure label."""
        clause, args = ("WHERE name = ?", [name]) if name else ("", [])
        rows = self._db.execute(f"SELECT trace_id, status, route, latency_ms, tokens_in, tokens_out, cost_usd, body "
                                f"FROM traces {clause}", args).fetchall()
        total = len(rows)
        latencies = [r[3] or 0.0 for r in rows]
        cost = sum(r[6] or 0.0 for r in rows)
        status_dist: Dict[str, int] = {}
        route_dist: Dict[str, int] = {}
        violations = 0
        for _, st, rt, _, _, _, _, body in rows:
            status_dist[st] = status_dist.get(st, 0) + 1
            route_dist[rt or "none"] = route_dist.get(rt or "none", 0) + 1
            if not json.loads(body).get("pii_audit_status", {}).get("is_compliant", True):
                violations += 1

        ids = [r[0] for r in rows]
        taxonomy: Dict[str, int] = {}
        score_avgs: Dict[str, List[float]] = {}
        for lst in self._scores_for(ids).values():
            for s in lst:
                score_avgs.setdefault(s["name"], []).append(s["value"])
                if s["name"] == "failure_severity":
                    taxonomy[s["comment"]] = taxonomy.get(s["comment"], 0) + 1
        pct = lambda q: round(float(np.percentile(latencies, q)), 2) if latencies else 0.0
        return {
            "total_queries": total,
            "mean_latency_ms": round(float(np.mean(latencies)), 2) if latencies else 0.0,
            "p50_latency_ms": pct(50),
            "p95_latency_ms": pct(95),
            "p99_latency_ms": pct(99),
            "total_tokens_in": sum(r[4] or 0 for r in rows),
            "total_tokens_out": sum(r[5] or 0 for r in rows),
            "total_cost_usd": round(cost, 6),
            "cost_per_query_usd": round(cost / total, 7) if total else 0.0,
            "pii_compliance_rate_pct": round((total - violations) / total * 100, 1) if total else 100.0,
            "status_distribution": status_dist,
            "route_distribution": route_dist,
            "failure_taxonomy": taxonomy,
            "score_averages": {k: round(sum(v) / len(v), 3) for k, v in score_avgs.items()},
            "langfuse_status": self.get_langfuse_status(),
        }

    def export_traces(self, export_format: str = "json") -> str:
        rows = self._db.execute("SELECT body FROM traces ORDER BY started_at").fetchall()
        traces = [json.loads(r[0]) for r in rows]
        scores = self._scores_for([t["trace_id"] for t in traces])
        for t in traces:
            t["scores"] = scores.get(t["trace_id"], [])
        if export_format == "jsonl":
            return "\n".join(json.dumps(t, default=str) for t in traces)
        return json.dumps(traces, indent=2, default=str)


capstone_telemetry = GoldStandardTelemetryService()
