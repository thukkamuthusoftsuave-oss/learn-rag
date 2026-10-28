"""Chat service: one entry point that routes each question to the right pipeline.

Pipeline for every question (each step is a traced span):
  condense follow-up (W6) -> input injection scan (W8 L2) -> route decision
  -> rag (W1-W6) | fixed_workflow (W7) | react_agent (W7/W8) | multi_agent_squad (W10) | policy_desk (W9/W12)
  -> output invariant check (W8 L4) -> evaluators (W4 failure separation, W5 taxonomy, W6 citation grounding)
"""

import asyncio
import re
import time
from functools import partial
from typing import List, Dict, Any, Optional, Tuple

from application.backend.retrieval.engine import hybrid_retriever
from application.backend.security.defense import security_defense
from application.backend.chat.llm import llm_client, MANDATED_REFUSAL_PHRASE
from application.backend.chat.router import RouteDecision, decide
from application.backend.agent.orchestrator import policy_orchestrator
from application.backend.observability.langfuse_telemetry import capstone_telemetry as tracer, redact
from application.backend.observability.telemetry import SEVERITY_WEIGHTS, telemetry_service

TOPIC_LABEL = {
    "notice_period": "notice period",
    "carry_over_cap": "carry-over cap",
    "sabbatical": "sabbatical",
    "eligibility": "eligibility",
}


class ChatService:
    """Enterprise conversational policy assistant service."""

    @staticmethod
    def condense_query(query: str, history: List[Dict[str, str]]) -> Tuple[str, bool]:
        """Rewrites ambiguous conversational follow-ups into standalone retrieval queries."""
        if not history:
            return query, False

        lower_q = query.lower().strip()
        last_turn = history[-1]
        prev_user_q = last_turn.get("user", "")

        # Check for follow-up patterns
        if lower_q.startswith("what about") or lower_q.startswith("how about") or "what about in" in lower_q:
            match = re.search(r"(?:what|how)\s+about\s+(?:in\s+)?(?:the\s+)?([A-Za-z0-9\s-]+)\??", lower_q)
            if match:
                new_target = match.group(1).strip().upper()
                for reg in ["US", "UK", "EMEA", "APAC", "LATAM", "NA"]:
                    if reg in prev_user_q.upper():
                        condensed = re.sub(rf"\b{reg}\b", new_target, prev_user_q, flags=re.IGNORECASE)
                        return condensed, True
                prev_emp = re.search(r"\bEMP-(?:[A-Z]+-)?\d+\b", prev_user_q, re.IGNORECASE)
                if prev_emp and new_target.startswith("EMP-"):
                    return prev_user_q.replace(prev_emp.group(0), new_target), True
                return f"{prev_user_q} in {new_target}", True

        if "does that apply" in lower_q or "what is it for" in lower_q:
            return f"{prev_user_q} (context: {query})", True

        return query, False

    # ------------------------------------------------------------------ entry points

    async def handle(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        region: Optional[str] = None,
        top_k: int = 5,
        hybrid: bool = True,
        force_route: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Routes the question automatically and runs the chosen pipeline."""
        start_time = time.perf_counter()
        history = chat_history or []

        with tracer.span("query_condensation", as_type="chain",
                         input={"query": query, "history": history[-3:], "history_turns": len(history)}) as s:
            condensed_query, was_condensed = self.condense_query(query, history)
            s.update(output={"condensed_query": condensed_query, "was_condensed": was_condensed})

        with tracer.span("input_injection_scan", as_type="guardrail", input=condensed_query,
                         metadata={"defense_layer": "L2 signature scan"}) as s:
            scan = security_defense.scan_for_injections(condensed_query)
            s.update(output=scan, level="WARNING" if scan["is_attack"] else None)

        base = {
            "condensed_query": condensed_query,
            "was_condensed": was_condensed,
            "retrieved_chunks": [],
            "citations": [],
        }
        if scan["is_attack"]:
            tracer.score("injection_blocked", 1, ", ".join(scan["detected_signatures"]))
            return {**base, "answer": "This request was blocked: it contains instructions that try to override the policy rules.",
                    "route": "blocked", "route_reasons": ["Prompt-injection signature found in the question."],
                    "latency_ms": self._ms(start_time), "tokens_used": 0,
                    "security_status": "PROMPT_INJECTION_BLOCKED", "defense_info": scan}

        with tracer.span("route_decision", as_type="chain", input={"query": condensed_query, "selected_region": region}) as s:
            decision = decide(condensed_query, region)
            if force_route:
                decision.route, decision.reasons = force_route, [f"Route forced to {force_route} by caller."]
            s.update(output=decision.as_dict())

        runners = {
            "rag": partial(self._run_rag, system_prompt=system_prompt),
            "fixed_workflow": self._run_workflow,
            "react_agent": self._run_agent,
            "multi_agent_squad": self._run_squad,
            "policy_desk": self._run_desk,
        }
        with tracer.span(decision.route, as_type="agent" if decision.route != "rag" else "chain",
                         input={"query": condensed_query, "employee_ids": decision.employee_ids, "topics": decision.topics}) as s:
            result = await runners[decision.route](condensed_query, decision, top_k, hybrid)
            s.update(output={"answer": result["answer"], "model": result.get("model")})

        with tracer.span("output_invariant_check", as_type="guardrail", input=result["answer"],
                         metadata={"defense_layer": "L4 policy invariants"}) as s:
            inv = security_defense.verify_policy_invariants(result["answer"])
            s.update(output=inv, level=None if inv["passed"] else "WARNING")
        if inv["passed"]:
            answer, security_status = result["answer"], "VERIFIED"
        else:
            answer = f"This answer was withheld: {inv['violations'][0]}"
            security_status = "GUARDRAIL_BLOCKED"

        envelope = {
            **base,
            **result,
            "answer": answer,
            "route": decision.route,
            "route_reasons": decision.reasons,
            "region_filter": decision.region or "All",
            "security_status": security_status,
            "invariant_verification": inv,
            "latency_ms": self._ms(start_time),
        }
        self._evaluate(envelope)
        return envelope

    async def answer_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        region: Optional[str] = None,
        top_k: int = 5,
        hybrid: bool = True,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieval-only path (kept for evals and tests that pin the RAG pipeline)."""
        return await self.handle(query, chat_history, region, top_k, hybrid, force_route="rag", system_prompt=system_prompt)

    # ------------------------------------------------------------------ routes

    async def _run_rag(self, query: str, decision: RouteDecision, top_k: int, hybrid: bool,
                       system_prompt: Optional[str] = None) -> Dict[str, Any]:
        with tracer.span("hybrid_retrieval", as_type="retriever",
                         input={"query": query, "region": decision.region, "top_k": top_k, "hybrid": hybrid}) as s:
            chunks = hybrid_retriever.retrieve(query=query, region=decision.region, top_k=top_k, hybrid=hybrid)
            s.update(output=[{"chunk_id": c.get("chunk_id"), "section": c.get("section"), "region": c.get("region"),
                              "score": c.get("score"), "dense_rank": c.get("vector_rank"), "bm25_rank": c.get("bm25_rank"),
                              "text_preview": c.get("text", "")[:160]} for c in chunks])

        with tracer.span("answer_synthesis", as_type="chain", input={"query": query, "context_chunks": len(chunks)}) as s:
            synth = await llm_client.generate_response(query=query, retrieved_chunks=chunks, system_prompt=system_prompt)
            s.update(output=synth["answer"], metadata={"model": synth["model"], "is_llm": synth.get("is_llm", False)})

        usage = synth.get("usage") or {}
        return {
            "answer": synth["answer"],
            "citations": synth["citations"],
            "retrieved_chunks": chunks,
            "model": synth["model"],
            "is_llm": synth.get("is_llm", False),
            # real provider usage when an LLM answered; otherwise a rough estimate
            "tokens_used": usage.get("total_tokens") or 350 + sum(len(c["text"].split()) for c in chunks),
            "retrieval_mode": "Hybrid (ChromaDB + BM25 RRF)" if hybrid else "ChromaDB Dense Vector Only",
        }

    async def _run_workflow(self, query: str, decision: RouteDecision, top_k: int, hybrid: bool) -> Dict[str, Any]:
        emp, topic = decision.employee_ids[0], decision.topics[0]
        res = policy_orchestrator.run_deterministic_workflow(employee_id=emp, topic=topic)
        return {"answer": res["answer"], "model": "deterministic-workflow", "tokens_used": 0,
                "citations": [f"HR-207 handbook: {TOPIC_LABEL[topic]}"]}

    async def _run_agent(self, query: str, decision: RouteDecision, top_k: int, hybrid: bool) -> Dict[str, Any]:
        emp = decision.employee_ids[0]
        parts, tokens = [], 0
        for topic in decision.topics:
            with tracer.span(f"react_loop::{topic}", as_type="agent", input={"employee_id": emp, "topic": topic}) as s:
                res = await policy_orchestrator.run_react_agent_async(employee_id=emp, topic=topic, hardened=True)
                for step in res.get("trajectory", []):
                    tracer.event(f"react_step_{step['step']}::{step['action']}",
                                 input={"thought": step["thought"], "action_input": step["action_input"]},
                                 output=redact(step["observation"]))
                s.update(output=res["answer"], metadata={"steps": len(res.get("trajectory", [])),
                                                         "security_status": res.get("security_status")})
            parts.append(f"**{TOPIC_LABEL[topic].capitalize()}:** {res['answer']}")
            tokens += res.get("total_tokens", 0)
        return {"answer": "\n\n".join(parts), "model": "react-agent", "tokens_used": tokens,
                "citations": [f"HR-207 handbook: {TOPIC_LABEL[t]}" for t in decision.topics]}

    async def _run_squad(self, query: str, decision: RouteDecision, top_k: int, hybrid: bool) -> Dict[str, Any]:
        jobs = [(emp, topic) for emp in decision.employee_ids for topic in decision.topics]

        async def one(emp: str, topic: str) -> Dict[str, Any]:
            with tracer.span(f"squad::{emp}::{topic}", as_type="agent", input={"employee_id": emp, "topic": topic}) as s:
                res = await policy_orchestrator.run_multi_agent_squad_async(employee_id=emp, topic=topic)
                for hop in res.get("handoff_chain", []):
                    # the hop list carries illustrative latencies; the real ones are the tool spans
                    tracer.event(f"a2a_hop_{hop['hop']}::{hop['from']}->{hop['to']}",
                                 input=redact(hop.get("payload")), output=redact(hop.get("result")),
                                 metadata={"type": hop.get("type")})
                s.update(output=res["answer"])
                return res

        results = await asyncio.gather(*(one(e, t) for e, t in jobs))
        lines = [f"- **{e}, {TOPIC_LABEL[t]}:** {r['answer'].removeprefix('Policy Squad Verified: ')}"
                 for (e, t), r in zip(jobs, results)]
        return {"answer": "\n".join(lines), "model": "multi-agent-squad",
                "tokens_used": sum(r.get("total_tokens", 0) for r in results),
                "citations": [f"HR-207 handbook: {TOPIC_LABEL[t]}" for t in decision.topics]}

    async def _run_desk(self, query: str, decision: RouteDecision, top_k: int, hybrid: bool) -> Dict[str, Any]:
        from application.backend.capstone.engine import capstone_agent  # importing installs the MCP tool spans
        res = await capstone_agent.answer_policy_query(query=query, employee_id=decision.employee_ids[0])
        return {"answer": res.get("answer", ""), "citations": res.get("citations", []), "model": "policy-answer-desk",
                "tokens_used": res.get("tokens_used", 0), "desk_status": res.get("status"),
                "escalated": res.get("escalated", False), "ticket_id": res.get("ticket_id")}

    # ------------------------------------------------------------------ evaluators

    @staticmethod
    def _evaluate(env: Dict[str, Any]) -> None:
        """W4 failure separation + W5 taxonomy + W6 citation grounding, each stored as a score."""
        chunks = env.get("retrieved_chunks") or []
        if env["route"] == "rag":
            with tracer.span("eval::failure_taxonomy", as_type="evaluator") as s:
                label = telemetry_service._classify(env)
                s.update(output={"label": label, "severity": SEVERITY_WEIGHTS.get(label, 0)},
                         metadata={"rule": "refusal with chunks = generation failure; no chunks = retrieval failure"})
            tracer.score("failure_severity", SEVERITY_WEIGHTS.get(label, 0), label)

            with tracer.span("eval::citation_grounding", as_type="evaluator") as s:
                retrieved = {c.get("section") for c in chunks}
                cited = env.get("citations") or []
                grounded = [c for c in cited if any(c.startswith(sec or "") or (sec or "") in c for sec in retrieved)]
                refused = env["answer"] == MANDATED_REFUSAL_PHRASE
                value = 1.0 if refused or (cited and len(grounded) == len(cited)) else (len(grounded) / len(cited) if cited else 0.0)
                s.update(output={"cited": cited, "grounded": grounded, "refused": refused, "score": value})
            tracer.score("citation_grounding", value, "refusal" if refused else f"{len(grounded)}/{len(cited)} citations in retrieved sections")

            if chunks:
                tracer.score("retrieval_top_rrf", chunks[0].get("score", 0.0), chunks[0].get("section"))
        else:
            label = "CORRECT" if env.get("answer") and "not found" not in env["answer"].lower() else "PIPELINE_ERROR"
            tracer.score("failure_severity", SEVERITY_WEIGHTS.get(label, 0), label)
        tracer.score("guardrail_passed", 1.0 if env["security_status"] == "VERIFIED" else 0.0, env["security_status"])

    @staticmethod
    def _ms(start: float) -> float:
        return round((time.perf_counter() - start) * 1000, 2)


chat_service = ChatService()
