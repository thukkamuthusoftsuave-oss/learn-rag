"""Generates the synthetic HR-207 policy addendum corpus.

Writes one ``data/addendum_<REGION>.txt`` file per region. The on-disk format
is a strict contract consumed by ``chunker.py`` (structure-aware chunker) and
``ingest.py`` (metadata extractor):

- Line 1: ``Region: <CODE>``
- Line 2: ``Effective Date: <YYYY-MM-DD>``
- Section headers: ``HR-207 Section <X.Y> - <Title>``

Sections 4.1/4.2/4.3 (where present) contain known-answer eval facts and must
not be altered. Sections 4.4+ are supplementary policy detail that makes the
corpus realistic and retrieval discriminating. Refusal eval cases depend on
the following NEVER appearing: the word "maternity", home-office equipment
reimbursement content, and sabbatical sections outside EMEA/UK.
"""

import os

DOCS = {
    "addendum_NA.txt": """Region: NA
Effective Date: 2026-01-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service and must be full-time. Continuous service means uninterrupted employment without a break longer than 30 days.
Eligibility is determined as of the last day of the calendar year.
Continuous service is measured from the most recent hire date.
Rehired employees restart their continuous service clock unless rehired within 30 days of separation.
Contract workers and vendors are not covered by this policy.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 5 days         |
| Regular       | 6 months - 2 yrs  | 10 days        |
| Senior        | > 2 yrs           | 15 days        |
Caps apply per calendar year and are not cumulative across years.
Carry-over is calculated on accrued, unused vacation balances as of December 31.
Balances above the cap are forfeited at year-end unless Section 4.5 applies.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on March 31 of the following calendar year.
Expired days are forfeited without payout.
| Employee Type | Expiry Date |
|---------------|-------------|
| Probationary  | March 31    |
| Regular       | March 31    |
| Senior        | June 30     |
Senior employees receive an extended expiry window as a retention benefit.
Expiry dates are visible in the HRIS balance view from January onward.

HR-207 Section 4.5 - Payout on Termination
On voluntary termination, unused carried-over days are paid at 100% of the base daily rate for Regular and Senior employees.
Probationary employees receive payout at 50% of the base daily rate.
On involuntary termination for cause, carried-over balances are forfeited.
Payouts are processed with the final paycheck within 30 days.
Resignation without the contractual notice period reduces payout to 50% for all employee types.

HR-207 Section 4.6 - Negative Balance
Employees may borrow up to 5 vacation days ahead of accrual with manager approval.
Borrowing is not permitted during the first 6 months of employment.
Negative balances must be repaid within 6 months through accrual.
Any remaining negative balance at separation is deducted from the final paycheck.

HR-207 Section 4.7 - Part-time Rule
Part-time employees working fewer than 40 hours per week are not full-time and therefore are not eligible for carry-over under this policy.
Interns and contingent workers are excluded from carry-over regardless of scheduled hours.
Seasonal workers are treated as part-time for the purposes of this policy.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS by December 15 of the current year.
Managers must approve or deny requests within 5 business days of submission.
January usage of carried-over days is auto-approved when the carry-over request was previously approved.
Requests submitted after the deadline are auto-denied unless the HR business partner grants an exception.
Disputes are escalated to the regional HR business partner within 10 business days.

HR-207 Section 4.9 - Policy Exceptions
The regional HR business partner may grant exceptions of up to 5 additional carry-over days per employee per year.
Exceptions must be documented in the HRIS with a business justification.
All exceptions are reviewed in the annual policy audit each February.
""",
    "addendum_EMEA.txt": """Region: EMEA
Effective Date: 2026-02-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service.
Eligibility is assessed as of the last day of the fiscal year.
Continuous service is measured from the most recent hire date.
Where local law is more generous than this policy, local law prevails.
Agency workers are covered only where required by local regulation.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 6 days         |
| Regular       | 6 months - 2 yrs  | 12 days        |
| Senior        | > 2 yrs           | 18 days        |
Caps apply per calendar year and are not cumulative across years.
Statutory minimum carry-over rights in member states are unaffected by these caps.
Collective agreements may set higher caps for specific sites or roles.

HR-207 Section 4.3 - Sabbatical
After 5 years, EMEA employees receive a 4-week sabbatical.
The sabbatical is fully paid at the base salary rate.
It must be taken within 12 months of becoming eligible, in one continuous block.
Sabbatical time does not count toward continuous service for carry-over purposes.
Employees must give at least 3 months notice before taking the sabbatical.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on April 30 of the following calendar year.
| Employee Type | Expiry Date |
|---------------|-------------|
| Probationary  | April 30    |
| Regular       | April 30    |
| Senior        | July 31     |
Works councils may negotiate later expiry dates for specific sites.
Employees on long-term sick leave retain carried-over days for up to 15 months where statute requires.

HR-207 Section 4.5 - Payout on Termination
Unused carried-over days are paid at 100% of the base daily rate on any termination.
Payout follows local statutory timelines, which range from the final paycheck to 60 days.
Forfeiture of statutory carry-over is not permitted in EMEA jurisdictions.
Collective-agreement payout rules take precedence where they are more favorable.

HR-207 Section 4.6 - Negative Balance
Employees may borrow up to 3 vacation days ahead of accrual with manager and works-council approval.
Negative balances must be repaid within 6 months through accrual.
Some member states prohibit paycheck deductions; in those, repayment is by future accrual only.

HR-207 Section 4.7 - Part-time Rule
Part-time employees are eligible for carry-over on a pro-rata basis proportional to their FTE percentage.
A 50% FTE Regular employee, for example, may carry over up to 6 days.
Pro-rata calculations round up to the nearest half day.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS by November 30 of the current year.
Managers must respond within 10 business days.
Works councils receive quarterly reports of approved carry-over balances.
Sites with collective agreements follow the notice periods defined in those agreements.

HR-207 Section 4.9 - Policy Exceptions
Site HR leads may grant exceptions only where a collective agreement permits them.
Every exception must be reported to the works council at its next quarterly meeting.
The regional policy owner reviews all exceptions annually each March.
""",
    "addendum_APAC.txt": """Region: APAC
Effective Date: 2026-03-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service.
Eligibility is assessed as of the last day of the calendar year.
Continuous service is measured from the most recent hire date.
Seconded employees retain eligibility under their home-country terms.
Fixed-term contract employees are eligible from their start date.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 4 days         |
| Regular       | 6 months - 2 yrs  | 8 days         |
| Senior        | > 2 yrs           | 12 days        |
Caps apply per calendar year and are not cumulative across years.
Country-specific statutory minimums override these caps where more generous.
Carry-over is calculated on accrued, unused vacation balances as of December 31.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on June 30 of the following calendar year.
| Employee Type | Expiry Date |
|---------------|-------------|
| Probationary  | June 30     |
| Regular       | June 30     |
| Senior        | September 30|
Expired days are forfeited without payout except where local law requires payment.
Employees receive an HRIS reminder 60 days before expiry.

HR-207 Section 4.5 - Payout on Termination
Unused carried-over days are paid at 75% of the base daily rate on voluntary termination.
On involuntary termination, payout follows local statutory requirements.
Probationary employees are not eligible for carry-over payout.
Payment is made with the final payroll run of the employment month.
Payout rates are calculated on the base salary in effect on the separation date.

HR-207 Section 4.6 - Negative Balance
Employees may borrow up to 2 vacation days ahead of accrual with manager approval.
Negative balances must be repaid within 3 months through accrual.
Any remaining negative balance at separation is deducted from final pay where legally permitted.
Borrowing is not permitted during probation.

HR-207 Section 4.7 - Part-time Rule
Part-time employees are eligible for carry-over on a pro-rata basis proportional to contracted hours.
Eligibility requires at least 20 scheduled hours per week.
Pro-rata calculations round to the nearest half day.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS by December 1 of the current year.
Managers must approve or deny requests within 7 business days.
Peak-season blackout periods (local New Year holidays) require site-lead approval for carry-over usage.
Blackout dates are published per site each October.

HR-207 Section 4.9 - Policy Exceptions
Country HR managers may grant exceptions of up to 3 additional carry-over days per employee per year.
Exceptions require a written business justification stored in the HRIS.
All exceptions are reviewed in the regional audit each April.
Repeated exceptions for the same employee require regional HR approval.
""",
    "addendum_LATAM.txt": """Region: LATAM
Effective Date: 2026-04-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service.
Eligibility is assessed as of the last day of the calendar year.
Continuous service is measured from the most recent hire date.
Statutory vacation rights under local labor codes are unaffected by this policy.
Employees on statutory leave continue to accrue service toward eligibility.
Transferred employees keep their continuous service when moving between LATAM entities.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 5 days         |
| Regular       | 6 months - 2 yrs  | 10 days        |
| Senior        | > 2 yrs           | 15 days        |
Caps apply per calendar year and are not cumulative across years.
Carry-over balances are recorded in the statutory vacation ledger.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on December 31 of the year following accrual.
| Employee Type | Expiry Date  |
|---------------|--------------|
| Probationary  | December 31  |
| Regular       | December 31  |
| Senior        | March 31     |
Expired days are forfeited without payout unless local law requires otherwise.
Expiry dates follow the statutory vacation calendar of each country.
Employees receive a written notice 30 days before carried-over days expire.

HR-207 Section 4.5 - Payout on Termination
Unused carried-over days are paid at 100% of the base daily rate, as required by local labor codes.
Payout is included in the statutory termination settlement.
No employee type is excluded from payout where payment is statutorily required.
Settlement timelines follow each country's labor authority rules.

HR-207 Section 4.6 - Negative Balance
Negative vacation balances are not permitted in LATAM.
Vacation may only be taken after it has accrued.
No exceptions to this rule may be granted by managers or HR.
Accrual posting dates follow each country's statutory calendar.

HR-207 Section 4.7 - Part-time Rule
Part-time employees accrue and carry over vacation on a pro-rata basis as defined by local law.
There is no minimum-hours threshold for eligibility.
Pro-rata calculations follow the statutory formula of each country.
Part-time caps are derived from the full-time caps in Section 4.2.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS by November 15 of the current year.
Managers must approve or deny requests within 10 business days.
Approved carry-over is recorded in the annual statutory vacation ledger.
Requests that miss the deadline are deferred to the following cycle.

HR-207 Section 4.9 - Policy Exceptions
No manager-level exceptions are permitted; statutory rules govern carry-over.
Country HR may request a policy variance from the regional policy owner in writing.
Approved variances are published to all employees in the affected country.
""",
    "addendum_US.txt": """Region: US
Effective Date: 2026-05-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service. Continuous service means 40 hours per week for 52 weeks.
Eligibility is assessed as of the last day of the calendar year.
Continuous service is measured from the most recent hire date.
Approved leaves of absence do not interrupt continuous service but do not accrue toward it.
Seasonal and temporary employees are not covered by this policy.
Rehired employees restart their continuous service clock unless rehired within 30 days of separation.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 5 days         |
| Regular       | 6 months - 2 yrs  | 10 days        |
| Senior        | > 2 yrs           | 20 days        |
Caps apply per calendar year and are not cumulative across years.
State-mandated accrual protections override these caps where applicable.
Carry-over is calculated on accrued, unused vacation balances as of December 31.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on March 15 of the following calendar year.
| Employee Type | Expiry Date |
|---------------|-------------|
| Probationary  | March 15    |
| Regular       | March 15    |
| Senior        | May 31      |
Expired days are forfeited except in states that prohibit forfeiture of accrued vacation.
Employees receive an HRIS reminder 45 days before expiry.

HR-207 Section 4.5 - Payout on Termination
Exempt employees are paid for unused carried-over days at 100% of the base daily rate.
Non-exempt employees are paid per applicable state law.
In states that treat accrued vacation as wages, forfeiture on termination is not permitted.
Payouts are included in the final paycheck per state timing rules.

HR-207 Section 4.6 - Negative Balance
Employees may borrow up to 5 vacation days ahead of accrual with manager approval.
Borrowing is not permitted during the probationary period.
Negative balances must be repaid within 6 months through accrual.
Deduction of a negative balance from final pay is applied only where state law permits.

HR-207 Section 4.7 - Part-time Rule
Part-time employees working fewer than 40 hours per week do not meet the continuous-service definition and are not eligible for carry-over.
This exclusion applies regardless of tenure or employee type.
Job-share arrangements are treated as part-time for the purposes of this policy.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS by December 1 of the current year.
Managers must approve or deny requests within 5 business days.
Use of carried-over days requires at least 10 business days advance notice.
Late requests are considered only for documented medical or family emergencies.

HR-207 Section 4.9 - Policy Exceptions
The VP of HR may grant exceptions of up to 5 additional carry-over days per employee per year.
Exceptions must be documented in the HRIS with a business justification.
Exceptions in states with accrual-as-wages laws require Legal review.
All exceptions are reviewed in the annual policy audit each February.
Exception decisions are final and do not set precedent for other employees.
""",
    "addendum_UK.txt": """Region: UK
Effective Date: 2026-06-01

HR-207 Section 4.1 - Eligibility
Employees are eligible for carry-over based on continuous service.
Eligibility is assessed as of the last day of the leave year.
Continuous service is measured from the most recent hire date.
Statutory holiday rights under the Working Time Regulations are unaffected by this policy.
Agency workers are covered only after completing 12 continuous weeks in the same role.

HR-207 Section 4.2 - Carry-over Cap
The following carry-over limits apply:
| Employee Type | Continuous Service | Carry-over Cap |
|---------------|-------------------|----------------|
| Probationary  | < 6 months        | 7 days         |
| Regular       | 6 months - 2 yrs  | 14 days        |
| Senior        | > 2 yrs           | 21 days        |
Caps apply per leave year and are not cumulative across years.
The leave year runs from April 6 to April 5 of the following year.

HR-207 Section 4.3 - Sabbatical
After 10 years, UK employees receive a 6-week sabbatical.
The sabbatical is fully paid at the base salary rate.
It must be taken within 18 months of becoming eligible, in one continuous block.
Pension contributions continue during the sabbatical period.
Employees must give at least 3 months notice before taking the sabbatical.

HR-207 Section 4.4 - Carry-over Expiry
Carried-over days expire on April 5 of the following tax year.
| Employee Type | Expiry Date |
|---------------|-------------|
| Probationary  | April 5     |
| Regular       | April 5     |
| Senior        | June 30     |
Statutory holiday that cannot be taken due to long-term sickness may be carried over up to 18 months by law.
Expiry dates are visible in the HRIS balance view throughout the leave year.

HR-207 Section 4.5 - Payout on Termination
Unused carried-over days are paid at 100% of the base daily rate on any termination.
Payment in lieu of untaken statutory holiday is included in the final payslip.
Deductions for days taken beyond accrual follow the employment contract.

HR-207 Section 4.6 - Negative Balance
Employees may borrow up to 3 vacation days ahead of accrual with manager approval.
Negative balances must be repaid within 6 months through accrual.
Deductions from final pay follow the employment contract's deduction clause.

HR-207 Section 4.7 - Part-time Rule
Part-time employees receive carry-over on a pro-rata basis aligned with statutory holiday entitlement.
Pro-ration is calculated against the full-time equivalent cap for the employee type.
Pro-rata calculations round up to the nearest half day.

HR-207 Section 4.8 - Approval Procedure
Carry-over requests must be submitted in the HRIS at least 20 business days before the leave year ends.
Notice to use carried-over days must be at least twice the length of the leave requested.
Managers must respond within 5 business days of submission.
Requests over the holiday periods in December require site-lead approval.

HR-207 Section 4.9 - Policy Exceptions
The UK HR director may grant exceptions of up to 5 additional carry-over days per employee per leave year.
Exceptions must not reduce statutory holiday entitlements under the Working Time Regulations.
All exceptions are reviewed in the annual policy audit each May.
""",
}


def write_corpus(data_dir: str = "data") -> list:
    """Writes every addendum in ``DOCS`` to ``data_dir``.

    Args:
        data_dir: Target directory for the generated ``addendum_*.txt`` files.
            Created if it does not exist.

    Returns:
        Sorted list of file paths that were written.
    """
    os.makedirs(data_dir, exist_ok=True)
    written = []
    for fname, content in DOCS.items():
        path = os.path.join(data_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        written.append(path)
    return sorted(written)


def main() -> None:
    """Regenerates the full corpus and reports what was written."""
    written = write_corpus()
    print(f"Created {len(written)} data files:")
    for path in written:
        print(f"  {path}")


if __name__ == "__main__":
    main()
