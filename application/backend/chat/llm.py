"""Asynchronous LLM Client & High-Precision Synthesis Pipeline."""

import re
import os
from typing import List, Dict, Any, Optional
import httpx
from application.backend.core.config import settings
from application.backend.observability.langfuse_telemetry import capstone_telemetry as tracer

MANDATED_REFUSAL_PHRASE = "I cannot answer this question based on the provided HR-207 policy documentation."

SYSTEM_PROMPT = f"""You are the authoritative policy assistant for HR-207 leave policies.
Answer questions SOLELY based on the provided retrieved policy sections.

CRITICAL INSTRUCTIONS:
1. Cite the exact policy section for every claim using [[HR-207 Section X.Y]].
2. If the retrieved context does NOT contain the factual evidence needed to answer the question with certainty, you MUST respond with the exact sentence:
   "{MANDATED_REFUSAL_PHRASE}"
3. Do NOT extrapolate or guess under any circumstances.
"""


class AsyncLLMClient:
    """Production asynchronous LLM client with OpenRouter API and offline semantic fallback."""

    def __init__(self):
        self.api_key = settings.openrouter_api_key
        self.model = settings.default_llm_model

    async def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generates an answer from retrieved context using OpenRouter or offline high-precision extraction."""
        if not retrieved_chunks:
            return {
                "answer": MANDATED_REFUSAL_PHRASE,
                "citations": [],
                "model": "rule-refusal",
                "is_llm": False
            }

        # Format context
        context_str = "\n\n".join([
            f"--- [{c.get('section', 'General')}] (Region: {c.get('region', 'Unknown')}) ---\n{c.get('text', '')}"
            for c in retrieved_chunks
        ])

        # 1. If API key is available, call OpenRouter or Groq asynchronously
        api_key = settings.groq_api_key or self.api_key
        if api_key and len(api_key.strip()) > 10:
            try:
                # Groq overrides OpenRouter if available
                if settings.groq_api_key:
                    endpoint = "https://api.groq.com/openai/v1/chat/completions"
                    model_to_use = getattr(settings, "groq_model", "openai/gpt-oss-20b")
                    headers = {"Authorization": f"Bearer {api_key}"}
                else:
                    endpoint = "https://openrouter.ai/api/v1/chat/completions"
                    model_to_use = self.model
                    headers = {
                        "Authorization": f"Bearer {api_key}",
                        "HTTP-Referer": "https://enterprise-policy-assistant.internal",
                        "X-Title": "HR-207 Policy Assistant"
                    }
                    
                import asyncio
                import requests

                payload = {
                    "model": model_to_use,
                    "temperature": settings.llm_temperature,
                    "max_tokens": settings.llm_max_tokens,
                    "messages": [
                        {"role": "system", "content": system_prompt or SYSTEM_PROMPT},
                        {"role": "user", "content": f"RETRIEVED CONTEXT:\n{context_str}\n\nUSER QUESTION: {query}"}
                    ]
                }

                def _call_api():
                    return requests.post(endpoint, headers=headers, json=payload, timeout=25)

                provider = "groq" if settings.groq_api_key else "openrouter"
                params = {"temperature": payload["temperature"], "max_tokens": payload["max_tokens"], "timeout_s": 25}
                with tracer.span("llm_call", as_type="generation", input=payload["messages"],
                                 metadata={"provider": provider, "endpoint": endpoint}) as gen:
                    gen.update(model=model_to_use, model_parameters=params)
                    response = await asyncio.to_thread(_call_api)
                    gen.update(metadata={"http_status": response.status_code,
                                         "provider_latency_ms": round(response.elapsed.total_seconds() * 1000, 2)})
                    if response.status_code == 200:
                        res_json = response.json()
                        choice = res_json["choices"][0]
                        answer = choice["message"]["content"].strip()
                        citations = re.findall(r"\[\[(.*?)\]\]", answer)
                        usage = res_json.get("usage") or {}
                        gen.update(
                            output=answer,
                            usage={"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)} if usage else None,
                            metadata={"finish_reason": choice.get("finish_reason"), "provider_response_id": res_json.get("id"),
                                      "provider_model": res_json.get("model")},
                        )
                        return {
                            "answer": answer,
                            "citations": citations,
                            "model": model_to_use,
                            "is_llm": True,
                            "usage": res_json.get("usage")
                        }
                    gen.update(level="ERROR", status_message=f"HTTP {response.status_code}: {response.text[:500]}")
                print(f"[-] LLM API Error: {response.status_code} - {response.text}")
            except Exception as e:
                print(f"[-] LLM Exception: {str(e)}")
                # Log and proceed to high-precision factual extractor fallback
                pass
        else:
            tracer.event("llm_not_configured", metadata={"reason": "no GROQ_API_KEY or OPENROUTER_API_KEY"}, level="WARNING")

        tracer.event("offline_fallback_used", level="WARNING",
                     metadata={"reason": "LLM call unavailable or failed; answering by sentence extraction"})

        # 2. High-Precision Offline Semantic Extractor (when no API key or network down)
        top_chunk = retrieved_chunks[0]
        section_tag = top_chunk.get("section", "HR-207 Policy")
        reg = top_chunk.get("region", "US")
        text = top_chunk.get("text", "")

        # Check refusal triggers
        unrelated = ["maternity", "paternity", "parental leave duration", "gym", "dental", "bonus percentage"]
        if any(u in query.lower() for u in unrelated):
            return {
                "answer": MANDATED_REFUSAL_PHRASE,
                "citations": [],
                "model": "offline-deterministic",
                "is_llm": False
            }

        # Extract sentences directly related to query tokens
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        relevant_sentences = []
        query_words = set(re.findall(r"\w+", query.lower()))

        for s in sentences:
            s_words = set(re.findall(r"\w+", s.lower()))
            overlap = len(query_words.intersection(s_words))
            if overlap >= 2:
                relevant_sentences.append((overlap, s))

        relevant_sentences.sort(key=lambda x: x[0], reverse=True)
        if relevant_sentences:
            extracted_text = " ".join([s for _, s in relevant_sentences[:2]])
            answer = f"According to {section_tag} for {reg}: {extracted_text} [[{section_tag}]]"
            citations = [section_tag]
            return {
                "answer": answer,
                "citations": citations,
                "model": "offline-semantic-extractor",
                "is_llm": False
            }
        else:
            return {
                "answer": MANDATED_REFUSAL_PHRASE,
                "citations": [],
                "model": "offline-deterministic",
                "is_llm": False
            }


llm_client = AsyncLLMClient()
