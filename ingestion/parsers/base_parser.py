from abc import ABC, abstractmethod
from ingestion.models import ParsedDocument


class BaseParser(ABC):
    """
    Every source-specific parser inherits from this class.
    The contract is simple: accept whatever the source needs as constructor
    arguments, then expose a single `parse()` method that returns a
    ParsedDocument so the pipeline treats all sources identically.
    """

    @abstractmethod
    def parse(self, *args, **kwargs) -> ParsedDocument:
        """
        Extract text and as many metadata fields as possible from the source.
        Fields the parser cannot determine (e.g. domain when not tagged) should
        be left as "" so MetadataEnricher can fill them in via Gemini.
        """
        ...
