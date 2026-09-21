"""Fixed workflow implementation for HR policy entitlement queries.

Re-implements the identical task as a deterministic fixed sequence:
  Step 1: Extract employee ID and call `get_employee_record`.
  Step 2: Identify topic and call `get_handbook_rule`.
  Step 3: If conditional statutory rules apply, call `get_jurisdiction_rules`.
  Step 4: Single LLM synthesis call over the assembled facts.

No while loop. No dynamic model tool selection. Deterministic, auditable,
fast, and cost-effective.
"""

import json
import time
from typing import Any, Dict, List, Optional

from policy_rag.agent.enums import JurisdictionEnum, PolicyTopicEnum
from policy_rag.agent.llm import call_llm, count_tokens
from policy_rag.agent.tools import (
    get_employee_record,
    get_handbook_rule,
    get_jurisdiction_rules,
)


class FixedWorkflow:
    """Fixed-pipeline executor for HR entitlement questions."""

    INPUT_COST_PER_MILLION: float = 0.15
    OUTPUT_COST_PER_MILLION: float = 0.60

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _extract_employee_id(self, query: str) -> Optional[str]:
        """Extracts employee ID formatted as EMP-XXX from the question."""
        for token in query.replace("(", " ").replace(")", " ").replace("?", " ").replace(",", " ").split():
            if token.upper().startswith("EMP-"):
                return token.upper()
        return None

    def _extract_topic(self, query: str, hours_per_week: float = 40.0) -> PolicyTopicEnum:
        """Determines the specific policy topic from the question text."""
        q_lower = query.lower()
        if "notice" in q_lower:
            return PolicyTopicEnum.NOTICE_PERIOD
        elif "sabbatical" in q_lower:
            return PolicyTopicEnum.SABBATICAL
        elif "part-time" in q_lower or "part time" in q_lower or hours_per_week < 40:
            return PolicyTopicEnum.PART_TIME_RULE
        elif "borrow" in q_lower or "negative" in q_lower:
            return PolicyTopicEnum.BORROWING_NEGATIVE_BALANCE
        elif "termination" in q_lower or "payout" in q_lower or "california" in q_lower:
            return PolicyTopicEnum.TERMINATION_PAYOUT
        else:
            return PolicyTopicEnum.CARRY_OVER_CAP

    def run(self, query: str) -> Dict[str, Any]:
        """Executes the fixed 4-step workflow without any loops."""
        start_time = time.time()
        steps: List[Dict[str, Any]] = []

        if self.verbose:
            print(f"\n[Fixed Workflow Started] Query: '{query}'")

        # Step 1: Employee Record Lookup
        emp_id = self._extract_employee_id(query)
        if not emp_id:
            emp_id = "EMP-101"  # Default fallback if unspecified

        step1_result = get_employee_record(emp_id)
        steps.append({
            "step": 1,
            "name": "get_employee_record",
            "args": {"employee_id": emp_id},
            "result": step1_result,
        })
        if self.verbose:
            print(f"  Step 1: Looked up employee record for {emp_id}")

        emp_info = step1_result.get("employee")
        if not emp_info:
            return {
                "status": "error",
                "answer": f"Employee record for {emp_id} not found.",
                "steps": steps,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_cost": 0.0,
                "latency_ms": round((time.time() - start_time) * 1000.0, 2),
                "laps": 0,
            }

        jurisdiction_str = emp_info["jurisdiction"]
        jurisdiction = JurisdictionEnum(jurisdiction_str)
        topic = self._extract_topic(query, emp_info.get("hours_per_week", 40.0))

        # Step 2: Company Policy Handbook Lookup
        step2_result = get_handbook_rule(jurisdiction, topic.value)
        steps.append({
            "step": 2,
            "name": "get_handbook_rule",
            "args": {"jurisdiction": jurisdiction.value, "section_or_topic": topic.value},
            "result": step2_result,
        })
        if self.verbose:
            print(f"  Step 2: Fetched handbook rule for {jurisdiction.value} -> {topic.value}")

        # Step 3: Statutory Jurisdiction Rules (Conditional Branching Step)
        q_lower = query.lower()
        needs_statutory = (
            (jurisdiction == JurisdictionEnum.UK and topic == PolicyTopicEnum.NOTICE_PERIOD)
            or (jurisdiction == JurisdictionEnum.US and (topic == PolicyTopicEnum.TERMINATION_PAYOUT or "california" in q_lower or emp_info.get("sub_region") == "California"))
            or (jurisdiction == JurisdictionEnum.EMEA and topic == PolicyTopicEnum.SABBATICAL)
            or (jurisdiction == JurisdictionEnum.APAC and topic == PolicyTopicEnum.NOTICE_PERIOD)
        )

        step3_result = None
        if needs_statutory:
            step3_result = get_jurisdiction_rules(jurisdiction, topic)
            steps.append({
                "step": 3,
                "name": "get_jurisdiction_rules",
                "args": {"jurisdiction": jurisdiction.value, "topic": topic.value},
                "result": step3_result,
            })
            if self.verbose:
                print(f"  Step 3: Fetched statutory rules for {jurisdiction.value} -> {topic.value}")
        else:
            steps.append({
                "step": 3,
                "name": "get_jurisdiction_rules",
                "skipped": True,
                "reason": "Statutory override not triggered by employee jurisdiction or topic",
            })
            if self.verbose:
                print("  Step 3: Statutory override check skipped (standard handbook applies)")

        # Step 4: Single LLM Synthesis Step
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an expert HR Policy Entitlement assistant. Given the retrieved evidence, "
                    "answer the employee question with high accuracy, citing relevant handbook sections and statutory statutes."
                ),
            },
            {"role": "user", "content": query},
            {
                "role": "tool",
                "name": "get_employee_record",
                "content": json.dumps(step1_result),
            },
            {
                "role": "tool",
                "name": "get_handbook_rule",
                "content": json.dumps(step2_result),
            },
        ]
        if step3_result:
            messages.append({
                "role": "tool",
                "name": "get_jurisdiction_rules",
                "content": json.dumps(step3_result),
            })

        # Single LLM call without tool schemas (tools were executed deterministically)
        llm_resp = call_llm(messages=messages, tools=None)

        prompt_tokens = llm_resp.prompt_tokens
        completion_tokens = llm_resp.completion_tokens
        total_tokens = prompt_tokens + completion_tokens

        cost = (
            (prompt_tokens * (self.INPUT_COST_PER_MILLION / 1_000_000.0))
            + (completion_tokens * (self.OUTPUT_COST_PER_MILLION / 1_000_000.0))
        )
        elapsed_ms = (time.time() - start_time) * 1000.0

        steps.append({
            "step": 4,
            "name": "llm_synthesis",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        })

        if self.verbose:
            print(f"  Step 4: Final answer synthesized (Tokens: {total_tokens}, Cost: ${cost:.6f})")

        return {
            "status": "success",
            "answer": llm_resp.content or "",
            "steps": steps,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_cost": round(cost, 6),
            "latency_ms": round(elapsed_ms, 2),
            "laps": 1,  # Single pass, no loops
        }
