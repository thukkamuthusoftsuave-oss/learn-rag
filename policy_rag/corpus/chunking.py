"""Chunking strategies for the policy corpus.

Two implementations are kept side by side because the difference between them
is the project's headline measurement (see
``policy_rag.evaluation.chunking``): the naive chunker splits blindly every
four lines and loses the metadata that makes a policy answer verifiable, while
the structure-aware chunker splits on ``HR-207 Section X.Y`` headers and
carries region, effective date and section into every chunk.

Both return a list of dicts with the same keys so the evaluation can compare
them directly: ``chunk_id``, ``text``, ``source_file``, ``policy_id``,
``region``, ``effective_date`` and ``section``.
"""

import re

NAIVE_CHUNK_LINES = 4

# "HR-207 Section 4.2 - Carry-over Cap" -> ("HR-207 Section 4.2", "Carry-over Cap")
SECTION_HEADER_RE = re.compile(r"^(HR-\d+ Section \d+\.\d+) - (.*)")

# "Region: US" / "Effective Date: 2026-01-01" — the header contract that
# policy_rag.corpus.generator writes and the indexer also relies on.
REGION_PREFIX = "Region:"
EFFECTIVE_DATE_PREFIX = "Effective Date:"


def naive_chunker(text: str, source_file: str) -> list:
    """Splits a document into fixed windows of four lines.

    The baseline strategy. It has no notion of section boundaries, so a cap
    table can be severed from the section header that gives it meaning, and it
    cannot populate region or section metadata.

    Args:
        text: Full document text.
        source_file: File name recorded on every chunk.

    Returns:
        List of chunk dicts with ``unknown`` for every metadata field.
    """
    lines = text.strip().split("\n")
    chunks = []
    for i in range(0, len(lines), NAIVE_CHUNK_LINES):
        chunks.append({
            "chunk_id": f"{source_file}_chunk_{i // NAIVE_CHUNK_LINES}",
            "text": "\n".join(lines[i:i + NAIVE_CHUNK_LINES]),
            "source_file": source_file,
            "policy_id": "unknown",
            "region": "unknown",
            "effective_date": "unknown",
            "section": "unknown",
        })
    return chunks


def structure_aware_chunker(text: str, source_file: str) -> list:
    """Splits a document on its section headers and attaches metadata.

    The header lines (``Region:``, ``Effective Date:``) are read once and
    stamped onto every chunk, and each section header starts a new chunk with
    the header line kept as the chunk's first line so clauses stay attached to
    the section number that governs them.

    Args:
        text: Full document text.
        source_file: File name recorded on every chunk.

    Returns:
        List of chunk dicts, one per section (plus a leading ``Header`` chunk).
    """
    lines = text.strip().split("\n")
    chunks = []

    region = "unknown"
    effective_date = "unknown"
    # Read the policy id off the document itself (a pre-pass, so the leading
    # Header chunk carries it too) rather than hardcoding a constant, so a
    # second policy family can be added without a code change.
    policy_id = _detect_policy_id(lines)

    current_section = "Header"
    current_chunk = []

    def flush() -> None:
        """Closes the section being accumulated and appends it to ``chunks``."""
        if not current_chunk:
            return
        chunks.append({
            "chunk_id": f"{source_file}_{current_section.replace(' ', '_')}",
            "text": "\n".join(current_chunk),
            "source_file": source_file,
            "policy_id": policy_id,
            "region": region,
            "effective_date": effective_date,
            "section": current_section,
        })

    for line in lines:
        if line.startswith(REGION_PREFIX):
            region = line.split(":", 1)[1].strip()
        elif line.startswith(EFFECTIVE_DATE_PREFIX):
            effective_date = line.split(":", 1)[1].strip()

        section_match = SECTION_HEADER_RE.match(line)
        if section_match:
            flush()
            current_section = section_match.group(1)
            current_chunk = [line]
        else:
            current_chunk.append(line)

    flush()
    return chunks


def _detect_policy_id(lines: list) -> str:
    """Returns the policy id (e.g. ``HR-207``) from the first section header.

    Args:
        lines: The document's lines.

    Returns:
        The policy id, or ``"unknown"`` when the document has no section header.
    """
    for line in lines:
        match = SECTION_HEADER_RE.match(line)
        if match:
            return match.group(1).split(" Section ")[0]
    return "unknown"
