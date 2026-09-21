"""Budget tracking and enforcement for the hand-built agent loop.

Enforces all four budgets:
1. `max_iterations`: Maximum loop laps allowed.
2. `max_tokens`: Total cumulative tokens (prompt + completion across ALL laps).
3. `max_cost`: Total dollar cost accumulated across all laps.
4. `wall_clock`: Maximum elapsed wall-clock seconds before early termination.
"""

import time
from typing import Optional


class BudgetExceededError(Exception):
    """Raised when any of the four operational budgets is exhausted."""

    def __init__(self, budget_name: str, limit: float, current: float, lap: int):
        self.budget_name = budget_name
        self.limit = limit
        self.current = current
        self.lap = lap
        super().__init__(
            f"[BUDGET EXCEEDED] {budget_name} exceeded at lap {lap}: "
            f"current={current:.4f} limit={limit:.4f}. Terminating cleanly."
        )


class BudgetTracker:
    """Tracks cumulative usage against all four operational budgets."""

    # Default pricing per 1,000,000 tokens (Gemini Flash Lite / Tier baseline)
    INPUT_COST_PER_MILLION: float = 0.15
    OUTPUT_COST_PER_MILLION: float = 0.60

    def __init__(
        self,
        max_iterations: int = 6,
        max_tokens: int = 8000,
        max_cost: float = 0.05,
        max_time_seconds: float = 15.0,
    ):
        self.max_iterations = max_iterations
        self.max_tokens = max_tokens
        self.max_cost = max_cost
        self.max_time_seconds = max_time_seconds

        self.iterations: int = 0
        self.total_prompt_tokens: int = 0
        self.total_completion_tokens: int = 0
        self.total_tokens: int = 0
        self.total_cost: float = 0.0
        self.start_time: float = time.time()
        self.last_check_time: float = self.start_time

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    def check_pre_lap(self) -> None:
        """Enforces budgets before launching an iteration / LLM call."""
        # 1. Wall-clock budget check
        elapsed = self.elapsed_seconds
        if elapsed >= self.max_time_seconds:
            raise BudgetExceededError(
                budget_name="wall_clock",
                limit=self.max_time_seconds,
                current=elapsed,
                lap=self.iterations,
            )

        # 2. Max iterations check
        if self.iterations >= self.max_iterations:
            raise BudgetExceededError(
                budget_name="max_iterations",
                limit=self.max_iterations,
                current=self.iterations,
                lap=self.iterations,
            )

        # 3. Max tokens check (already accumulated from prior laps)
        if self.total_tokens >= self.max_tokens:
            raise BudgetExceededError(
                budget_name="max_tokens",
                limit=self.max_tokens,
                current=self.total_tokens,
                lap=self.iterations,
            )

        # 4. Max cost check (already accumulated from prior laps)
        if self.total_cost >= self.max_cost:
            raise BudgetExceededError(
                budget_name="max_cost",
                limit=self.max_cost,
                current=self.total_cost,
                lap=self.iterations,
            )

    def record_lap(self, prompt_tokens: int, completion_tokens: int) -> None:
        """Records token and cost consumption for a completed lap and checks post-lap limits."""
        self.iterations += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += (prompt_tokens + completion_tokens)

        lap_cost = (
            (prompt_tokens * (self.INPUT_COST_PER_MILLION / 1_000_000.0))
            + (completion_tokens * (self.OUTPUT_COST_PER_MILLION / 1_000_000.0))
        )
        self.total_cost += lap_cost

        # Immediately enforce token and cost limits after lap completion
        if self.total_tokens >= self.max_tokens:
            raise BudgetExceededError(
                budget_name="max_tokens",
                limit=self.max_tokens,
                current=self.total_tokens,
                lap=self.iterations,
            )

        if self.total_cost >= self.max_cost:
            raise BudgetExceededError(
                budget_name="max_cost",
                limit=self.max_cost,
                current=self.total_cost,
                lap=self.iterations,
            )

    def summary(self) -> dict:
        """Returns a snapshot of budget consumption."""
        return {
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "max_tokens": self.max_tokens,
            "total_cost": round(self.total_cost, 6),
            "max_cost": self.max_cost,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
            "max_time_seconds": self.max_time_seconds,
        }
