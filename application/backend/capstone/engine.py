"""Policy Answer Desk engine: runs the Week 12 capstone agent inside a Langfuse trace.

Nothing here invents timings. The agent's real calls are wrapped once at startup:
- every `mcp.dispatch(...)` becomes a `tool` span
- the colleague-leak check and the HRBP discretionary check become `guardrail` spans
Tool inputs/outputs are redacted before they reach telemetry (grade, salary, leave balances).
"""

from typing import Any, Callable, Dict, Optional

from curriculum.week_12_capstone.capstone_agent import capstone_agent
from curriculum.week_12_capstone.data.employees import sanitize_for_logging
from application.backend.observability.langfuse_telemetry import REDACTED, capstone_telemetry


def _redact_tool_io(tool_name: str, arguments: Dict[str, Any], result: Optional[Dict[str, Any]] = None):
    """Returns (input, output) safe for telemetry."""
    if tool_name == "escalate_to_hrbp":
        # issue_summary and grade-band clause names both reveal the requester's grade
        safe_in = {"employee_id": arguments.get("employee_id"), "policy_clause": REDACTED}
    else:
        safe_in = dict(arguments)
    if result is None:
        return safe_in, None

    status = result.get("status")
    if tool_name == "get_employee_record" and "employee" in result:
        safe_out = {"status": status, "employee": sanitize_for_logging(result["employee"])}
    elif tool_name == "check_leave_balance":
        safe_out = {"status": status, "leave_balances": REDACTED}
    elif tool_name == "search_policy_docs":
        safe_out = {"status": status, "results": [
            {k: r.get(k) for k in ("source", "version", "clause", "effective_date")}
            for r in result.get("results", [])
        ]}
    elif tool_name == "escalate_to_hrbp":
        safe_out = {"status": status, "ticket_id": result.get("ticket_id")}
    else:
        safe_out = {"status": status, "message": result.get("message")}
    return safe_in, safe_out


class _TracedMCP:
    """Proxy over the MCP server: each dispatch is a measured `tool` span."""

    def __init__(self, server: Any):
        self._server = server

    def __getattr__(self, name: str) -> Any:
        return getattr(self._server, name)

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        safe_in, _ = _redact_tool_io(tool_name, arguments)
        with capstone_telemetry.span(f"mcp_tool::{tool_name}", as_type="tool", input=safe_in,
                                     metadata={"transport": "in_process_dispatch"}) as s:
            result = self._server.dispatch(tool_name, arguments)
            _, safe_out = _redact_tool_io(tool_name, arguments, result)
            s.update(output=safe_out, level="WARNING" if result.get("status") == "error" else None)
            return result


def _traced_guardrail(fn: Callable, name: str, summarize: Callable[[Any], Any]) -> Callable:
    def wrapper(*args, **kwargs):
        with capstone_telemetry.span(name, as_type="guardrail") as s:
            out = fn(*args, **kwargs)
            s.update(output=summarize(out))
            return out
    return wrapper


# Instrument the shared agent instance once. Outside a trace these wrappers are no-ops,
# so the curriculum eval scripts that import capstone_agent directly are unaffected.
if not isinstance(capstone_agent.mcp, _TracedMCP):
    capstone_agent.mcp = _TracedMCP(capstone_agent.mcp)
    capstone_agent._detect_adversarial_leak_attempt = _traced_guardrail(
        capstone_agent._detect_adversarial_leak_attempt, "colleague_leak_guardrail",
        lambda r: {"is_leak_attempt": r.get("is_leak_attempt")},
    )
    capstone_agent._check_discretionary_exception = _traced_guardrail(
        capstone_agent._check_discretionary_exception, "hrbp_discretionary_check",
        # reason and clause text can name the grade band, so only the decision is logged
        lambda r: {"needs_escalation": bool(r and r.get("needs_escalation"))},
    )


class CapstoneEngine:
    """Service layer for the Policy Answer Desk."""

    async def execute_query(
        self,
        query: str,
        employee_id: str = "EMP-IND-301",
        force_year: Optional[int] = None,
        client_channel: str = "Web_UI_Policy_Desk",
    ) -> Dict[str, Any]:
        with capstone_telemetry.trace(
            "policy_answer_desk",
            input={"query": query, "force_year": force_year},
            user_id=employee_id,
            tags=["capstone", client_channel],
            metadata={"client_channel": client_channel},
        ) as t:
            res = await capstone_agent.answer_policy_query(query=query, employee_id=employee_id, force_year=force_year)
            t.update(output=res.get("answer"), metadata={
                "status": res.get("status"),
                "entity": (res.get("resolved_profile") or {}).get("entity"),
                "escalated": res.get("escalated", False),
                "policy_version_used": res.get("policy_version_used"),
            })
            t.local["status"] = res.get("status", "SUCCESS")
            t.local["final_response"] = {
                "answer": res.get("answer"),
                "citations": res.get("citations", []),
                "escalated_to_hrbp": res.get("escalated", False),
                "ticket_id": res.get("ticket_id"),
            }

        rec = t.local  # finalized when the trace block exits
        return {
            **{k: v for k, v in res.items() if k != "spans"},
            "trace_id": rec["trace_id"],
            "latency_ms": rec["total_latency_ms"],
            "pii_audit_status": rec["pii_audit_status"],
            "langfuse_url": rec.get("langfuse_url"),
            "trace": rec,
        }


capstone_engine = CapstoneEngine()
