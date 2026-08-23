import asyncio
from ingestion.scraper import load_documents
from ingestion.chunking import chunk_text

# Use a real PRID to test scraping, cleaning, language detection, and chunking
# E.g. PRID 1996160
docs = load_documents(["1996160"], languages=("en", "hi", "bn"))
for doc in docs:
    print(f"--- Doc PRID: {doc.prid}, Lang: {doc.language} ---")
    print(f"Title: {doc.title}")
    print(f"Posted On: {doc.posted_on}")
    print(f"Raw Text Len: {len(doc.raw_text)}")
    print(f"Snippet: {doc.raw_text[:100]}")
    
    chunks = chunk_text(doc.raw_text, doc.language, chunk_size=200, overlap_sentences=1)
    print(f"Produced {len(chunks)} chunks.")
    if chunks:
        print(f"Chunk 0: {chunks[0]}")
        if len(chunks) > 1:
            print(f"Chunk 1: {chunks[1]}")
    print()
