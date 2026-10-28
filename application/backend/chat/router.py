"""Decides which pipeline answers a question. Plain rules, every decision explained.

The course's lesson (W7, W10): use the cheapest path that can answer. A known employee plus one
known topic is a fixed lookup, so no LLM is needed; several topics need an agent that chooses tools;
several employees are independent sub-tasks, so a squad runs them in parallel; everything else is
retrieval over the handbook.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from application.backend.agent.tools import EMPLOYEE_DATABASE as HR_EMPLOYEES
from curriculum.week_12_capstone.data.employees import EMPLOYEE_DATABASE as DESK_EMPLOYEES

EMPLOYEE_ID = re.compile(r"\bEMP-(?:[A-Z]+-)?\d+\b", re.IGNORECASE)

TOPIC_KEYWORDS = {
    "notice_period": ("notice period", "notice", "resign", "resignation"),
    "carry_over_cap": ("carry over", "carry-over", "carryover", "roll over", "rollover", "unused vacation", "unused leave"),
    "sabbatical": ("sabbatical",),
}
# only counts when nothing more specific matched: "eligible for a sabbatical" is a sabbatical question
FALLBACK_TOPIC = ("eligibility", ("eligible", "eligibility", "qualify"))

REGION_NAMES = {
    "UK": (r"\bUK\b", r"\bunited kingdom\b", r"\bbritain\b"),
    "US": (r"\bUS\b", r"\bUSA\b", r"\bunited states\b"),
    "EMEA": (r"\bEMEA\b", r"\beurope\b"),
    "APAC": (r"\bAPAC\b", r"\basia\b"),
    "LATAM": (r"\bLATAM\b", r"\blatin america\b"),
    "NA": (r"\bNA\b", r"\bnorth america\b"),
}


@dataclass
class RouteDecision:
    route: str
    reasons: List[str]
    employee_ids: List[str] = field(default_factory=list)
    unknown_employee_ids: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    region: Optional[str] = None
    region_source: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def detect_topics(query: str) -> List[str]:
    q = query.lower()
    topics = [t for t, words in TOPIC_KEYWORDS.items() if any(w in q for w in words)]
    if not topics and any(w in q for w in FALLBACK_TOPIC[1]):
        topics = [FALLBACK_TOPIC[0]]
    return topics


def detect_region(query: str) -> Optional[str]:
    """Only a single unambiguous region counts; 'UK vs US' is a comparison, not a filter."""
    found = [code for code, pats in REGION_NAMES.items() if any(re.search(p, query, re.IGNORECASE) for p in pats)]
    return found[0] if len(found) == 1 else None


def decide(query: str, selected_region: Optional[str] = None) -> RouteDecision:
    ids = list(dict.fromkeys(m.upper() for m in EMPLOYEE_ID.findall(query)))
    hr = [i for i in ids if i in HR_EMPLOYEES]
    desk = [i for i in ids if i in DESK_EMPLOYEES and i not in hr]
    unknown = [i for i in ids if i not in hr and i not in desk]
    topics = detect_topics(query)

    def rag(reasons: List[str]) -> RouteDecision:
        if selected_region and selected_region.upper() != "ALL":
            region, source = selected_region.upper(), "selected by user"
        elif len(hr) == 1:
            region, source = HR_EMPLOYEES[hr[0]]["jurisdiction"], f"jurisdiction of {hr[0]}"
        else:
            region = detect_region(query)
            source = "named in the question" if region else None
        if region:
            reasons.append(f"Filtering the handbook to {region} ({source}).")
        return RouteDecision("rag", reasons, hr, unknown, topics, region, source)

    if unknown:
        note = f"{', '.join(unknown)} is not a known employee, so no record lookup."
    else:
        note = None

    if desk and not hr:
        return RouteDecision("policy_desk", [
            f"{', '.join(desk)} belongs to the India/UK shared-services desk.",
            "The desk resolves entity and grade over MCP tools before answering.",
        ], desk, unknown, topics)

    if len(hr) >= 2 and topics:
        return RouteDecision("multi_agent_squad", [
            f"{len(hr)} employees named: each is an independent lookup.",
            "A squad of profile and policy specialists runs them in parallel.",
        ], hr, unknown, topics)

    if len(hr) == 1 and len(topics) == 1:
        return RouteDecision("fixed_workflow", [
            f"One employee ({hr[0]}) and one topic ({topics[0]}).",
            "The lookup path is known, so a fixed workflow answers without an LLM.",
        ], hr, unknown, topics)

    if len(hr) == 1 and len(topics) >= 2:
        return RouteDecision("react_agent", [
            f"One employee ({hr[0]}) but {len(topics)} topics.",
            "A ReAct agent chooses which tools to call for each topic.",
        ], hr, unknown, topics)

    reasons = ["No employee-specific lookup needed: answering from the handbook."]
    if hr and not topics:
        reasons = [f"{hr[0]} named but no specific entitlement topic: answering from the handbook."]
    if len(hr) >= 2 and not topics:
        reasons = ["Several employees named but no entitlement topic: answering from the handbook."]
    if note:
        reasons.append(note)
    return rag(reasons)


if __name__ == "__main__":
    assert decide("How many vacation days can I carry over?").route == "rag"
    assert decide("Carry-over rules in the UK?").region == "UK"
    assert decide("UK vs US carry over").region is None
    assert decide("What is the notice period for EMP-102?").route == "fixed_workflow"
    assert decide("Is EMP-103 eligible for a sabbatical?").topics == ["sabbatical"]
    assert decide("Notice period and sabbatical for EMP-103").route == "react_agent"
    assert decide("Compare carry over for EMP-101 and EMP-104").route == "multi_agent_squad"
    assert decide("What is my notice period? I am EMP-UK-601").route == "policy_desk"
    d = decide("Notice period for EMP-999")
    assert d.route == "rag" and d.unknown_employee_ids == ["EMP-999"]
    print("router ok")
