"""Hand-built ReAct agent loop with visible steps and 4-budget enforcement.

The agent works in an explicit loop:
  Plan / Think -> Act (call tool) -> Observe (tool result) -> Repeat until done.

Every step is logged visibly. All four budgets (max iterations, max tokens,
max cost, wall-clock time) are strictly checked on every lap.
Per-lap tokens are summed cumulatively because each lap re-sends the entire
history to the LLM.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

from policy_rag.agent.budgets import BudgetTracker, BudgetExceededError
from policy_rag.agent.llm import call_llm
from policy_rag.agent.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger("policy_rag.agent.loop")


AGENT_SYSTEM_PROMPT = (
    "You are an expert HR Policy Entitlement Agent. "
    "Your objective is to answer employee entitlement questions accurately based on company policy and statutory regulations.\n"
    "You have access to three specific tools:\n"
    "1. get_employee_record: Fetch demographic, jurisdiction, tenure, and leave balance details for an employee ID.\n"
    "2. get_handbook_rule: Fetch standard HR-207 corporate policy handbook text, tier tables, and caps for a jurisdiction and policy topic.\n"
    "3. get_jurisdiction_rules: Fetch statutory labor regulations and government legal overrides for a jurisdiction and policy topic.\n\n"
    "Work methodically in steps:\n"
    "- First inspect the employee's personal record.\n"
    "- Next check the relevant handbook rule for their jurisdiction and question topic.\n"
    "- If statutory law may override handbook policy (e.g. tenure-based statutory notice in the UK, wage protection in California, or statutory sabbaticals in EMEA), check jurisdiction statutory rules.\n"
    "- Finally, provide a clear, concise, and fully substantiated answer citing policy and statutory sections."
)


class HRAgent:
    """Hand-built ReAct agent executing transparent multi-step loops."""

    def __init__(
        self,
        system_prompt: str = AGENT_SYSTEM_PROMPT,
        tools: Optional[List[Dict[str, Any]]] = None,
        verbose: bool = True,
    ):
        self.system_prompt = system_prompt
        self.tools = tools if tools is not None else TOOL_DEFINITIONS
        self.verbose = verbose

    def run(
        self,
        query: str,
        max_iterations: int = 6,
        max_tokens: int = 8000,
        max_cost: float = 0.05,
        max_time_seconds: float = 15.0,
    ) -> Dict[str, Any]:
        """Runs the agent loop with all 4 budgets strictly enforced."""
        tracker = BudgetTracker(
            max_iterations=max_iterations,
            max_tokens=max_tokens,
            max_cost=max_cost,
            max_time_seconds=max_time_seconds,
        )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query},
        ]

        steps: List[Dict[str, Any]] = []
        final_answer: str = ""
        termination_reason: str = "completed"

        if self.verbose:
            print(f"\n[Agent Started] Query: '{query}'")
            print(f"[Budgets] max_iters={max_iterations}, max_tokens={max_tokens}, max_cost=${max_cost}, max_time={max_time_seconds}s")

        try:
            while True:
                # 1. Pre-lap budget check (checks wall-clock, max_iterations, accumulated tokens, accumulated cost)
                tracker.check_pre_lap()
                current_lap = tracker.iterations + 1

                if self.verbose:
                    print(f"\n--- [Lap {current_lap}] Thinking ---")

                # 2. ReAct Model Step
                response = call_llm(messages=messages, tools=self.tools)

                # 3. Record tokens and check post-lap token/cost limits
                tracker.record_lap(
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                )

                if self.verbose:
                    print(f"  Thought: {response.content}")
                    print(f"  Lap Usage: prompt={response.prompt_tokens} compl={response.completion_tokens} (Total: {tracker.total_tokens} tokens, ${tracker.total_cost:.6f})")

                # 4. Handle Tool Calls
                if response.has_tool_calls:
                    # Append assistant message with tool calls to context
                    assistant_msg = {
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                    }
                    messages.append(assistant_msg)

                    lap_tool_steps = []
                    for tc in response.tool_calls:
                        tool_name = tc["function"]["name"]
                        raw_args = tc["function"]["arguments"]
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                        if self.verbose:
                            print(f"  Action: Call `{tool_name}` with args: {args}")

                        # Execute tool
                        result = execute_tool(tool_name, args)

                        if self.verbose:
                            preview = json.dumps(result)
                            if len(preview) > 120:
                                preview = preview[:117] + "..."
                            print(f"  Observation: {preview}")

                        lap_tool_steps.append({
                            "tool": tool_name,
                            "args": args,
                            "result": result,
                        })

                        # Append tool observation to message history
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.get("id", "call_0"),
                            "name": tool_name,
                            "content": json.dumps(result),
                        })

                    steps.append({
                        "lap": current_lap,
                        "type": "tool_execution",
                        "thought": response.content,
                        "tool_actions": lap_tool_steps,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                    })

                else:
                    # Final synthesis completed
                    final_answer = response.content or ""
                    if self.verbose:
                        print(f"\n[Final Answer Received at Lap {current_lap}]:\n{final_answer}")

                    steps.append({
                        "lap": current_lap,
                        "type": "final_answer",
                        "thought": None,
                        "answer": final_answer,
                        "prompt_tokens": response.prompt_tokens,
                        "completion_tokens": response.completion_tokens,
                    })
                    break

        except BudgetExceededError as exc:
            termination_reason = "budget_exceeded"
            final_answer = f"Terminated early: {exc}"
            if self.verbose:
                print(f"\n{exc}")
            steps.append({
                "lap": tracker.iterations,
                "type": "budget_exceeded",
                "budget_name": exc.budget_name,
                "limit": exc.limit,
                "current": exc.current,
            })

        return {
            "status": "success" if termination_reason == "completed" else "budget_exceeded",
            "termination_reason": termination_reason,
            "answer": final_answer,
            "steps": steps,
            "total_tokens": tracker.total_tokens,
            "prompt_tokens": tracker.total_prompt_tokens,
            "completion_tokens": tracker.total_completion_tokens,
            "total_cost": round(tracker.total_cost, 6),
            "latency_ms": round(tracker.elapsed_seconds * 1000.0, 2),
            "laps": tracker.iterations,
            "budgets": tracker.summary(),
        }
