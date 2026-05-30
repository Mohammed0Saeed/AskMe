import logging
from typing import List

from generation.audit_logger import AuditLogger
from generation.generator import Generator
from generation.models import GenerationResult
from retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


class GenerationPipeline:
    """
    Top-level orchestrator for Layer 3.  Wires together:
      Generator (Gemini RAG call) → AuditLogger (JSONL persistence)
    Kept separate from the Generator so the logging concern does not
    pollute the generation logic and can be swapped out independently.
    """

    def __init__(self) -> None:
        self._generator = Generator()
        self._logger    = AuditLogger()

    def generate_conversational(
        self, query: str,
        conversation_id: str = "", user_id: str = "", user_name: str = "",
    ) -> GenerationResult:
        result = self._generator.generate_conversational(query)
        self._logger.log(result, [], conversation_id=conversation_id,
                         user_id=user_id, user_name=user_name)
        return result

    def generate_offtopic(
        self, query: str,
        conversation_id: str = "", user_id: str = "", user_name: str = "",
    ) -> GenerationResult:
        result = self._generator.generate_offtopic(query)
        self._logger.log(result, [], conversation_id=conversation_id,
                         user_id=user_id, user_name=user_name)
        return result

    def generate(
        self,
        query: str,
        retrieval_results: List[RetrievalResult],
        conversation_id: str = "", user_id: str = "", user_name: str = "",
    ) -> GenerationResult:
        """
        Generates a cited answer from the provided retrieval results and writes
        the full audit entry to disk.  Returns the GenerationResult so the
        caller (Flask route) can serialise it for the API response.
        The audit entry is written after generation so a failed Gemini call does
        not produce a blank log entry that would confuse auditors.
        """
        result = self._generator.generate(query, retrieval_results)
        self._logger.log(result, retrieval_results, conversation_id=conversation_id,
                         user_id=user_id, user_name=user_name)
        logger.info(
            "Generated answer [audit=%s] confidence=%s citations=%d",
            result.audit_id,
            result.confidence.level,
            len(result.citations),
        )
        return result
