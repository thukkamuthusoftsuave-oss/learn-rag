"""Week 1: Naive Chunking Implementation.

Splits policy documents using arbitrary fixed line or character boundaries
without awareness of headings, tables, or semantic units.
"""

from typing import List, Dict, Any


def naive_chunk_text(text: str, lines_per_chunk: int = 4, overlap_lines: int = 0) -> List[Dict[str, Any]]:
    """Splits raw text into arbitrary line-bounded chunks.
    
    This demonstrates the naive approach where documents are split strictly
    by line count or token count without understanding semantic boundaries.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks = []
    step = max(1, lines_per_chunk - overlap_lines)
    
    for i in range(0, len(lines), step):
        chunk_slice = lines[i : i + lines_per_chunk]
        if not chunk_slice:
            continue
        chunk_content = "\n".join(chunk_slice)
        chunks.append({
            "chunk_id": f"naive_chunk_{len(chunks)}",
            "text": chunk_content,
            "start_line": i,
            "end_line": min(i + lines_per_chunk, len(lines)),
            "strategy": "naive_line_split",
        })
    return chunks
