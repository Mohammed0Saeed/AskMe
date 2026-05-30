"""
AskMe – Layer 1: Ingestion

Usage examples for every supported source type.
Set GEMINI_API_KEY in a .env file before running.
"""

import logging
from ingestion import IngestionPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

pipeline = IngestionPipeline()


# --- PDF ---
# domain="" triggers Gemini auto-detection; or pass e.g. domain="Legal"
pdf_chunks = pipeline.ingest_pdf(
    file_path="samples/policy.pdf",
    access_level="confidential",
    domain="",
)

# # --- Confluence (live API) ---
# confluence_chunks = pipeline.ingest_confluence_space(
#     base_url="https://yourcompany.atlassian.net",
#     username="you@yourcompany.com",
#     api_token="YOUR_ATLASSIAN_TOKEN",
#     space_key="CS",
#     access_level="internal",
#     domain="Customer Service",
# )
#
# # --- Confluence (HTML export) ---
# html_chunks = pipeline.ingest_confluence_html(
#     file_path="samples/exported_page.html",
#     access_level="internal",
#     domain="",
# )
#
# # --- Teams transcript (.vtt) ---
# teams_chunks = pipeline.ingest_teams_transcript(
#     file_path="samples/meeting.vtt",
#     meeting_organiser="Alice Smith",
#     meeting_date="2024-06-01",
#     meeting_title="Q2 Legal Review",
#     access_level="restricted",
#     domain="Legal",
# )

# Inspect a few chunks
for chunk in pdf_chunks[:3]:
    print(f"[{chunk.chunk_id[:8]}]")
    print(f"  domain      : {chunk.metadata.domain}")
    print(f"  author      : {chunk.metadata.author}")
    print(f"  date        : {chunk.metadata.date}")
    print(f"  access      : {chunk.metadata.access_level}")
    print(f"  source      : {chunk.metadata.source_system} p.{chunk.metadata.page_number}")
    print(f"  text preview: {chunk.content[:120]!r}")
    print()
