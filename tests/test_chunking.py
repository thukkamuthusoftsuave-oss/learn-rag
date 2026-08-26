"""Tests for the chunkers - the only pieces that need no models or index."""

from policy_rag.corpus.chunking import naive_chunker, structure_aware_chunker

SAMPLE = """Region: US
Effective Date: 2026-01-01

HR-207 Section 4.1 - Eligibility
Employees must be full-time.
Continuous service means uninterrupted employment.

HR-207 Section 4.2 - Carry-over Cap
| Employee Type | Cap |
| Senior        | 15  |
"""


def test_structure_chunker_splits_on_sections():
    """One chunk per section, plus the leading header chunk."""
    chunks = structure_aware_chunker(SAMPLE, "addendum_US.txt")
    sections = [c["section"] for c in chunks]
    assert sections == ["Header", "HR-207 Section 4.1", "HR-207 Section 4.2"]


def test_structure_chunker_stamps_metadata_on_every_chunk():
    """Region, effective date and policy id reach every chunk, header included."""
    chunks = structure_aware_chunker(SAMPLE, "addendum_US.txt")
    assert all(c["region"] == "US" for c in chunks)
    assert all(c["effective_date"] == "2026-01-01" for c in chunks)
    assert all(c["policy_id"] == "HR-207" for c in chunks)
    assert all(c["source_file"] == "addendum_US.txt" for c in chunks)


def test_section_header_stays_with_its_clauses():
    """The header line leads its own chunk, so clauses keep their section number."""
    chunks = structure_aware_chunker(SAMPLE, "addendum_US.txt")
    cap_chunk = next(c for c in chunks if c["section"] == "HR-207 Section 4.2")
    assert cap_chunk["text"].startswith("HR-207 Section 4.2 - Carry-over Cap")
    assert "Senior" in cap_chunk["text"]


def test_naive_chunker_has_no_metadata():
    """The baseline loses exactly what the structure-aware chunker preserves."""
    chunks = naive_chunker(SAMPLE, "addendum_US.txt")
    assert chunks, "naive chunker produced nothing"
    assert all(c["region"] == "unknown" for c in chunks)
    assert all(c["section"] == "unknown" for c in chunks)


def test_naive_chunker_covers_every_line():
    """Fixed windows must not drop content, however badly they cut it."""
    chunks = naive_chunker(SAMPLE, "addendum_US.txt")
    rejoined = "\n".join(c["text"] for c in chunks)
    assert rejoined == SAMPLE.strip()


def test_chunk_ids_are_unique_per_document():
    """Chunk ids are used as citation targets, so they must not collide."""
    for chunker in (naive_chunker, structure_aware_chunker):
        ids = [c["chunk_id"] for c in chunker(SAMPLE, "addendum_US.txt")]
        assert len(ids) == len(set(ids))
