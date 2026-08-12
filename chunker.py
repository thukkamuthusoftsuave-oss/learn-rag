import re

def naive_chunker(text, source_file):
    # Splits text into chunks of 4 lines
    lines = text.strip().split('\n')
    chunks = []
    for i in range(0, len(lines), 4):
        chunk_text = '\n'.join(lines[i:i+4])
        # Missing robust metadata in naive chunker
        chunks.append({
            'chunk_id': f"{source_file}_chunk_{i//4}",
            'text': chunk_text,
            'source_file': source_file,
            'policy_id': 'unknown',
            'region': 'unknown',
            'effective_date': 'unknown',
            'section': 'unknown'
        })
    return chunks

def structure_aware_chunker(text, source_file):
    # Extracts metadata from the document header and chunks by section header
    lines = text.strip().split('\n')
    chunks = []
    
    region = "unknown"
    effective_date = "unknown"
    policy_id = "HR-207" # Assuming all are HR-207 based on prompt
    
    current_section = "Header"
    current_chunk = []
    
    for line in lines:
        if line.startswith("Region:"):
            region = line.split(":", 1)[1].strip()
        elif line.startswith("Effective Date:"):
            effective_date = line.split(":", 1)[1].strip()
            
        section_match = re.match(r'^(HR-\d+ Section \d+\.\d+) - (.*)', line)
        if section_match:
            # Save previous section
            if current_chunk:
                chunks.append({
                    'chunk_id': f"{source_file}_{current_section.replace(' ', '_')}",
                    'text': '\n'.join(current_chunk),
                    'source_file': source_file,
                    'policy_id': policy_id,
                    'region': region,
                    'effective_date': effective_date,
                    'section': current_section
                })
            current_section = section_match.group(1)
            # Prepend section number to keep clauses attached to section numbers
            current_chunk = [line]
        else:
            current_chunk.append(line)
            
    # Add final chunk
    if current_chunk:
        chunks.append({
            'chunk_id': f"{source_file}_{current_section.replace(' ', '_')}",
            'text': '\n'.join(current_chunk),
            'source_file': source_file,
            'policy_id': policy_id,
            'region': region,
            'effective_date': effective_date,
            'section': current_section
        })
        
    return chunks
