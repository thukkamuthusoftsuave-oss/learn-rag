# Week 5 Manual Trace Review Sheet

**Goal:** run and read these 20 HR-policy questions through the app, write an
observation before assigning any category, then turn the observations into a
ranked error taxonomy.

Run the questions one at a time in the app. Record the full output/trace ID;
for a CLI run, use `policy-rag chat "<question>" --region <region>` and add
`--json` if you want the complete trace in the terminal. Leave out `--region`
where the sheet says **none**.

## The rule for every trace

1. Read the question, retrieved sources/chunks, and final answer.
2. Compare the answer with the expected behaviour in this sheet and the named
   policy section in `data/`.
3. Write one plain, factual observation first. Do not name a category yet.
4. Mark it as correct, correct refusal, retrieval failure, generation failure,
   or unclear. If incorrect, record a severity from 1 to 5.

**Fast diagnosis:** if the policy source that contains the answer was not
retrieved, it is a retrieval failure. If that source was retrieved but the
answer is wrong/incomplete, it is a generation failure. A correct refusal is
not a failure.

## Questions to run

| ID | Region | Question | Expected behaviour / policy to check |
|---|---|---|---|
| CORE-01 | NA | What is the carry-over cap for a probationary employee in NA? | Answer from `addendum_NA.txt`, HR-207 Section 4.2 |
| CORE-02 | EMEA | What is the carry-over cap for a regular employee with 1 year of service in EMEA? | Answer from `addendum_EMEA.txt`, Section 4.2 |
| CORE-03 | APAC | What is the carry-over cap for a senior employee in APAC? | Answer from `addendum_APAC.txt`, Section 4.2 |
| CORE-04 | LATAM | When does the HR-207 policy become effective in LATAM? | Answer from the header of `addendum_LATAM.txt` |
| CORE-05 | US | What defines continuous service in US for the carry-over policy? | Answer from `addendum_US.txt`, Section 4.1 |
| CORE-06 | UK | Who is eligible for the sabbatical in UK? | Answer from `addendum_UK.txt`, Section 4.3 |
| CORE-07 | US | What is the max carry-over for a senior with > 2 years of service in US? | Answer from `addendum_US.txt`, Section 4.2 |
| CORE-08 | NA | Does a regular employee in NA get 15 days carry-over cap? | Answer should be **no**; check `addendum_NA.txt`, Section 4.2 |
| OOC-01 | none | What is the maternity leave policy in EMEA? | Correct refusal; maternity leave is outside this corpus |
| OOC-02 | none | Who is eligible for sabbatical in LATAM? | Correct refusal; LATAM has no sabbatical clause |
| OOC-03 | none | What is the reimbursement limit for home office equipment? | Correct refusal; different policy family |
| OOC-04 | US | What is selfcare? | Correct refusal; not covered by this corpus |
| EDGE-01 | US | I am a part-time employee (20 hours/week) in the US and I have worked here for 3 years. How many carry-over days do I get? | Answer should be 0 days; check `addendum_US.txt`, Section 4.7 |
| EDGE-02 | NA | What happens to my carry-over balance if I resign without notice in NA? | Answer from `addendum_NA.txt`, Section 4.5 |
| EDGE-03 | NA | Can a contract worker claim carry-over in NA? | Answer from `addendum_NA.txt`, Section 4.1 |
| EDGE-04 | UK | When do carried-over days expire in UK? | Answer from `addendum_UK.txt`, Section 4.4 |
| EDGE-05 | APAC | How do I submit a carry-over request in APAC? | Answer from `addendum_APAC.txt`, Section 4.8 |
| EDGE-06 | EMEA | What is Section 4.9 about in EMEA? | Answer from `addendum_EMEA.txt`, Section 4.9 |
| EDGE-07 | EMEA | What is the sabbatical duration and eligibility in EMEA? | Both facts must be answered; check `addendum_EMEA.txt`, Section 4.3 |
| EDGE-08 | US | Can I borrow vacation days in advance in US, and what is the limit? | Answer from `addendum_US.txt`, Section 4.6 |

## Your review log

Fill one row immediately after each run. The open-coding observation must come
before the proposed problem group.

| ID | Trace ID / saved output | Retrieved sources correct? | Answer correct and complete? | Open-coding observation - one honest sentence | Proposed group (after observation) | Severity 1-5 |
|---|---|---|---|---|---|---|
| CORE-01 |  |  |  |  |  |  |
| CORE-02 |  |  |  |  |  |  |
| CORE-03 |  |  |  |  |  |  |
| CORE-04 |  |  |  |  |  |  |
| CORE-05 |  |  |  |  |  |  |
| CORE-06 |  |  |  |  |  |  |
| CORE-07 |  |  |  |  |  |  |
| CORE-08 |  |  |  |  |  |  |
| OOC-01 |  |  |  |  |  |  |
| OOC-02 |  |  |  |  |  |  |
| OOC-03 |  |  |  |  |  |  |
| OOC-04 |  |  |  |  |  |  |
| EDGE-01 |  |  |  |  |  |  |
| EDGE-02 |  |  |  |  |  |  |
| EDGE-03 |  |  |  |  |  |  |
| EDGE-04 |  |  |  |  |  |  |
| EDGE-05 |  |  |  |  |  |  |
| EDGE-06 |  |  |  |  |  |  |
| EDGE-07 |  |  |  |  |  |  |
| EDGE-08 |  |  |  |  |  |  |

## How to judge the answer

Use this same checklist every time.

- **Grounded:** does the answer state only what the named policy says? A made-up
  rule is wrong even if it sounds plausible.
- **Correct source and region:** for an answer question, was the expected
  addendum retrieved? For a refusal question, did it refuse instead of inventing
  a policy?
- **Complete:** did it include important conditions, exclusions, thresholds, and
  both requested facts? `EDGE-07` deliberately tests this.
- **Direct:** did it answer the question rather than provide irrelevant policy
  text?
- **Safe refusal:** when the policy is not in the corpus, did it clearly say it
  cannot answer from the provided documents?

For an incorrect answer, choose severity using this scale:

| Severity | Meaning |
|---:|---|
| 5 | Wrong regional policy or advice likely to cause a consequential HR decision |
| 4 | Confidently invented policy or a material wrong entitlement |
| 3 | Important condition/exclusion/fact missing, making the answer incomplete |
| 2 | Correct substance but citation/presentation issue |
| 1 | Minor wording issue; meaning remains clear and safe |

## After all 20 reviews: taxonomy and priority

Do not add a group until all observation sentences are written. Then group
similar failures under names a stranger understands, count them, and rank only
real bugs using **count × severity**.

| Priority | Problem group | Trace IDs | Count | Severity | Score (count x severity) | Why it happens / evidence |
|---:|---|---|---:|---:|---:|---|
| 1 |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |

## Final prediction card

Write this before changing any code.

| Field | Your answer |
|---|---|
| Chosen problem |  |
| Evidence | `__ / 20` traces; severity `__ / 5`; score `__` |
| One change only |  |
| Prediction |  |
| What it will not fix |  |
