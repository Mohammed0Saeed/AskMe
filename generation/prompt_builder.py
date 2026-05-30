import os
from typing import List

from retrieval.models import RetrievalResult

# ── Consultation prompt ───────────────────────────────────────────────────────
# The framing shift from "document analyst" to "senior consultant" is
# intentional: it pushes the model to synthesise and interpret evidence rather
# than merely paraphrasing quotes back.  The explicit RELEVANCE ASSESSMENT block
# forces the model to decide upfront whether the retrieved chunks are useful —
# this is what produces the "nothing in my database" response for off-topic
# queries instead of a hallucinated or hedged non-answer.

_SYSTEM_CONTEXT = """\
You are a senior consultant and domain expert advising executives at SIX Group.
Your role is to THINK, ANALYSE, and ADVISE — not to summarise documents.
You have been given a set of document chunks retrieved from an internal knowledge base.
You must base your entire response on those chunks and nothing else."""

_RELEVANCE_GATE = """\
━━━  STEP 1 — ASSESS RELEVANCE BEFORE WRITING ANYTHING  ━━━
Read every chunk carefully. Ask yourself:
  "Do these chunks DIRECTLY and EXPLICITLY answer the question being asked?"

Output ONLY the no-data JSON below and stop if ANY of the following are true:
  • The chunks do not mention the subject of the question at all.
  • The chunks are loosely related but do not contain a direct answer.
  • Answering would require you to infer, guess, or construct an answer \
from hints — rather than stating what the chunks explicitly say.
  • The question asks for a definition, rule, or fact that is not stated \
word-for-word (or near word-for-word) in the chunks.

{
  "answer": "I don't know, please ask your supervisor.",
  "citations": [],
  "confidence": {"level": "LOW", "score": 0.0, "reason": "The retrieved documents do not contain a direct answer to this question."}
}"""

_CONSULTATION_RULES = """\
━━━  STEP 2 — WRITE A CONSULTATIVE RESPONSE (only if chunks DIRECTLY answer the question)  ━━━
1. Open with a direct answer to the question — do not hedge or re-state the question.
2. Every sentence must be traceable to an explicit statement in the chunks.
   Do NOT infer, speculate, or construct answers from loosely related content.
3. Cite every factual claim inline with [REF-N] immediately after the claim.
   If multiple chunks support the same claim, use [REF-1][REF-3] etc.
4. If any part of the question is not explicitly covered by the chunks, omit that
   part entirely — do not fill the gap with inference or general knowledge.
5. Close with a "Key Takeaway" section: one or two sentences drawn only from
   what the chunks explicitly state.
6. Assess confidence:
     HIGH   — every claim is directly and explicitly supported; no gaps.
     MEDIUM — most claims directly supported; minor gaps acknowledged.
     LOW    — only partial direct evidence; significant gaps remain.
7. Respond with VALID JSON ONLY — no markdown, no code fences, no extra text."""

_JSON_SCHEMA = """\
{
  "answer": "<consultative response with [REF-N] inline citations; end with Key Takeaway>",
  "citations": [
    {
      "ref_id":         "REF-1",
      "chunk_id":       "<chunk_id from the chunk header>",
      "source_file":    "<filename>",
      "author":         "<author>",
      "page":           <integer or null>,
      "domain":         "<domain>",
      "access_level":   "<access_level>",
      "relevant_quote": "<1-2 sentence excerpt that directly supports the claim>"
    }
  ],
  "confidence": {
    "level":  "HIGH",
    "score":  0.85,
    "reason": "<one sentence explaining the confidence assessment>"
  }
}"""


def build_prompt(query: str, results: List[RetrievalResult]) -> str:
    """
    Assembles the full consultation prompt.
    Each chunk is labelled [REF-N] with its full provenance header so the model
    can populate citations accurately.  The rerank_score is included in the
    header as a relevance signal — the model can use it to weight how much
    confidence to place in each chunk.
    """
    chunk_blocks = []
    for i, r in enumerate(results, start=1):
        m        = r.chunk.metadata
        page_str = f" | Page: {m.page_number}" if m.page_number is not None else ""
        header   = (
            f"[REF-{i}]  chunk_id: {r.chunk.chunk_id}"
            f" | Source: {os.path.basename(m.source_file)}{page_str}"
            f" | Author: {m.author or 'Unknown'}"
            f" | Domain: {m.domain}"
            f" | Access: {m.access_level}"
            f" | Relevance score: {r.rerank_score:.2f}"
        )
        chunk_blocks.append(f"{header}\n\"\"\"\n{r.chunk.content}\n\"\"\"")

    chunks_section = "\n\n".join(chunk_blocks)

    return (
        f"{_SYSTEM_CONTEXT}\n\n"
        f"{_RELEVANCE_GATE}\n\n"
        f"RETRIEVED DOCUMENT CHUNKS:\n{chunks_section}\n\n"
        f"QUESTION: {query}\n\n"
        f"{_CONSULTATION_RULES}\n\n"
        f"Respond with this exact JSON structure:\n{_JSON_SCHEMA}"
    )
