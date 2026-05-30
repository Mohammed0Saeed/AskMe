from dataclasses import dataclass, field
from typing import List, Optional
import uuid


@dataclass
class TokenUsage:
    """
    Token counts returned by the LLM provider for one generation call.
    Stored on every GenerationResult so the UI and audit log always have
    the exact cost of each query — critical for monitoring when running
    against paid APIs like Gemini.
    prompt_tokens    : tokens consumed by the RAG prompt (chunks + question)
    completion_tokens: tokens produced in the model's answer
    total_tokens     : sum of both (what the provider bills against)
    estimated        : True when the provider did not return counts and we fell
                       back to a character-based approximation (4 chars ≈ 1 token)
    """
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int
    estimated:         bool = False


@dataclass
class Citation:
    """
    Maps one [REF-N] tag in the answer back to the exact document chunk that
    supports the claim.  Every field needed for a compliance audit trail is
    stored here so judges can trace "claim → quote → file → page → author"
    without opening the original document.
    """
    ref_id:         str            # "REF-1", "REF-2", etc. — matches inline tag
    chunk_id:       str            # 8-char ID linking back to the indexed chunk
    source_file:    str            # Original filename (no temp-path leakage)
    author:         str
    domain:         str
    access_level:   str
    page_number:    Optional[int]
    relevant_quote: str            # The 1-2 sentence excerpt that supports the claim


@dataclass
class Confidence:
    """
    Gemini self-assesses confidence after seeing all the retrieved evidence.
    Using the LLM for this rather than a heuristic score means the assessment
    reflects semantic coverage ("did the chunks actually answer the question?")
    not just retrieval score magnitude.
    """
    level:  str    # "HIGH" | "MEDIUM" | "LOW"
    score:  float  # 0.0 – 1.0 numeric version of level for UI rendering
    reason: str    # One sentence explaining the assessment


@dataclass
class GenerationResult:
    """
    The full output of one generation call.  Kept as a flat dataclass so it
    is trivially serialisable to JSON for the audit log and the API response.
    audit_id is a short UUID assigned at creation time and written to the log
    so a specific answer can be retrieved for a compliance review.
    no_data is True when the LLM determined the retrieved documents do not
    contain information relevant to the question — the UI renders this as a
    clear "not found" message rather than a fabricated answer.
    """
    answer:      str
    citations:   List[Citation]
    confidence:  Confidence
    token_usage: Optional[TokenUsage] = None
    query:       str  = ""
    model:       str  = ""
    no_data:     bool = False
    audit_id:    str  = field(default_factory=lambda: str(uuid.uuid4()).replace("-", "")[:12])
