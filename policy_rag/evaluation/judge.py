"""Track C HR Policy-Answer Judge: Rule assertions and LLM-as-judge evaluation.

Evaluates RAG answers against policy ground truth using:
1. Rule-based assertion checks (free, deterministic, run first):
   - Exact refusal sentinel check
   - Source document retrieval in top-3 chunks
   - Citation format syntax
2. Policy-Answer Judge (G-Eval / RAGAS inspired criteria):
   - Faithfulness / Groundedness (context-supported claims)
   - Policy Accuracy / Entitlement correctness (specific numbers, caps, eligibility)
   - Refusal Safety (out-of-corpus handling without hallucinations)
"""

import json
import re
from typing import Optional

from policy_rag import config
from policy_rag.evaluation.datasets import GoldenQuery


# Citation pattern: [[Section]](chunk_id:file) or [[file]]
CITATION_REGEX = re.compile(r"\[\[.*?\]\](?:\(.*?\))?")


def check_refusal_assertion(answer_text: str, is_refusal: bool, expected_type: str) -> dict:
    """Checks whether refusal behavior matches expectation."""
    has_refusal_phrase = config.REFUSAL_SENTINEL.lower() in (answer_text or "").lower()
    actual_refused = bool(is_refusal or has_refusal_phrase)

    if expected_type == "refusal":
        passed = actual_refused
        reason = (
            "Correct refusal sentinel present"
            if passed
            else "Failed to refuse out-of-corpus question (hallucination risk)"
        )
    else:
        passed = not actual_refused
        reason = (
            "Properly attempted to answer in-corpus question"
            if passed
            else "Eager refusal triggered on answerable question"
        )
    return {"passed": passed, "actual_refused": actual_refused, "reason": reason}


def check_citation_assertion(answer_text: str, expected_type: str) -> dict:
    """Checks whether the answer contains formatted policy citations."""
    if expected_type == "refusal":
        # Refusal answers are not expected to contain citations
        return {"passed": True, "reason": "Refusals do not require citations"}

    has_citation = bool(CITATION_REGEX.search(answer_text or ""))
    return {
        "passed": has_citation,
        "reason": "Citation found in answer" if has_citation else "Missing [[Policy]](...) citation syntax",
    }


def check_source_assertion(retrieved_chunks: list, expected_source: Optional[str]) -> dict:
    """Checks whether the expected policy document was retrieved in the top chunks."""
    if not expected_source:
        return {"passed": True, "reason": "No single source expected"}

    top_sources = [c.get("source_file") for c in (retrieved_chunks or [])[:3]]
    passed = expected_source in top_sources
    return {
        "passed": passed,
        "top_sources": top_sources,
        "reason": f"Expected source {expected_source} present in top 3" if passed else f"Expected source {expected_source} missing from top 3 {top_sources}",
    }


def run_rule_assertions(trace: dict, golden: GoldenQuery) -> dict:
    """Runs all deterministic rule assertions before calling any LLM judge."""
    answer_text = trace.get("answer", "")
    is_refusal = trace.get("is_refusal", False)
    retrieved_chunks = trace.get("retrieved_chunks", [])

    refusal_check = check_refusal_assertion(answer_text, is_refusal, golden.expected_type)
    citation_check = check_citation_assertion(answer_text, golden.expected_type)
    source_check = check_source_assertion(retrieved_chunks, golden.expected_source)

    all_passed = refusal_check["passed"] and citation_check["passed"] and source_check["passed"]

    return {
        "passed": all_passed,
        "refusal_check": refusal_check,
        "citation_check": citation_check,
        "source_check": source_check,
    }


JUDGE_SYSTEM_PROMPT = """You are an expert HR Policy Compliance Judge evaluating an AI assistant's answer.
You evaluate the answer against the retrieved context and the expected policy facts.

Scoring Criteria:
1. Faithfulness (1-5): Is every claim in the answer directly grounded in the provided context?
2. Policy Accuracy (1-5): Does the answer state the exact numbers, eligibility thresholds, employee classes, and conditions required by the policy?
3. Refusal Safety (1-5): If the question asks for a policy not present in the context, did it safely refuse instead of making up numbers?

Rating Rubric:
- 5: Excellent. Completely grounded, exact figures and conditions, proper citations.
- 4: Good. Accurate on all material facts; minor phrasing nuance only.
- 3: Incomplete/Marginal. Answer is partially correct but missed an essential qualification, penalty clause, or prerequisite definition.
- 2: Poor. Misinterpreted the rule or cited facts for the wrong employee tier.
- 1: Critical Error. Confidently invented numbers, cited the wrong region's rules, or failed to refuse out-of-corpus queries.

Binary Verdict:
- PASS: Score >= 4 AND all expected facts/conditions correctly handled.
- FAIL: Score <= 3 OR any material inaccuracy/hallucination/missing precondition.
"""


def _mock_judge_evaluate(trace: dict, golden: GoldenQuery, assertions: dict) -> dict:
    """Deterministic offline judge used when OPENROUTER_API_KEY is unset or for test runs."""
    answer_text = (trace.get("answer") or "").lower()
    golden_type = golden.expected_type

    if not assertions["passed"]:
        return {
            "score": 1 if golden_type == "refusal" else 2,
            "verdict": "FAIL",
            "faithfulness": 2,
            "policy_accuracy": 2,
            "reasoning": f"Failed rule assertions: {assertions['refusal_check']['reason']}; {assertions['source_check']['reason']}",
            "judge_model": "mock-judge",
        }

    if golden_type == "refusal":
        return {
            "score": 5,
            "verdict": "PASS",
            "faithfulness": 5,
            "policy_accuracy": 5,
            "reasoning": "Correctly and safely refused out-of-corpus question without fabricating policies.",
            "judge_model": "mock-judge",
        }

    expected_facts = [f.lower() for f in golden.expected_facts]
    if not expected_facts:
        return {
            "score": 4,
            "verdict": "PASS",
            "faithfulness": 4,
            "policy_accuracy": 4,
            "reasoning": "Answer retrieved from correct source and passed rule assertions.",
            "judge_model": "mock-judge",
        }

    facts_matched = [f for f in expected_facts if f in answer_text]
    match_ratio = len(facts_matched) / len(expected_facts)

    if match_ratio == 1.0:
        score = 5
        verdict = "PASS"
        reasoning = f"All {len(expected_facts)} expected policy facts present and verified."
    elif match_ratio >= 0.5:
        score = 3
        verdict = "FAIL"
        missing = [f for f in expected_facts if f not in answer_text]
        reasoning = f"Partially accurate ({int(match_ratio*100)}% facts). Missing key policy condition(s): {missing}"
    else:
        score = 2
        verdict = "FAIL"
        reasoning = f"Missing core policy facts: expected {expected_facts}."

    return {
        "score": score,
        "verdict": verdict,
        "faithfulness": 4 if verdict == "PASS" else 3,
        "policy_accuracy": score,
        "reasoning": reasoning,
        "judge_model": "mock-judge",
    }


def evaluate_with_llm(trace: dict, golden: GoldenQuery, assertions: dict) -> dict:
    """Evaluates an answer using an LLM-as-judge via OpenRouter, falling back to mock."""
    api_key = config.openrouter_api_key()
    if not api_key:
        return _mock_judge_evaluate(trace, golden, assertions)

    import httpx

    context_snippets = "\n".join(
        f"- [Chunk {c['rank']}] ({c['source_file']}): {c['text_preview']}"
        for c in trace.get("retrieved_chunks", [])
    )

    user_prompt = f"""Question: {golden.query}
Region Filter: {golden.region or 'None'}
Expected Type: {golden.expected_type}
Expected Source: {golden.expected_source or 'None'}
Key Required Facts/Conditions: {list(golden.expected_facts)}

Retrieved Context Snippets:
{context_snippets}

Assistant's Answer to Grade:
\"\"\"{trace.get('answer', '')}\"\"\"

Provide your judgment in JSON format with keys:
- "score": integer 1-5
- "verdict": "PASS" or "FAIL"
- "faithfulness": integer 1-5
- "policy_accuracy": integer 1-5
- "reasoning": "brief explanation"
"""
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config.LLM_MODEL_NAME,
            "messages": [
                {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }
        resp = httpx.post(
            f"{config.OPENROUTER_BASE_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            parsed["judge_model"] = config.LLM_MODEL_NAME
            return parsed
    except Exception:
        pass

    return _mock_judge_evaluate(trace, golden, assertions)


def judge_answer(trace: dict, golden: GoldenQuery) -> dict:
    """Complete evaluation pipeline: runs rule assertions first, then the policy judge."""
    assertions = run_rule_assertions(trace, golden)
    judge_result = evaluate_with_llm(trace, golden, assertions)

    final_verdict = "PASS" if (assertions["passed"] and judge_result.get("verdict") == "PASS") else "FAIL"

    return {
        "golden_id": golden.id,
        "query": golden.query,
        "problem_type": golden.problem_type,
        "expected_type": golden.expected_type,
        "assertions": assertions,
        "score": judge_result.get("score", 1),
        "verdict": final_verdict,
        "faithfulness": judge_result.get("faithfulness", 1),
        "policy_accuracy": judge_result.get("policy_accuracy", 1),
        "reasoning": judge_result.get("reasoning", ""),
        "judge_model": judge_result.get("judge_model", "mock-judge"),
    }
