"""Week 6: Query Condensation & Transformation Engine.

Rewrites conversational follow-up questions into standalone, context-complete
search queries before vector/hybrid retrieval.
"""

from typing import List, Dict, Any


def condense_followup_query(current_query: str, chat_history: List[Dict[str, str]]) -> str:
    """Condenses a follow-up question into a standalone query.
    
    If chat_history is empty or the query is already self-contained, returns current_query.
    Otherwise, resolves coreferences and elided subjects.
    """
    if not chat_history:
        return current_query

    # Rule-based / heuristic extraction for common follow-up patterns
    lower_q = current_query.lower().strip()
    last_turn = chat_history[-1]
    prev_user_q = last_turn.get("user", "")

    # Pattern: "What about [region/subject]?" or "How about in the UK?"
    if lower_q.startswith("what about") or lower_q.startswith("how about") or "what about in" in lower_q:
        import re
        target_match = re.search(r"(?:what|how)\s+about\s+(?:in\s+)?(?:the\s+)?([A-Za-z0-9\s]+)\??", lower_q)
        if target_match:
            new_target = target_match.group(1).strip().upper()
            # Replace previous region or append
            for reg in ["US", "UK", "EMEA", "APAC", "LATAM", "NA"]:
                if reg in prev_user_q.upper():
                    # Substitute region in previous question
                    condensed = re.sub(rf"\b{reg}\b", new_target, prev_user_q, flags=re.IGNORECASE)
                    return condensed
            return f"{prev_user_q} in {new_target}"

    # Pattern: "Does that apply to probationary employees?"
    if "does that apply" in lower_q or "what is it for" in lower_q:
        return f"{prev_user_q} (specifically for: {current_query})"

    return current_query
