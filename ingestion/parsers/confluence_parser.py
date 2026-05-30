import os
import logging
from typing import Optional, List

import requests
from bs4 import BeautifulSoup

from ingestion.models import ParsedDocument
from ingestion.parsers.base_parser import BaseParser

logger = logging.getLogger(__name__)


def _html_to_text(html: str) -> str:
    """
    Strips all HTML tags from a Confluence page body and returns clean plain
    text.  Preserves newlines at block-level elements (p, h1-h6, li, br) so
    the resulting text retains paragraph structure for the chunker.
    """
    soup = BeautifulSoup(html, "html.parser")
    # Insert newlines at block boundaries before stripping tags
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "br"]):
        tag.insert_after("\n")
    return soup.get_text(separator=" ").strip()


class ConfluenceAPIParser(BaseParser):
    """
    Fetches pages from a Confluence Cloud space via the REST API (v2).
    Requires:
      - base_url : e.g. "https://yourcompany.atlassian.net"
      - username : Atlassian account email
      - api_token: Atlassian API token (not your password)
    Retrieves every page in the given space, strips HTML, and packages each
    page as a ParsedDocument.  Returns a list; the pipeline calls parse() once
    per space and fans out from there.
    """

    def __init__(self, base_url: str, username: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = (username, api_token)

    def _get_pages_in_space(self, space_key: str) -> List[dict]:
        """
        Paginates through the Confluence REST API to collect all page IDs,
        titles, and author information for the given space.  Uses a limit of
        50 per request and follows the `_links.next` cursor until exhausted.
        """
        pages = []
        url = f"{self._base_url}/wiki/rest/api/content"
        params = {
            "spaceKey": space_key,
            "type": "page",
            "expand": "history.lastUpdated,history.createdBy,version",
            "limit": 50,
            "start": 0,
        }

        while True:
            resp = requests.get(url, params=params, auth=self._auth, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            pages.extend(data.get("results", []))

            # Confluence signals no more pages by omitting "next" in _links
            if "next" not in data.get("_links", {}):
                break
            params["start"] += params["limit"]

        return pages

    def _get_page_body(self, page_id: str) -> str:
        """
        Fetches the storage-format HTML body for a single Confluence page by ID.
        Returns an empty string if the request fails so a single bad page does
        not abort the entire space ingestion.
        """
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
        params = {"expand": "body.storage"}
        try:
            resp = requests.get(url, params=params, auth=self._auth, timeout=30)
            resp.raise_for_status()
            return resp.json()["body"]["storage"]["value"]
        except Exception as exc:
            logger.warning("Failed to fetch page %s: %s", page_id, exc)
            return ""

    def parse(
        self,
        space_key: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> List[ParsedDocument]:
        """
        Ingests an entire Confluence space.  Each page becomes one ParsedDocument.
        Author and date are read from the page history; the HTML body is converted
        to plain text.  Returns a list so the pipeline can chunk each document
        independently.
        """
        pages_meta = self._get_pages_in_space(space_key)
        documents = []

        for page in pages_meta:
            page_id = page["id"]
            title = page.get("title", "")
            author = (
                page.get("history", {})
                    .get("createdBy", {})
                    .get("displayName", "")
            )
            date = (
                page.get("history", {})
                    .get("lastUpdated", {})
                    .get("when", "")[:10]  # Keep only YYYY-MM-DD
            )
            url = f"{self._base_url}/wiki{page.get('_links', {}).get('webui', '')}"

            html_body = self._get_page_body(page_id)
            text = _html_to_text(html_body)

            if not text.strip():
                continue

            documents.append(ParsedDocument(
                content=text,
                author=author,
                date=date,
                source_system="Confluence",
                source_file=url,
                access_level=access_level,
                domain=domain,
                title=title,
                url=url,
            ))

        return documents


class ConfluenceHTMLParser(BaseParser):
    """
    Parses a Confluence HTML export (a single .html file exported from a space).
    Useful when live API access is not available or for offline/archival ingestion.
    Author and date are extracted from the meta tags that Confluence embeds
    in its HTML exports.
    """

    def parse(
        self,
        file_path: str,
        access_level: str = "internal",
        domain: str = "",
    ) -> ParsedDocument:
        """
        Reads an HTML file from disk, extracts the page title from <title>,
        author from <meta name="author">, and date from <meta name="date">.
        The full visible text is extracted by stripping all HTML tags.
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"HTML file not found: {file_path}")

        with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()

        soup = BeautifulSoup(html, "html.parser")

        title = soup.title.string.strip() if soup.title else os.path.basename(file_path)

        # Confluence HTML exports include these meta tags when available
        author_tag = soup.find("meta", attrs={"name": "author"})
        author = author_tag["content"] if author_tag else ""

        date_tag = soup.find("meta", attrs={"name": "date"})
        date = date_tag["content"][:10] if date_tag else ""

        text = _html_to_text(str(soup.body) if soup.body else html)

        return ParsedDocument(
            content=text,
            author=author,
            date=date,
            source_system="Confluence",
            source_file=file_path,
            access_level=access_level,
            domain=domain,
            title=title,
        )
