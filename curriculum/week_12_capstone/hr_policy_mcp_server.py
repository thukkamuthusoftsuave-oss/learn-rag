"""Model Context Protocol (MCP) Server for HR Policy Answer Desk.
Exposes entity-scoped policy search, employee record lookup, leave balance check,
and HRBP escalation over JSON-RPC 2.0 stdio protocol.
"""

import sys
import os
import json
import logging
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from curriculum.week_12_capstone.data.policy_corpus import (
    GENERAL_HANDBOOK,
    LEAVE_POLICY_2024,
    LEAVE_POLICY_2025,
    INDIA_ENTITY_ANNEX,
    UK_ENTITY_ANNEX,
    GRADE_BAND_MATRIX
)
from curriculum.week_12_capstone.data.employees import (
    get_raw_employee,
    sanitize_for_agent,
    sanitize_for_logging
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HRPolicyMCPServer")


class HRPolicyMCPServer:
    """Production Model Context Protocol (MCP) server for Capstone Variant C."""

    def __init__(self):
        self.tools = [
            {
                "name": "get_employee_record",
                "description": "Look up an employee's verified HR record including entity jurisdiction, grade (1-7), title, and tenure.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string", "description": "Corporate employee ID, e.g. EMP-IND-301, EMP-UK-601"}
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "check_leave_balance",
                "description": "Check an employee's current accrued and remaining leave balances by category.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string", "description": "Corporate employee ID"},
                        "leave_type": {"type": "string", "description": "Type of leave: earned_leave, annual_leave, casual_leave, sick_leave"}
                    },
                    "required": ["employee_id"]
                }
            },
            {
                "name": "search_policy_docs",
                "description": "Search company policy handbook and entity annexes. Entity Annex silently overrides General Handbook where conflicting.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Subject matter inquiry, e.g. parental leave, notice period, carry over"},
                        "entity": {"type": "string", "enum": ["India", "UK", "Global"], "description": "Corporate entity for statutory overrides"},
                        "effective_year": {"type": "integer", "description": "Policy version year (2024 for superseded, 2025 for active). Default is 2025."}
                    },
                    "required": ["query", "entity"]
                }
            },
            {
                "name": "escalate_to_hrbp",
                "description": "Hand off discretionary, non-standard, executive Grade 7, or hardship inquiries to an HR Business Partner instead of guessing.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "employee_id": {"type": "string", "description": "Corporate employee ID"},
                        "issue_summary": {"type": "string", "description": "Summary of the discretionary request"},
                        "policy_clause": {"type": "string", "description": "Relevant policy clause requiring HRBP discretion"}
                    },
                    "required": ["employee_id", "issue_summary"]
                }
            }
        ]

    def handle_get_employee_record(self, employee_id: str) -> Dict[str, Any]:
        raw = get_raw_employee(employee_id)
        if not raw:
            return {"status": "error", "message": f"Employee record '{employee_id}' not found."}
        # Hold PII line in telemetry log!
        logger.info(f"[MCP Span: get_employee_record] Looked up record: {sanitize_for_logging(raw)}")
        return {"status": "success", "employee": sanitize_for_agent(raw)}

    def handle_check_leave_balance(self, employee_id: str, leave_type: Optional[str] = None) -> Dict[str, Any]:
        raw = get_raw_employee(employee_id)
        if not raw:
            return {"status": "error", "message": f"Employee record '{employee_id}' not found."}
        balances = raw.get("leave_balances", {})
        if leave_type:
            lt_clean = leave_type.strip().lower()
            return {
                "status": "success",
                "employee_id": raw["employee_id"],
                "leave_type": lt_clean,
                "balance": balances.get(lt_clean, 0)
            }
        return {"status": "success", "employee_id": raw["employee_id"], "leave_balances": balances}

    def handle_search_policy_docs(self, query: str, entity: str, effective_year: int = 2025) -> Dict[str, Any]:
        q_lower = query.lower()
        results = []

        # 1. If 2024 is explicitly requested, check 2024 Superseded Policy FIRST
        if effective_year == 2024:
            if any(k in q_lower for k in ["parental", "maternity", "caregiver", "leave"]):
                results.append({
                    "source": "Global Parental Leave Policy 2024 (SUPERSEDED)",
                    "version": "HR-LEAVE-2024-v1.0",
                    "effective_date": "2024-01-01",
                    "clause": "Section 4.1 - Parental Leave Entitlement (2024 Rules)",
                    "text": "Primary caregivers were entitled to 12 weeks of paid parental leave at 100% of base salary in 2024.",
                    "precedence": "Historical Superseded Policy"
                })
            if any(k in q_lower for k in ["carry", "rollover"]):
                results.append({
                    "source": "Global Parental Leave Policy 2024 (SUPERSEDED)",
                    "version": "HR-LEAVE-2024-v1.0",
                    "effective_date": "2024-01-01",
                    "clause": "Section 4.2 - Annual Vacation Carry-Over (2024 Rules)",
                    "text": "In 2024, employees could carry over up to 5 unused vacation days, expiring on March 31.",
                    "precedence": "Historical Superseded Policy"
                })
            if any(k in q_lower for k in ["sabbatical"]):
                results.append({
                    "source": "Global Parental Leave Policy 2024 (SUPERSEDED)",
                    "version": "HR-LEAVE-2024-v1.0",
                    "effective_date": "2024-01-01",
                    "clause": "Section 4.3 - Sabbatical Leave (2024 Rules)",
                    "text": "In 2024, employees with 8+ years service were eligible for a 4-week unpaid sabbatical.",
                    "precedence": "Historical Superseded Policy"
                })

        # 2. Check Entity Annex (Entity Annex Silently Wins for Active 2025 Rules)
        if not results:
            if entity == "India":
                if any(k in q_lower for k in ["maternity", "parental", "paternity", "mother", "child"]):
                    results.append({
                        "source": "India Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-IND",
                        "effective_date": "2025-01-01",
                        "clause": "Section 1.1 - Statutory Maternity Benefit",
                        "text": "All female employees in India are entitled to 26 weeks of fully paid maternity leave. Male employees receive 2 weeks (10 working days) paternity leave.",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })
                elif any(k in q_lower for k in ["notice", "resign", "separation"]):
                    results.append({
                        "source": "India Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-IND",
                        "effective_date": "2025-01-01",
                        "clause": "Section 3.1 - India Notice Period Overrides",
                        "text": "Notice periods in India: Probation: 30 days. Confirmed Grades 1-4: 60 days (2 months). Confirmed Grades 5-7: 90 days (3 months).",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })
                elif any(k in q_lower for k in ["carry", "encash", "earned leave", "vacation"]):
                    results.append({
                        "source": "India Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-IND",
                        "effective_date": "2025-01-01",
                        "clause": "Section 2.1 - India Leave Structure & Carry-Over Overrides",
                        "text": "India employees receive 18 days Earned Leave per annum, accumulative up to a statutory ceiling of 30 days. Casual leave is 7 days.",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })

            elif entity == "UK":
                if any(k in q_lower for k in ["maternity", "parental", "paternity", "mother", "child"]):
                    results.append({
                        "source": "UK Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-UK",
                        "effective_date": "2025-01-01",
                        "clause": "Section 1.1 - Statutory & Company Maternity Leave (UK)",
                        "text": "UK employees receive 52 weeks maternity leave. Company enhanced top-up: Grades 1-3: SMP + 6 weeks full pay; Grades 4-6: SMP + 18 weeks full pay; Grade 7: 26 weeks full pay. Paternity leave: 2 weeks.",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })
                elif any(k in q_lower for k in ["notice", "resign", "separation"]):
                    results.append({
                        "source": "UK Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-UK",
                        "effective_date": "2025-01-01",
                        "clause": "Section 3.1 - UK Statutory Notice Period Overrides",
                        "text": "UK notice periods: Probation: 1 week. Confirmed Grades 1-3: 4 weeks. Confirmed Grades 4-6: 12 weeks. Grade 7: 6 months.",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })
                elif any(k in q_lower for k in ["annual leave", "vacation", "bank holiday", "carry"]):
                    results.append({
                        "source": "UK Entity Annex (Effective: 2025-01-01)",
                        "version": "HR-207-ANNEX-UK",
                        "effective_date": "2025-01-01",
                        "clause": "Section 2.1 - UK Annual Leave & Working Time Regulations",
                        "text": "UK employees receive 25 days paid annual leave plus 8 UK statutory bank holidays (total 33 days). Up to 5 days carry-over permitted.",
                        "precedence": "Entity Annex Override (Wins over Handbook)"
                    })

        # 3. Active 2025 Global Policies
        if not results:
            if any(k in q_lower for k in ["carry", "rollover"]):
                results.append({
                    "source": "Global Parental & Extended Leave Policy 2025 (ACTIVE)",
                    "version": "HR-LEAVE-2025-v2.0",
                    "effective_date": "2025-01-01",
                    "clause": "Section 4.2 - Enhanced Vacation Carry-Over (2025 Rules)",
                    "text": "Under the 2025 Enhanced Leave Policy, employees may carry over up to 10 unused vacation days without March 31 forfeiture.",
                    "precedence": "Global Active Policy"
                })
            elif any(k in q_lower for k in ["sabbatical"]):
                results.append({
                    "source": "Global Parental & Extended Leave Policy 2025 (ACTIVE)",
                    "version": "HR-LEAVE-2025-v2.0",
                    "effective_date": "2025-01-01",
                    "clause": "Section 4.3 - Expanded Sabbatical Leave (2025 Rules)",
                    "text": "Employees with at least 7 years of continuous full-time service are eligible for a 6-week fully paid sabbatical.",
                    "precedence": "Global Active Policy"
                })
            elif any(k in q_lower for k in ["parental", "caregiver"]):
                results.append({
                    "source": "Global Parental & Extended Leave Policy 2025 (ACTIVE)",
                    "version": "HR-LEAVE-2025-v2.0",
                    "effective_date": "2025-01-01",
                    "clause": "Section 4.1 - Enhanced Parental Leave Entitlement (2025 Rules)",
                    "text": "Primary caregivers are eligible for 26 weeks of paid parental leave at 100% of base salary.",
                    "precedence": "Global Active Policy"
                })
            elif any(k in q_lower for k in ["probation", "confirmation"]):
                results.append({
                    "source": "Global Employee Handbook (HR-207 CORE)",
                    "version": "HR-207 Base",
                    "effective_date": "2024-01-01",
                    "clause": "Section 3.1 - Probationary Period",
                    "text": "Standard probationary period: 3 calendar months for Grades 1-5; 6 calendar months for Grades 6-7.",
                    "precedence": "Base Framework (General Case)"
                })
            else:
                results.append({
                    "source": "Global Employee Handbook (HR-207 CORE)",
                    "version": "HR-207 Base",
                    "effective_date": "2024-01-01",
                    "clause": "Section 2.1 - General Leave Entitlement",
                    "text": "Employees receive 20 days standard annual vacation leave per calendar year accrued monthly.",
                    "precedence": "Base Framework (General Case)"
                })

        return {
            "status": "success",
            "entity": entity,
            "effective_year": effective_year,
            "results_count": len(results),
            "results": results
        }

    def handle_escalate_to_hrbp(self, employee_id: str, issue_summary: str, policy_clause: Optional[str] = None) -> Dict[str, Any]:
        ticket_id = f"HRBP-ESC-{hash(issue_summary) % 100000:05d}"
        logger.info(f"[MCP Span: escalate_to_hrbp] Created escalation ticket {ticket_id} for {employee_id}")
        return {
            "status": "escalated",
            "ticket_id": ticket_id,
            "employee_id": employee_id,
            "summary": issue_summary,
            "clause": policy_clause or "Discretionary policy exception",
            "message": "This inquiry involves discretionary authority or executive terms. It has been routed directly to your assigned HR Business Partner rather than guessing."
        }

    def dispatch(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatches tool call."""
        if tool_name == "get_employee_record":
            return self.handle_get_employee_record(arguments.get("employee_id", ""))
        elif tool_name == "check_leave_balance":
            return self.handle_check_leave_balance(arguments.get("employee_id", ""), arguments.get("leave_type"))
        elif tool_name == "search_policy_docs":
            return self.handle_search_policy_docs(
                arguments.get("query", ""),
                arguments.get("entity", "India"),
                arguments.get("effective_year", 2025)
            )
        elif tool_name == "escalate_to_hrbp":
            return self.handle_escalate_to_hrbp(
                arguments.get("employee_id", ""),
                arguments.get("issue_summary", ""),
                arguments.get("policy_clause")
            )
        else:
            return {"status": "error", "message": f"Tool '{tool_name}' not implemented in MCP server."}

    def run_stdio(self):
        """Standard JSON-RPC 2.0 stdio server loop."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                req_id = req.get("id")
                method = req.get("method")

                if method == "tools/list":
                    res = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": self.tools}}
                elif method == "tools/call":
                    params = req.get("params", {})
                    name = params.get("name")
                    arguments = params.get("arguments", {})
                    call_res = self.dispatch(name, arguments)
                    res = {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(call_res)}]}}
                else:
                    res = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

                sys.stdout.write(json.dumps(res) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_res = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(e)}}
                sys.stdout.write(json.dumps(err_res) + "\n")
                sys.stdout.flush()


mcp_server = HRPolicyMCPServer()

if __name__ == "__main__":
    mcp_server.run_stdio()
