"""Multi-Turn Chat Service with Asynchronous Synthesis and Query Condensation."""

import time
import uuid
import re
from typing import List, Dict, Any, Optional, Tuple
from application.backend.retrieval.engine import hybrid_retriever
from application.backend.security.defense import security_defense
from application.backend.chat.llm import llm_client, MANDATED_REFUSAL_PHRASE
from application.backend.core.config import settings


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
            match = re.search(r"(?:what|how)\s+about\s+(?:in\s+)?(?:the\s+)?([A-Za-z0-9\s]+)\??", lower_q)
            if match:
                new_target = match.group(1).strip().upper()
                for reg in ["US", "UK", "EMEA", "APAC", "LATAM", "NA"]:
                    if reg in prev_user_q.upper():
                        condensed = re.sub(rf"\b{reg}\b", new_target, prev_user_q, flags=re.IGNORECASE)
                        return condensed, True
                return f"{prev_user_q} in {new_target}", True

        if "does that apply" in lower_q or "what is it for" in lower_q:
            return f"{prev_user_q} (context: {query})", True

        return query, False

    async def answer_query(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        region: Optional[str] = None,
        top_k: int = 5,
        hybrid: bool = True
    ) -> Dict[str, Any]:
        """Asynchronously processes a chat inquiry through condensation, hybrid retrieval, and synthesis."""
        start_time = time.perf_counter()
        trace_id = str(uuid.uuid4())
        history = chat_history or []

        # 1. Query Condensation
        condensed_query, was_condensed = self.condense_query(query, history)

        # 2. Check for Prompt Injections in Query
        query_scan = security_defense.scan_for_injections(condensed_query)
        if query_scan["is_attack"]:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return {
                "trace_id": trace_id,
                "answer": "Security Alert: Prompt injection signature detected in user input. Request rejected.",
                "condensed_query": condensed_query,
                "was_condensed": was_condensed,
                "retrieved_chunks": [],
                "citations": [],
                "latency_ms": latency_ms,
                "tokens_used": 120,
                "security_status": "PROMPT_INJECTION_BLOCKED",
                "defense_info": query_scan
            }

        # 3. Hybrid Retrieval (ChromaDB HNSW + BM25 with LRU Cache)
        retrieved_chunks = hybrid_retriever.retrieve(
            query=condensed_query,
            region=region,
            top_k=top_k,
            hybrid=hybrid
        )

        # 4. Asynchronous Synthesis
        synthesis_result = await llm_client.generate_response(
            query=condensed_query,
            retrieved_chunks=retrieved_chunks
        )
        raw_answer = synthesis_result["answer"]
        citations = synthesis_result["citations"]

        # 5. Invariant Guardrail Verification
        inv_check = security_defense.verify_policy_invariants(raw_answer)
        if not inv_check["passed"]:
            final_answer = f"Security Notice: Answer blocked by policy invariant violation: {inv_check['violations'][0]}"
            security_status = "GUARDRAIL_BLOCKED"
        else:
            final_answer = raw_answer
            security_status = "VERIFIED"

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        total_tokens = 350 + sum(len(c["text"].split()) for c in retrieved_chunks)

        return {
            "trace_id": trace_id,
            "answer": final_answer,
            "condensed_query": condensed_query,
            "was_condensed": was_condensed,
            "retrieved_chunks": retrieved_chunks,
            "citations": citations,
            "latency_ms": latency_ms,
            "tokens_used": total_tokens,
            "region_filter": region or "All",
            "retrieval_mode": "Hybrid (ChromaDB + BM25 RRF)" if hybrid else "ChromaDB Dense Vector Only",
            "security_status": security_status,
            "model": synthesis_result["model"],
            "invariant_verification": inv_check
        }


chat_service = ChatService()
