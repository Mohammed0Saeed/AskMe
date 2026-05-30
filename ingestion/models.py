from dataclasses import dataclass, field
from typing import Optional
import uuid


@dataclass
class ChunkMetadata:
    """
    Carries every traceability and access-control field for a single chunk.
    All five required fields are enforced so nothing silently reaches the
    vector store without being tagged.
    """
    author: str           # Person or system that produced the source document
    date: str             # ISO-8601 creation/modification date, e.g. "2024-06-01"
    source_system: str    # Origin system: "PDF" | "Confluence" | "Teams"
    access_level: str     # "public" | "internal" | "confidential" | "restricted"
    domain: str           # Business domain: "Legal" | "Customer Service" | etc.
    source_file: str      # File path or URL that was ingested
    chunk_index: int      # Zero-based position within the parent document
    title: Optional[str] = None       # Document or page title when available
    page_number: Optional[int] = None # PDF page or Confluence page number
    url: Optional[str] = None         # Direct link back to the source


@dataclass
class DocumentChunk:
    """
    The atomic unit that flows through the pipeline: text + rich metadata.
    chunk_id is a UUID so every chunk is globally unique across all sources.
    """
    content: str
    metadata: ChunkMetadata
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class ParsedDocument:
    """
    Intermediate object returned by every parser before chunking.
    The parser is responsible for filling as many metadata fields as it can
    from the source; anything still unknown is left as "" for the enricher to fill.
    """
    content: str          # Full extracted text of the document
    author: str
    date: str
    source_system: str
    source_file: str
    access_level: str
    domain: str
    title: str = ""
    url: str = ""
    # PDF: list of {"page": int, "text": str} dicts for page-level chunking
    pages: Optional[list] = None
    # Teams: list of {"speaker": str, "timestamp": str, "text": str} dicts
    segments: Optional[list] = None
