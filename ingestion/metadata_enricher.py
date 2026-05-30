import json
import logging

from google import genai

from config import GEMINI_API_KEY, GEMINI_MODEL, KNOWN_DOMAINS

logger = logging.getLogger(__name__)


def _build_gemini_client() -> genai.Client:
    """
    Creates a google-genai Client using the API key from config.
    Called once per MetadataEnricher instance so the key is validated at
    startup rather than silently failing on the first Gemini call.
    """
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set. Add it to your .env file or environment."
        )
    return genai.Client(api_key=GEMINI_API_KEY)


def _strip_code_fence(raw: str) -> str:
    """
    Removes markdown code fences (```json ... ```) that Gemini sometimes wraps
    around JSON responses.  Returns the inner content so json.loads() works
    without needing to handle the fence in every caller.
    """
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


class MetadataEnricher:
    """
    Uses Gemini to fill in metadata fields that the parsers could not extract
    from the source document.  Currently handles:
      - domain  : detected from chunk/document content
      - author  : extracted when embedded in free text but not in file metadata
    All Gemini calls are wrapped in try/except so a network or quota failure
    degrades gracefully rather than crashing the whole ingestion run.
    """

    def __init__(self) -> None:
        self._client = _build_gemini_client()

    def detect_domain(self, text: str) -> str:
        """
        Asks Gemini to classify the text into one of the known business domains
        (Legal, Customer Service, HR, Finance, Technology, Operations, Marketing,
        Other).  Returns the domain string or "Other" on any failure.
        The prompt deliberately constrains the answer to a JSON object so the
        response is machine-readable without brittle string parsing.
        """
        domains_list = ", ".join(KNOWN_DOMAINS)
        prompt = (
            f"Classify the following text into exactly one business domain.\n"
            f"Choose only from: {domains_list}.\n\n"
            f"Text:\n{text[:1500]}\n\n"
            f'Respond with valid JSON only: {{"domain": "<domain>"}}'
        )
        try:
            response = self._client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            raw = _strip_code_fence(response.text.strip())
            data = json.loads(raw)
            return data.get("domain", "Other")
        except Exception as exc:
            logger.warning("domain detection failed: %s", exc)
            return "Other"

    def extract_author_and_date(self, text: str) -> dict:
        """
        Asks Gemini to extract author name and date from the body of a document
        when the parser could not find them in file-level metadata.
        Returns a dict with "author" and "date" keys; values are empty strings
        when nothing could be found so callers can check truthiness.
        """
        prompt = (
            "Extract the author name and date from the text below.\n"
            "If you cannot find one or both, return an empty string for that field.\n\n"
            f"Text:\n{text[:1500]}\n\n"
            'Respond with valid JSON only: {"author": "<name or empty>", "date": "<ISO-8601 or empty>"}'
        )
        try:
            response = self._client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt
            )
            raw = _strip_code_fence(response.text.strip())
            data = json.loads(raw)
            return {
                "author": data.get("author", ""),
                "date": data.get("date", ""),
            }
        except Exception as exc:
            logger.warning("author/date extraction failed: %s", exc)
            return {"author": "", "date": ""}

    def enrich(self, text: str, author: str, date: str, domain: str) -> dict:
        """
        Single entry point for the pipeline.  Only calls Gemini for fields that
        are genuinely missing ("" or the sentinel "auto") so we never burn quota
        re-detecting metadata that the parser already found.
        Returns a dict with the final "author", "date", and "domain" values.
        """
        needs_author = not author
        needs_date = not date
        needs_domain = not domain or domain.lower() == "auto"

        result = {"author": author, "date": date, "domain": domain}

        # Batch author+date into one call if both are missing
        if needs_author or needs_date:
            extracted = self.extract_author_and_date(text)
            if needs_author:
                result["author"] = extracted["author"] or "Unknown"
            if needs_date:
                result["date"] = extracted["date"] or "Unknown"

        if needs_domain:
            result["domain"] = self.detect_domain(text)

        return result
