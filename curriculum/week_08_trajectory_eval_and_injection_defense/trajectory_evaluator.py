"""Week 8: Trajectory Evaluation & Outcome-vs-Trajectory Gap Engine.

Measures whether an agent arrived at the correct answer through a valid,
verified trajectory rather than an unverified parametric shortcut.
"""

from typing import List, Dict, Any, Tuple


def evaluate_trajectory_gap(
    final_answer: str,
    trajectory_steps: List[str],
    expected_facts: List[str],
    mandatory_tools: List[str]
) -> Dict[str, Any]:
    """Evaluates both outcome and trajectory to calculate the Gap.
    
    Outcome Pass: All expected_facts are present in the final answer.
    Trajectory Pass: All mandatory_tools were called in the execution trajectory.
    Outcome-vs-Trajectory Gap: Outcome Pass == True but Trajectory Pass == False (Lucky Shortcut).
    """
    outcome_passed = all(fact.lower() in final_answer.lower() for fact in expected_facts)
    missing_tools = [tool for tool in mandatory_tools if tool not in trajectory_steps]
    trajectory_passed = (len(missing_tools) == 0)
    gap_detected = outcome_passed and not trajectory_passed

    return {
        "outcome_passed": outcome_passed,
        "trajectory_passed": trajectory_passed,
        "gap_detected": gap_detected,
        "missing_mandatory_tools": missing_tools,
        "status": "VALID_TRAJECTORY" if trajectory_passed and outcome_passed else (
            "OUTCOME_VS_TRAJECTORY_GAP" if gap_detected else "FAILED"
        )
    }
