import logging
from typing import List, Optional

from ingestion.chunker import chunk_text, chunk_pages, chunk_segments
from ingestion.metadata_enricher import MetadataEnricher
from ingestion.models import ChunkMetadata, DocumentChunk, ParsedDocument
from ingestion.parsers.confluence_parser import ConfluenceAPIParser, ConfluenceHTMLParser
from ingestion.parsers.pdf_parser import PDFParser
from ingestion.parsers.teams_parser import TeamsTranscriptParser

logger = logging.getLogger(__name__)


def _build_chunks(doc: ParsedDocument, enriched_meta: dict) -> List[DocumentChunk]:
    """
    Converts a ParsedDocument into a list of DocumentChunks after enrichment.
    Chooses the chunking strategy based on what the parser produced:
      - pages   → page-aware chunking (PDFs) so page_number is set on every chunk
      - segments → speaker-aware chunking (Teams) so author reflects the speaker
      - content  → plain text chunking (Confluence HTML, generic)
    The enriched_meta dict (author, date, domain) overwrites whatever the parser
    found only for fields that were originally empty; existing values are kept.
    """
    chunks: List[DocumentChunk] = []

    base_author = enriched_meta.get("author") or doc.author
    base_date = enriched_meta.get("date") or doc.date
    domain = enriched_meta.get("domain") or doc.domain

    if doc.pages:
        # PDF path: one chunk per page-slice, preserving page number
        page_chunks = chunk_pages(doc.pages)
        for c in page_chunks:
            meta = ChunkMetadata(
                author=base_author,
                date=base_date,
                source_system=doc.source_system,
                access_level=doc.access_level,
                domain=domain,
                source_file=doc.source_file,
                chunk_index=c["chunk_index"],
                title=doc.title,
                page_number=c["page"],
                url=doc.url or None,
            )
            chunks.append(DocumentChunk(content=c["text"], metadata=meta))

    elif doc.segments:
        # Teams path: speaker is the author of each individual chunk
        seg_chunks = chunk_segments(doc.segments)
        for c in seg_chunks:
            meta = ChunkMetadata(
                author=c["speaker"],     # override with actual speaker
                date=base_date,
                source_system=doc.source_system,
                access_level=doc.access_level,
                domain=domain,
                source_file=doc.source_file,
                chunk_index=c["chunk_index"],
                title=doc.title,
                url=doc.url or None,
            )
            chunks.append(DocumentChunk(content=c["text"], metadata=meta))

    else:
        # Confluence / generic path: flat text chunking
        text_chunks = chunk_text(doc.content)
        for idx, text in enumerate(text_chunks):
            meta = ChunkMetadata(
                author=base_author,
                date=base_date,
                source_system=doc.source_system,
                access_level=doc.access_level,
                domain=domain,
                source_file=doc.source_file,
                chunk_index=idx,
                title=doc.title,
                url=doc.url or None,
            )
            chunks.append(DocumentChunk(content=text, metadata=meta))

    return chunks


class IngestionPipeline:
    """
    Top-level orchestrator for Layer 1.  Wires together:
      parser → MetadataEnricher (Gemini) → chunker → List[DocumentChunk]
    Each public method corresponds to one source type and returns a flat list
    of fully-tagged DocumentChunks ready for the vector store (Layer 2).
    Pass domain="" or domain="auto" to let Gemini detect the domain from content.
    """

    def __init__(self) -> None:
        self._enricher = MetadataEnricher()

    def _enrich_and_chunk(self, doc: ParsedDocument) -> List[DocumentChunk]:
        """
        Calls MetadataEnricher for any metadata field the parser left blank,
        then delegates to _build_chunks.  Using a sample of the document text
        (first 1500 chars) keeps Gemini costs low while still being representative.
        """
        sample = doc.content[:1500]
        enriched = self._enricher.enrich(
            text=sample,
            author=doc.author,
            date=doc.date,
            domain=doc.domain,
        )
        chunks = _build_chunks(doc, enriched)
        logger.info(
            "Ingested '%s' → %d chunks [domain=%s, access=%s]",
            doc.title or doc.source_file,
            len(chunks),
            enriched["domain"],
            doc.access_level,
        )
        return chunks

    def ingest_pdf(
        self,
        file_path: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> List[DocumentChunk]:
        """
        Ingests a local PDF file.  Extracts text page-by-page so page numbers
        appear in chunk metadata.  Author and date are read from the PDF's own
        metadata fields (Author, CreationDate); missing values are filled by Gemini.
        """
        parser = PDFParser()
        doc = parser.parse(file_path, access_level=access_level, domain=domain)
        return self._enrich_and_chunk(doc)

    def ingest_confluence_space(
        self,
        base_url: str,
        username: str,
        api_token: str,
        space_key: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> List[DocumentChunk]:
        """
        Ingests all pages in a Confluence Cloud space via the REST API.
        Each page is enriched and chunked independently.  The combined list of
        all chunks from all pages is returned so the caller handles them uniformly.
        """
        parser = ConfluenceAPIParser(base_url, username, api_token)
        documents: List[ParsedDocument] = parser.parse(
            space_key, access_level=access_level, domain=domain
        )
        all_chunks: List[DocumentChunk] = []
        for doc in documents:
            all_chunks.extend(self._enrich_and_chunk(doc))
        return all_chunks

    def ingest_confluence_html(
        self,
        file_path: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> List[DocumentChunk]:
        """
        Ingests a single Confluence page exported as HTML.
        Use this when live API access is unavailable (e.g. offline archives).
        """
        parser = ConfluenceHTMLParser()
        doc = parser.parse(file_path, access_level=access_level, domain=domain)
        return self._enrich_and_chunk(doc)

    def ingest_teams_transcript(
        self,
        file_path: str,
        meeting_organiser: str = "",
        meeting_date: str = "",
        meeting_title: str = "",
        access_level: str = "internal",
        domain: str = "",
    ) -> List[DocumentChunk]:
        """
        Ingests a Teams meeting transcript (.vtt or .json).
        Each chunk's author field is set to the individual speaker, not the
        meeting organiser, so per-person attribution is preserved in the metadata.
        If meeting_date is not supplied, Gemini will attempt to extract it from
        the transcript text.
        """
        parser = TeamsTranscriptParser()
        doc = parser.parse(
            file_path,
            meeting_organiser=meeting_organiser,
            meeting_date=meeting_date,
            meeting_title=meeting_title,
            access_level=access_level,
            domain=domain,
        )
        return self._enrich_and_chunk(doc)
