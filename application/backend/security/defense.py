"""4-Layer Defense-in-Depth Security Framework.

Guards the autonomous policy agent and RAG pipeline against indirect prompt injections,
jailbreaks, and policy invariant violations.
"""

import re
import json
from typing import Dict, Any, Tuple, Optional, List
from application.backend.core.config import settings

INJECTION_SIGNATURES = [
    r"(?i)ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions",
    r"(?i)urgent\s+(?:audit\s+)?override",
    r"(?i)grant\s+(?:employee\s+)?(?:an\s+)?immediate",
    r"(?i)disregard\s+(?:company\s+)?policy",
    r"(?i)golden\s+parachute",
    r"(?i)system\s+(?:notice|instruction|prompt)",
    r"(?i)bypass\s+(?:all\s+)?(?:checks|rules)",
    r"(?i)unrestricted\s+admin\s+mode",
]


class SecurityDefenseSystem:
    """Enterprise 4-Layer Defense-in-Depth engine."""

    @staticmethod
    def scan_for_injections(text: str) -> Dict[str, Any]:
        """Layer 2: Regex & heuristic pattern scanner."""
        detected = []
        for pattern in INJECTION_SIGNATURES:
            match = re.search(pattern, text)
            if match:
                detected.append(match.group(0))

        is_attack = len(detected) > 0
        return {
            "is_attack": is_attack,
            "detected_signatures": detected,
            "status": "THREAT_DETECTED" if is_attack else "CLEAN"
        }

    @staticmethod
    def sandbox_tool_output(data: Dict[str, Any]) -> Dict[str, Any]:
        """Layer 3: Least-privilege sandboxing - strips raw text notes and sensitive fields."""
        safe_copy = dict(data)
        # Strip fields prone to indirect prompt injection or PII leakage
        untrusted_fields = ["notes", "internal_comments", "salary", "ssn", "compensation"]
        stripped_fields = []
        for field in untrusted_fields:
            if field in safe_copy:
                del safe_copy[field]
                stripped_fields.append(field)
        return {
            "sanitized_data": safe_copy,
            "stripped_fields": stripped_fields
        }

    @staticmethod
    def encapsulate_xml(data: Any, tag_name: str = "untrusted_policy_data") -> str:
        """Layer 1: Structural XML isolation boundaries."""
        serialized = json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
        return f"<{tag_name} origin='system_database' validation='isolated'>\n{serialized}\n</{tag_name}>"

    @staticmethod
    def verify_policy_invariants(answer: str, max_days: int = None) -> Dict[str, Any]:
        """Layer 4: Policy invariant post-guards."""
        cap = max_days or settings.max_allowed_vacation_carryover
        violations = []

        # Check carry-over day claims against global maximum
        days_found = re.findall(r"(\d+)\s+(?:vacation\s+)?days?", answer, re.IGNORECASE)
        for d in days_found:
            val = int(d)
            if val > cap:
                violations.append(
                    f"Output specifies {val} days, which violates the strict enterprise cap of {cap} days."
                )

        # Check unauthorized overrides
        if "override" in answer.lower() and "urgent" in answer.lower():
            violations.append("Unauthorized policy override detected in synthesis.")

        is_valid = len(violations) == 0
        return {
            "passed": is_valid,
            "violations": violations,
            "status": "INVARIANT_VERIFIED" if is_valid else "INVARIANT_VIOLATION_BLOCKED"
        }


security_defense = SecurityDefenseSystem()
