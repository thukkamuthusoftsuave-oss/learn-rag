"""Enums for HR policy agent tools and workflow parameters.

Using typed enums guarantees valid inputs, eliminates tool hallucinations for
jurisdiction names, and provides strict schema validation across both the
hand-built agent loop and the fixed workflow.
"""

from enum import Enum


class JurisdictionEnum(str, Enum):
    """Supported corporate HR jurisdictions."""
    US = "US"
    UK = "UK"
    EMEA = "EMEA"
    APAC = "APAC"
    LATAM = "LATAM"
    NA = "NA"


class PolicyTopicEnum(str, Enum):
    """Specific HR policy topics covered by handbook and statutory rules."""
    CARRY_OVER_CAP = "carry_over_cap"
    NOTICE_PERIOD = "notice_period"
    SABBATICAL = "sabbatical"
    PART_TIME_RULE = "part_time_rule"
    BORROWING_NEGATIVE_BALANCE = "borrowing_negative_balance"
    TERMINATION_PAYOUT = "termination_payout"
    STATUTORY_LEAVE = "statutory_leave"
