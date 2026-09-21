"""Week 2: Structure-Aware Chunking & Metadata Extraction.

Splits policy documents along natural semantic headers (HR-207 Section X.Y)
and attaches rich metadata (region, policy_id, section, effective_date).
"""

import re
from typing import List, Dict, Any


def extract_document_metadata(text: str) -> Dict[str, str]:
    """Extracts document-level metadata from headers."""
    region_match = re.search(r"Region:\s*([A-Za-z]+)", text)
    effective_match = re.search(r"Effective Date:\s*([0-9\-]+)", text)
    
    return {
        "policy_id": "HR-207",
        "region": region_match.group(1).strip() if region_match else "unknown",
        "effective_date": effective_match.group(1).strip() if effective_match else "unknown",
    }


def structure_aware_chunk_text(text: str, filename: str = "") -> List[Dict[str, Any]]:
    """Splits text on 'HR-207 Section X.Y' headers, maintaining cohesive tables."""
    doc_meta = extract_document_metadata(text)
    
    # Header pattern: HR-207 Section X.Y
    section_pattern = re.compile(r"(HR-207\s+Section\s+\d+\.\d+[^\n]*)", re.IGNORECASE)
    
    parts = section_pattern.split(text)
    chunks = []
    
    # The first part is document preamble/header
    if parts and parts[0].strip():
        preamble_text = parts[0].strip()
        chunks.append({
            "chunk_id": f"{doc_meta['region']}_preamble",
            "text": preamble_text,
            "section": "Header",
            "region": doc_meta["region"],
            "policy_id": doc_meta["policy_id"],
            "effective_date": doc_meta["effective_date"],
            "filename": filename,
            "strategy": "structure_aware_preamble",
        })
    
    # Subsequent parts alternate: [section_header, section_content, ...]
    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        body = parts[i + 1].strip() if (i + 1) < len(parts) else ""
        full_section_text = f"{header}\n{body}".strip()
        
        # Extract section number (e.g. 4.1, 4.2)
        sec_num_match = re.search(r"Section\s+(\d+\.\d+)", header, re.IGNORECASE)
        sec_num = sec_num_match.group(1) if sec_num_match else "unknown"
        
        chunks.append({
            "chunk_id": f"{doc_meta['region']}_sec_{sec_num.replace('.', '_')}",
            "text": full_section_text,
            "section": f"HR-207 Section {sec_num}",
            "region": doc_meta["region"],
            "policy_id": doc_meta["policy_id"],
            "effective_date": doc_meta["effective_date"],
            "filename": filename,
            "strategy": "structure_aware_section",
        })
        
    return chunks
