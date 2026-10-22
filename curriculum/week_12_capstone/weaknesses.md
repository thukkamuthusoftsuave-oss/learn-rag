<!-- Soft Suave · The AI Engineering League -->
# Week 12 Capstone — Top 3 Known System Weaknesses

**Project:** Variant C · Policy Answer Desk (HR Policy Shared-Services)  
**Author:** AI Engineering Squad Lead  
**Timestamp:** Wednesday, Week 12 · 09:15 AM (Written Unprompted Prior to Panel Defense)  

---

## 1. Weakness 1: Temporal Straddling Across Policy Transition Boundaries
- **The Vulnerability:**  
  The system currently routes queries to either `HR-LEAVE-2024-v1.0` (retrospective) or `HR-LEAVE-2025-v2.0` (active/current). However, if an employee asks about an extended absence that **straddles the boundary** — for example:  
  *"I started my 16-week maternity leave on November 15, 2024, and return in March 2025. Which policy's leave accrual rate applies to my vacation days during the crossover period?"*
- **Why It Fails:**  
  Our query-time temporal classifier makes a binary choice ($2024$ vs $2025$). It cannot dynamically split an ongoing continuous leave span across two distinct policy effective dates. The system will arbitrarily cite either the 2024 or 2025 accrual clause.
- **Risk to HR:** Low-to-Medium frequency (occurs during annual January/February transition), but High grievance potential if accrued leave calculations differ by 2+ days.
- **Pre-emptive Defense:** We have added an explicit assertion rule: any query containing date ranges crossing `2025-01-01` must trigger `escalate_to_hrbp()` for manual reconciliation rather than computing a split automated answer.

---

## 2. Weakness 2: Partial Annex Coverage & Silent Fallback Ambiguity
- **The Vulnerability:**  
  The system enforces the rule that *“The Entity Annex silently overrides the General Handbook where they conflict.”* However, in edge cases where an Annex defines a primary benefit but is completely silent on associated procedural prerequisites, the system struggles with partial inheritance.  
  *Example:* The UK Entity Annex defines Statutory Maternity Pay (SMP) entitlements (Clause 2.1) but does not state notice lead times (e.g., notifying HR 15 weeks prior to expected week of childbirth). Does the 8-week notice rule in Section 4.1 of the general handbook survive, or does the Annex's statutory scope completely extinguish Section 4.1?
- **Why It Fails:**  
  The retriever either returns the Annex alone (leaving the employee uninformed about the 8-week notice requirement) or blends both chunks (risking conflicting statements).
- **Risk to HR:** Legal ambiguity during employee pregnancy notifications.
- **Pre-emptive Defense:** Documented in our eval suite as an intentional non-coverage zone. We recommend HR explicitly annotate in the 2026 handbook revision which clauses are fully replaced vs partially augmented.

---

## 3. Weakness 3: Secondments & Cross-Border Dual-Entity Employees
- **The Vulnerability:**  
  Grade and entity resolution rely strictly on `get_employee_record(emp_id)`. If an employee contracted under the India legal entity (`EMP-IN-001`) is placed on a 6-month technical secondment in London, the system resolves their entity as `India`.  
  If they ask: *"What public holidays or overtime rules apply to me while working in the Shoreditch office?"*, the system retrieves the India Entity Annex (referencing Indian national holidays and Factories Act overtime) rather than UK Working Time Regulations.
- **Why It Fails:**  
  The employee database table stores home contracting entity (`contract_entity`), but lacks dynamic jurisdictional location fields (`work_location_current`).
- **Risk to HR:** Potential violation of local host-country statutory rest period laws for seconded staff.
- **Pre-emptive Defense:** In the 10× scale roadmap, the employee lookup tool schema will expand to return `contract_entity`, `tax_residence`, and `physical_work_location`, enabling multi-variable jurisdictional policy arbitration.
