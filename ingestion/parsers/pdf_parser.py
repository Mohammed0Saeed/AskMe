import os
from datetime import datetime
from typing import Optional

import pdfplumber

from ingestion.models import ParsedDocument
from ingestion.parsers.base_parser import BaseParser


def _parse_pdf_date(raw: Optional[str]) -> str:
    """
    Converts the PDF date string format "D:YYYYMMDDHHmmSS" into ISO-8601.
    Returns the raw string unchanged if it does not match the expected pattern,
    and an empty string if the input is None.
    """
    if not raw:
        return ""
    # Strip the leading "D:" prefix used in PDF metadata
    raw = raw.lstrip("D:").split("+")[0].split("-")[0].split("Z")[0]
    try:
        dt = datetime.strptime(raw[:14], "%Y%m%d%H%M%S")
        return dt.date().isoformat()
    except ValueError:
        return raw


class PDFParser(BaseParser):
    """
    Parses a local PDF file page-by-page using pdfplumber.
    Extracts:
      - Full text (all pages concatenated) into ParsedDocument.content
      - Per-page text into ParsedDocument.pages for page-aware chunking
      - Author and creation date from PDF metadata when present
    access_level and domain are passed in by the caller since they are
    business decisions, not properties of the file itself.
    """

    def parse(
        self,
        file_path: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> ParsedDocument:
        """
        Opens `file_path` with pdfplumber, iterates every page, and collects
        text + page number pairs.  Falls back gracefully when a page has no
        extractable text (scanned pages, images) by recording an empty string
        so the rest of the document is not blocked.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"PDF not found: {file_path}")

        pages_data = []
        full_text_parts = []

        with pdfplumber.open(file_path) as pdf:
            # Pull whatever metadata the PDF exposes
            meta = pdf.metadata or {}
            author = meta.get("Author", "") or ""
            raw_date = meta.get("CreationDate", "") or meta.get("ModDate", "")
            date = _parse_pdf_date(raw_date)
            title = meta.get("Title", "") or os.path.basename(file_path)

            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_data.append({"page": page.page_number, "text": text})
                if text:
                    full_text_parts.append(text)

        full_text = "\n\n".join(full_text_parts)

        return ParsedDocument(
            content=full_text,
            author=author,
            date=date,
            source_system="PDF",
            source_file=file_path,
            access_level=access_level,
            domain=domain,
            title=title,
            pages=pages_data,
        )
