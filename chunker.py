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
            'source_file': source_file
        })
    return chunks
