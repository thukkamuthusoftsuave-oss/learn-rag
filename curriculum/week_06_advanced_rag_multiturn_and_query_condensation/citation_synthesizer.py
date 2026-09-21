"""Week 6: Citation Synthesis & Verification.

Enforces structured citation tags [[HR-207 Section X.Y]] and maps them
to retrieved source documents.
"""

import re
from typing import List, Dict, Any, Tuple


def extract_citations(text: str) -> List[str]:
    """Extracts all [[HR-207 Section X.Y]] tags from an answer."""
    pattern = re.compile(r"\[\[(.*?)\]\]")
    return pattern.findall(text)


def verify_citations(answer: str, retrieved_chunks: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Verifies that all citations in the answer actually exist in the retrieved chunks."""
    citations = extract_citations(answer)
    if not citations:
        return False, ["Missing citations: Answer contains no [[HR-207 Section X.Y]] tags."]

    retrieved_sections = {c.get("section", "").strip() for c in retrieved_chunks}
    retrieved_filenames = {c.get("filename", "").strip() for c in retrieved_chunks}

    invalid_citations = []
    for cite in citations:
        # Match against either section name or filename
        matched = any(cite in sec for sec in retrieved_sections) or (cite in retrieved_filenames)
        if not matched:
            invalid_citations.append(f"Citation '{cite}' not grounded in retrieved context.")

    return (len(invalid_citations) == 0), invalid_citations
