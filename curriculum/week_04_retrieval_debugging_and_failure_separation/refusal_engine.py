"""Week 4: Deterministic Refusal Prompt Engine.

Ensures that LLMs do not invent policies for questions outside the corpus,
mandating a deterministic refusal phrase.
"""

MANDATED_REFUSAL_PHRASE = "I cannot answer this question based on the provided HR-207 policy documentation."

SYSTEM_PROMPT_TEMPLATE = f"""You are an authoritative policy assistant for HR-207 leave policies.
Answer questions SOLELY based on the provided retrieved policy sections.

CRITICAL RULES:
1. Cite the exact section for every claim using the format [[HR-207 Section X.Y]].
2. If the context does NOT contain sufficient factual evidence to answer the question with certainty, you MUST respond with the exact sentence:
   "{MANDATED_REFUSAL_PHRASE}"
3. Do NOT extrapolate, guess, or use external knowledge under any circumstances.
"""


def format_context_prompt(query: str, retrieved_chunks: list) -> str:
    context_str = "\n\n".join([
        f"--- Source: {c.get('filename')} ({c.get('section', 'Unknown Section')}) ---\n{c.get('text', '')}"
        for c in retrieved_chunks
    ])
    
    return f"{SYSTEM_PROMPT_TEMPLATE}\n\nRETRIEVED CONTEXT:\n{context_str}\n\nUSER QUESTION: {query}\n\nANSWER:"
