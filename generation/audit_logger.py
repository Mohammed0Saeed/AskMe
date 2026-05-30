import json
import logging
import os
from datetime import datetime, timezone
from typing import List

from generation.models import GenerationResult
from retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = "audit_log.jsonl"


def _load_all() -> List[dict]:
    if not os.path.exists(AUDIT_LOG_PATH):
        return []
    entries = []
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                continue
    return entries


class AuditLogger:
    """
    Appends one JSON line per generation call to audit_log.jsonl.
    JSONL (one JSON object per line) was chosen over a database so the log is:
      - human-readable with any text editor
      - grep-able without tooling (grep "audit_id" audit_log.jsonl)
      - appendable without locks or transactions
      - importable into pandas / Excel for judge review
    Each entry contains the full query, answer, every citation with its quote,
    and all retrieval scores so an auditor can reconstruct the exact reasoning
    chain for any answer.
    """

    def log(
        self,
        result: GenerationResult,
        retrieval_results: List[RetrievalResult],
        conversation_id: str = "",
        user_id: str = "",
        user_name: str = "",
    ) -> dict:
        """
        Writes one audit entry and returns it as a dict.  The return value is
        included in the API response so the UI can display the audit_id and
        let users link back to the log entry.
        """
        entry = {
            "audit_id":        result.audit_id,
            "conversation_id": conversation_id,
            "user_id":         user_id,
            "user_name":       user_name,
            "timestamp":       datetime.now(timezone.utc).isoformat(),
            "model":           result.model,
            "query":           result.query,
            "answer":    result.answer,
            "confidence": {
                "level":  result.confidence.level,
                "score":  result.confidence.score,
                "reason": result.confidence.reason,
            },
            "token_usage": {
                "prompt_tokens":     result.token_usage.prompt_tokens     if result.token_usage else 0,
                "completion_tokens": result.token_usage.completion_tokens if result.token_usage else 0,
                "total_tokens":      result.token_usage.total_tokens      if result.token_usage else 0,
                "estimated":         result.token_usage.estimated         if result.token_usage else True,
            },
            "citations": [
                {
                    "ref_id":         c.ref_id,
                    "chunk_id":       c.chunk_id,
                    "source_file":    c.source_file,
                    "author":         c.author,
                    "domain":         c.domain,
                    "access_level":   c.access_level,
                    "page_number":    c.page_number,
                    "relevant_quote": c.relevant_quote,
                }
                for c in result.citations
            ],
            # Full retrieval trace so judges can see the hybrid-search pipeline
            "retrieval_trace": [
                {
                    "rank":          r.rank,
                    "chunk_id":      r.chunk.chunk_id,
                    "source_file":   os.path.basename(r.chunk.metadata.source_file),
                    "author":        r.chunk.metadata.author,
                    "domain":        r.chunk.metadata.domain,
                    "access_level":  r.chunk.metadata.access_level,
                    "page_number":   r.chunk.metadata.page_number,
                    "rerank_score":  round(r.rerank_score, 4),
                    "vector_score":  round(r.vector_score, 4),
                    "bm25_score":    round(r.bm25_score,   4),
                    "rrf_score":     round(r.rrf_score,    6),
                }
                for r in retrieval_results
            ],
        }

        try:
            with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Audit log write failed: %s", exc)

        return entry


def read_recent(n: int = 20) -> List[dict]:
    """Reads the last n entries from the audit log, most-recent-first."""
    entries = _load_all()
    return list(reversed(entries[-n:]))


def read_by_id(audit_id: str) -> dict | None:
    """Finds and returns a single audit entry by its audit_id."""
    for entry in _load_all():
        if entry.get("audit_id") == audit_id:
            return entry
    return None


def read_conversation(conversation_id: str) -> List[dict]:
    """Returns all audit entries for a conversation_id, oldest-first."""
    return [e for e in _load_all() if e.get("conversation_id") == conversation_id]
