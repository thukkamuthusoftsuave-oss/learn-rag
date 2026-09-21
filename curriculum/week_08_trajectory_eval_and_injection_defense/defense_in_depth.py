"""Week 8: 4-Layer Defense-in-Depth against Indirect Prompt Injection.

1. Layer 1: Strict XML boundary isolation tags (<untrusted_data>).
2. Layer 2: Heuristic regex scanner for injection signatures.
3. Layer 3: Least-privilege tool execution sandboxing (stripping raw note fields).
4. Layer 4: Policy invariant post-guards (validating output constraints).
"""

import re
from typing import Dict, Any, Tuple, Optional

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"(?i)urgent\s+(?:audit\s+)?override",
    r"(?i)grant\s+(?:employee\s+)?(?:an\s+)?immediate",
    r"(?i)disregard\s+(?:company\s+)?policy",
    r"(?i)golden\s+parachute",
    r"(?i)system\s+(?:notice|instruction|prompt)",
]


def scan_for_injection_patterns(text: str) -> Tuple[bool, Optional[str]]:
    """Layer 2: Scans text for known prompt injection regex signatures."""
    for pattern in INJECTION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return True, f"Injection signature detected: '{match.group(0)}'"
    return False, None


def sandbox_employee_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Layer 3: Least-privilege sandboxing - strips raw text notes and sensitive PII."""
    safe_copy = dict(record)
    if "notes" in safe_copy:
        del safe_copy["notes"]
    if "salary" in safe_copy:
        del safe_copy["salary"]
    if "ssn" in safe_copy:
        del safe_copy["ssn"]
    return safe_copy


def wrap_with_xml_boundaries(data: Dict[str, Any], tag_name: str = "untrusted_data") -> str:
    """Layer 1: Wraps data in unambiguous XML isolation tags."""
    import json
    json_str = json.dumps(data)
    return f"<{tag_name} origin='external_record'>\n{json_str}\n</{tag_name}>"


def check_policy_invariants(answer: str, max_allowed_days: int = 15) -> Tuple[bool, str]:
    """Layer 4: Invariant post-guards - validates that output satisfies policy bounds."""
    # Check if answer claims days greater than global cap (15 days)
    days_match = re.findall(r"(\d+)\s+days?", answer, re.IGNORECASE)
    for d in days_match:
        val = int(d)
        if val > max_allowed_days:
            return False, f"Invariant violation: Output mentions {val} days, which exceeds maximum cap of {max_allowed_days} days."
    return True, "Invariant checks passed."
