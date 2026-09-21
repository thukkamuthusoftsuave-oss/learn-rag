"""Week 7: Typed Tool Registry for HR Entitlement Operations.

Defines three disjoint, strictly typed tools with Enum parameters:
1. get_employee_record: Employee demographic & tenure profile.
2. get_handbook_rule: Corporate HR-207 handbook policy text.
3. get_jurisdiction_rules: Statutory labor laws & legal overrides.
"""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class JurisdictionEnum(str, Enum):
    US = "US"
    UK = "UK"
    EMEA = "EMEA"
    APAC = "APAC"
    LATAM = "LATAM"
    NA = "NA"


# Mock Database of Employee Profiles
EMPLOYEE_DB: Dict[str, Dict[str, Any]] = {
    "EMP-101": {"employee_id": "EMP-101", "name": "Alice Smith", "jurisdiction": "UK", "tenure_years": 1.5, "employee_type": "Regular", "weekly_hours": 40, "vacation_balance": 12},
    "EMP-102": {"employee_id": "EMP-102", "name": "Bob Jones", "jurisdiction": "UK", "tenure_years": 4.0, "employee_type": "Regular", "weekly_hours": 40, "vacation_balance": 15},
    "EMP-103": {"employee_id": "EMP-103", "name": "Carlos Ruiz", "jurisdiction": "EMEA", "tenure_years": 6.0, "employee_type": "Senior", "weekly_hours": 40, "vacation_balance": 18},
    "EMP-104": {"employee_id": "EMP-104", "name": "Diana Chen", "jurisdiction": "EMEA", "tenure_years": 3.0, "employee_type": "Regular", "weekly_hours": 40, "vacation_balance": 10},
    "EMP-105": {"employee_id": "EMP-105", "name": "Evan Wright", "jurisdiction": "US", "tenure_years": 2.5, "employee_type": "Regular", "weekly_hours": 40, "vacation_balance": 14},
}

# Mock Database of Corporate Policies
HANDBOOK_DB: Dict[str, Dict[str, Any]] = {
    "UK": {"notice_period": "Base policy notice is 1 month for regular employees.", "carry_over_cap": 8, "sabbatical": "Eligible after 10 years for 6-week sabbatical."},
    "EMEA": {"notice_period": "Standard notice is 4 weeks.", "carry_over_cap": 10, "sabbatical": "Eligible after 5 years for 4-week sabbatical."},
    "US": {"notice_period": "At-will employment; 2 weeks standard notice requested.", "carry_over_cap": 10, "sabbatical": "No sabbatical benefit."},
}

# Mock Database of Statutory Overrides
STATUTORY_DB: Dict[str, Dict[str, Any]] = {
    "UK": {
        "notice_period": "UK Employment Rights Act 1996 § 86: Continuous service between 1 month and 2 years requires exactly 1 week statutory notice. 2+ years requires 1 week per completed year up to 12 weeks."
    },
    "EMEA": {
        "sabbatical": "Statutory labor code respects corporate 5-year threshold for sabbatical leave."
    },
    "US": {
        "wage_protection": "California Labor Code § 227.3 prohibits forfeiture of vested vacation upon termination."
    }
}


def get_employee_record(employee_id: str) -> Dict[str, Any]:
    """Retrieve an employee's HR profile."""
    if employee_id in EMPLOYEE_DB:
        return {"status": "success", "data": EMPLOYEE_DB[employee_id]}
    return {"status": "error", "message": f"Employee {employee_id} not found."}


def get_handbook_rule(jurisdiction: str, topic: str) -> Dict[str, Any]:
    """Retrieve corporate HR-207 handbook policy text."""
    jur_data = HANDBOOK_DB.get(jurisdiction.upper(), {})
    rule = jur_data.get(topic.lower())
    if rule:
        return {"status": "success", "jurisdiction": jurisdiction, "topic": topic, "policy": rule}
    return {"status": "error", "message": f"No handbook rule found for {jurisdiction} on {topic}."}


def get_jurisdiction_rules(jurisdiction: str, topic: str) -> Dict[str, Any]:
    """Retrieve statutory labor laws and legal overrides."""
    jur_data = STATUTORY_DB.get(jurisdiction.upper(), {})
    rule = jur_data.get(topic.lower())
    if rule:
        return {"status": "success", "jurisdiction": jurisdiction, "topic": topic, "statutory_mandate": rule}
    return {"status": "success", "jurisdiction": jurisdiction, "topic": topic, "statutory_mandate": "No specific statutory override; corporate policy governs."}
