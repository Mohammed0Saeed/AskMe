"""
Quick smoke-test for Layer 1.  Runs three checks in order:
  1. Chunker — no external deps, must always pass
  2. Teams parser + Gemini enrichment — uses the sample VTT in samples/
  3. PDF parser — skipped with a clear message if no sample PDF is present
Run from the project root:  python test_ingestion.py
"""

import sys
import os

# ── 1. Chunker ────────────────────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Chunker (no external deps)")
print("=" * 60)

from ingestion.chunker import chunk_text

LONG_TEXT = (
    "The policy defines the acceptable use of corporate IT resources. "
    "Employees must not share passwords or access credentials with anyone. "
    "All data classified as confidential must be encrypted at rest and in transit. "
    "Violations may result in disciplinary action up to and including termination. "
    "This policy is reviewed annually by the Information Security team. "
    "Questions should be directed to security@company.com. "
) * 6  # ~420 words — forces multiple chunks

chunks = chunk_text(LONG_TEXT)
assert len(chunks) > 1, "Long text should produce multiple chunks"
for i, c in enumerate(chunks):
    assert len(c) <= 512 + 64, f"Chunk {i} too long: {len(c)} chars"
print(f"  PASS — {len(chunks)} chunks produced, all within size limit")


# ── 2. Teams parser + Gemini enrichment ───────────────────────────────────────
print()
print("=" * 60)
print("TEST 2: Teams VTT parser + Gemini metadata enrichment")
print("=" * 60)

from ingestion import IngestionPipeline

pipeline = IngestionPipeline()

VTT_PATH = "samples/meeting.vtt"
assert os.path.isfile(VTT_PATH), f"Sample VTT not found at {VTT_PATH}"

chunks = pipeline.ingest_teams_transcript(
    file_path=VTT_PATH,
    meeting_organiser="Alice Smith",
    meeting_date="2024-06-01",
    meeting_title="Q2 Contract Review",
    access_level="confidential",
    domain="",          # intentionally blank → Gemini should detect "Legal" or similar
)

assert len(chunks) > 0, "Teams parser produced zero chunks"
print(f"  Chunks produced : {len(chunks)}")
print()
for chunk in chunks:
    print(f"  [{chunk.chunk_id[:8]}]")
    print(f"    author        : {chunk.metadata.author}")
    print(f"    domain        : {chunk.metadata.domain}   ← Gemini detected")
    print(f"    access_level  : {chunk.metadata.access_level}")
    print(f"    source_system : {chunk.metadata.source_system}")
    print(f"    text preview  : {chunk.content[:90]!r}")
    print()
print("  PASS")


# ── 3. PDF parser ─────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("TEST 3: PDF parser")
print("=" * 60)

PDF_PATH = "samples/policy.pdf"
if not os.path.isfile(PDF_PATH):
    print(f"  SKIP — drop any PDF at {PDF_PATH} to test this path")
else:
    pdf_chunks = pipeline.ingest_pdf(
        file_path=PDF_PATH,
        access_level="internal",
        domain="",
    )
    assert len(pdf_chunks) > 0, "PDF parser produced zero chunks"
    print(f"  Chunks produced: {len(pdf_chunks)}")
    c = pdf_chunks[0]
    print(f"  First chunk:")
    print(f"    author   : {c.metadata.author}")
    print(f"    date     : {c.metadata.date}")
    print(f"    domain   : {c.metadata.domain}")
    print(f"    page     : {c.metadata.page_number}")
    print(f"    preview  : {c.content[:90]!r}")
    print("  PASS")

print()
print("All tests done.")
