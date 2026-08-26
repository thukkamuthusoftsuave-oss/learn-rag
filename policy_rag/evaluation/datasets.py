"""The golden question sets every evaluation suite scores against.

One file, one definition of each question. The retrieval benchmark, the
chunking bake-off, the answer-quality run and the smoke checks all read from
here, so a question cannot mean one thing in one report and something else in
another.

Four sets, each with a job:

``CORE_QUERIES``
    Eight known-answer questions, region named explicitly. Written before any
    retrieval was ever run and never tuned to observed results - that is what
    makes them evidence rather than decoration.
``HARD_QUERIES``
    Retrieval stress cases: no region named, or an exact term (a service
    threshold, a section number) that a biencoder blurs but BM25 matches
    literally. This is where hybrid retrieval earns its place.
``REFUSAL_QUERIES``
    Out-of-corpus topics. The correct behaviour is the exact refusal sentence,
    not a plausible-sounding answer.
``EDGE_QUERIES``
    In-corpus but demanding: a clause that disqualifies the obvious cap-table
    row, an expiry rule, a procedure buried in a later section.
"""

from dataclasses import dataclass

# Region codes that appear in the corpus, in the order used for display.
REGIONS = ["NA", "US", "UK", "EMEA", "APAC", "LATAM"]


@dataclass(frozen=True)
class GoldenQuery:
    """One evaluation question and what a correct system does with it.

    Attributes:
        id: Stable identifier used in reports and traces.
        query: The question as a user would type it.
        region: Region filter to apply, or None to leave retrieval unfiltered.
        expected_type: ``"answer"`` or ``"refusal"``.
        expected_source: File that must be retrieved, or None when no single
            document is correct.
        expected_section: Section holding the answer, for the chunking bake-off.
        note: Why this question is in the set.
        ambiguous: True when no single source is correct, so the question is
            excluded from metrics and reported as a known limitation.
    """

    id: str
    query: str
    region: str = None
    expected_type: str = "answer"
    expected_source: str = None
    expected_section: str = None
    note: str = ""
    ambiguous: bool = False

    def expectation(self) -> dict:
        """Returns the gold fields the taxonomy needs to label a trace."""
        return {
            "golden_id": self.id,
            "expected_type": self.expected_type,
            "expected_source": self.expected_source,
            "expected_section": self.expected_section,
        }


CORE_QUERIES = [
    GoldenQuery(
        id="CORE-01",
        query="What is the carry-over cap for a probationary employee in NA?",
        region="NA",
        expected_source="addendum_NA.txt",
        expected_section="HR-207 Section 4.2",
        note="Cap table row selected by employee type.",
    ),
    GoldenQuery(
        id="CORE-02",
        query="What is the carry-over cap for a regular employee with 1 year of service in EMEA?",
        region="EMEA",
        expected_source="addendum_EMEA.txt",
        expected_section="HR-207 Section 4.2",
        note="Cap table row selected by service length.",
    ),
    GoldenQuery(
        id="CORE-03",
        query="What is the carry-over cap for a senior employee in APAC?",
        region="APAC",
        expected_source="addendum_APAC.txt",
        expected_section="HR-207 Section 4.2",
        note="Same question shape, different region - tests region separation.",
    ),
    GoldenQuery(
        id="CORE-04",
        query="When does the HR-207 policy become effective in LATAM?",
        region="LATAM",
        expected_source="addendum_LATAM.txt",
        expected_section="Header",
        note="Answer lives in the document header, not a section.",
    ),
    GoldenQuery(
        id="CORE-05",
        query="What defines continuous service in US for the carry-over policy?",
        region="US",
        expected_source="addendum_US.txt",
        expected_section="HR-207 Section 4.1",
        note="Definition clause that gates every cap.",
    ),
    GoldenQuery(
        id="CORE-06",
        query="Who is eligible for the sabbatical in UK?",
        region="UK",
        expected_source="addendum_UK.txt",
        expected_section="HR-207 Section 4.3",
        note="Section that exists only in EMEA and UK.",
    ),
    GoldenQuery(
        id="CORE-07",
        query="What is the max carry-over for a senior with > 2 years of service in US?",
        region="US",
        expected_source="addendum_US.txt",
        expected_section="HR-207 Section 4.2",
        note="Numeric threshold in the query text.",
    ),
    GoldenQuery(
        id="CORE-08",
        query="Does a regular employee in NA get 15 days carry-over cap?",
        region="NA",
        expected_source="addendum_NA.txt",
        expected_section="HR-207 Section 4.2",
        note="Yes/no question whose correct answer is 'no' - 15 is the senior cap.",
    ),
]

HARD_QUERIES = [
    GoldenQuery(
        id="HARD-01",
        query="After 10 years of service what sabbatical am I entitled to?",
        expected_source="addendum_UK.txt",
        expected_section="HR-207 Section 4.3",
        note="Only UK grants a sabbatical at 10 years; '10 years' is an exact BM25 target.",
    ),
    GoldenQuery(
        id="HARD-02",
        query="After 5 years of service what sabbatical am I entitled to?",
        expected_source="addendum_EMEA.txt",
        expected_section="HR-207 Section 4.3",
        note="Only EMEA grants a sabbatical at 5 years; vector search conflates it with UK.",
    ),
    GoldenQuery(
        id="HARD-03",
        query="What does HR-207 Section 4.8 say about approval deadlines in APAC?",
        expected_source="addendum_APAC.txt",
        expected_section="HR-207 Section 4.8",
        note="Literal section number - the clearest case for keyword matching.",
    ),
    GoldenQuery(
        id="HARD-04",
        query="What is the carry-over cap for a senior employee with more than 2 years of service?",
        expected_source=None,
        note="No region named at all. Neither retriever can fix this; it needs a region filter.",
        ambiguous=True,
    ),
]

REFUSAL_QUERIES = [
    GoldenQuery(
        id="OOC-01",
        query="What is the maternity leave policy in EMEA?",
        expected_type="refusal",
        note="Adjacent HR topic that the corpus deliberately never mentions.",
    ),
    GoldenQuery(
        id="OOC-02",
        query="Who is eligible for sabbatical in LATAM?",
        expected_type="refusal",
        note="Real section, wrong region - LATAM has no sabbatical clause.",
    ),
    GoldenQuery(
        id="OOC-03",
        query="What is the reimbursement limit for home office equipment?",
        expected_type="refusal",
        note="Different policy family entirely.",
    ),
    GoldenQuery(
        id="OOC-04",
        query="What is selfcare?",
        region="US",
        expected_type="refusal",
        note="Vague, near-topical question with a region filter still applied.",
    ),
]

EDGE_QUERIES = [
    GoldenQuery(
        id="EDGE-01",
        query=(
            "I am a part-time employee (20 hours/week) in the US and I have worked here "
            "for 3 years. How many carry-over days do I get?"
        ),
        region="US",
        expected_source="addendum_US.txt",
        expected_section="HR-207 Section 4.7",
        note="Eligibility clause disqualifies the obvious senior cap-table row.",
    ),
    GoldenQuery(
        id="EDGE-02",
        query="What happens to my carry-over balance if I resign without notice in NA?",
        region="NA",
        expected_source="addendum_NA.txt",
        expected_section="HR-207 Section 4.5",
        note="Forfeiture rule in a later section.",
    ),
    GoldenQuery(
        id="EDGE-03",
        query="Can a contract worker claim carry-over in NA?",
        region="NA",
        expected_source="addendum_NA.txt",
        expected_section="HR-207 Section 4.1",
        note="Exclusion stated in the eligibility section.",
    ),
    GoldenQuery(
        id="EDGE-04",
        query="When do carried-over days expire in UK?",
        region="UK",
        expected_source="addendum_UK.txt",
        expected_section="HR-207 Section 4.4",
        note="Expiry date differs per region.",
    ),
    GoldenQuery(
        id="EDGE-05",
        query="How do I submit a carry-over request in APAC?",
        region="APAC",
        expected_source="addendum_APAC.txt",
        expected_section="HR-207 Section 4.8",
        note="Procedural rather than entitlement question.",
    ),
    GoldenQuery(
        id="EDGE-06",
        query="What is Section 4.9 about in EMEA?",
        region="EMEA",
        expected_source="addendum_EMEA.txt",
        expected_section="HR-207 Section 4.9",
        note="Asks for a section by number rather than by topic.",
    ),
    GoldenQuery(
        id="EDGE-07",
        query="What is the sabbatical duration and eligibility in EMEA?",
        region="EMEA",
        expected_source="addendum_EMEA.txt",
        expected_section="HR-207 Section 4.3",
        note="Two facts must come from the same section.",
    ),
    GoldenQuery(
        id="EDGE-08",
        query="Can I borrow vacation days in advance in US, and what is the limit?",
        region="US",
        expected_source="addendum_US.txt",
        expected_section="HR-207 Section 4.6",
        note="Advance-borrowing rule with a numeric limit.",
    ),
]

# Ranking quality: region-explicit baseline plus the exact-term stress cases.
RETRIEVAL_SUITE = CORE_QUERIES + HARD_QUERIES

# Answer quality: what the assistant actually says, including when it should
# say nothing at all.
ANSWER_QUALITY_SUITE = CORE_QUERIES + REFUSAL_QUERIES + EDGE_QUERIES

# Fast end-to-end confidence check: one forced refusal, one query whose region
# comes only from the metadata filter, and one reasoning trap.
SMOKE_SUITE = [
    REFUSAL_QUERIES[0],
    GoldenQuery(
        id="SMOKE-REGION",
        query="What is the carry-over cap for a probationary employee?",
        region="US",
        expected_source="addendum_US.txt",
        expected_section="HR-207 Section 4.2",
        note="Region is supplied by the filter, not by the query text.",
    ),
    EDGE_QUERIES[0],
]

ALL_QUERIES = CORE_QUERIES + HARD_QUERIES + REFUSAL_QUERIES + EDGE_QUERIES + [
    query for query in SMOKE_SUITE
    if query.id not in {q.id for q in CORE_QUERIES + HARD_QUERIES + REFUSAL_QUERIES + EDGE_QUERIES}
]


def by_id(query_id: str) -> GoldenQuery:
    """Looks up a golden query by its identifier.

    Args:
        query_id: Identifier such as ``"CORE-01"``.

    Returns:
        The matching ``GoldenQuery``.

    Raises:
        KeyError: If no query has that identifier.
    """
    for query in ALL_QUERIES:
        if query.id == query_id:
            return query
    raise KeyError(query_id)
