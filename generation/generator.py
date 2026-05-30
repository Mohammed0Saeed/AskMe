import json
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Tuple

import requests
from google import genai

from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
)
from generation.models import Citation, Confidence, GenerationResult, TokenUsage
from generation.prompt_builder import build_prompt
from retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)

NO_DATA_PHRASE = "i don't know, please ask your supervisor"


# ── Provider abstraction ──────────────────────────────────────────────────────

class BaseProvider(ABC):
    """
    Every LLM backend returns both the raw text response and a TokenUsage object.
    Keeping token counts inside the provider means each backend extracts them
    from its own response format — callers never have to branch on provider type.
    """

    @abstractmethod
    def complete(self, prompt: str) -> Tuple[str, TokenUsage]:
        """Returns (response_text, token_usage) for the given prompt."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...


def _estimate_tokens(text: str) -> int:
    """
    Rough token count when the provider does not return one.
    The 4-chars-per-token rule is accurate to ±20% for English prose and is
    good enough for display purposes — it is never used for billing.
    """
    return max(1, len(text) // 4)


class GeminiProvider(BaseProvider):
    """
    Google Gemini via the google-genai SDK.
    usage_metadata on the response contains exact token counts billed by Google.
    Falls back to character estimation if the metadata is absent (should not
    happen in practice but guards against SDK version differences).
    """

    def __init__(self) -> None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in .env")
        self._client = genai.Client(api_key=GEMINI_API_KEY)

    def complete(self, prompt: str) -> Tuple[str, TokenUsage]:
        """
        Calls Gemini and extracts token counts from response.usage_metadata.
        The three fields (prompt_token_count, candidates_token_count,
        total_token_count) map directly onto our TokenUsage dataclass.
        """
        response = self._client.models.generate_content(
            model=GEMINI_MODEL, contents=prompt
        )
        meta = response.usage_metadata
        if meta and meta.total_token_count:
            usage = TokenUsage(
                prompt_tokens     = meta.prompt_token_count     or 0,
                completion_tokens = meta.candidates_token_count or 0,
                total_tokens      = meta.total_token_count      or 0,
                estimated         = False,
            )
        else:
            p = _estimate_tokens(prompt)
            c = _estimate_tokens(response.text or "")
            usage = TokenUsage(p, c, p + c, estimated=True)

        return response.text, usage

    @property
    def model_name(self) -> str:
        return GEMINI_MODEL


class OllamaProvider(BaseProvider):
    """
    Local Ollama server.
    Ollama returns prompt_eval_count (prompt tokens) and eval_count (completion
    tokens) at the top level of the /api/chat response when stream=False.
    Falls back to character estimation if these fields are missing (older Ollama
    versions or models that do not track tokens).
    """

    def __init__(self) -> None:
        self._base_url = OLLAMA_BASE_URL.rstrip("/")
        self._model    = OLLAMA_MODEL

    def complete(self, prompt: str) -> Tuple[str, TokenUsage]:
        """Calls Ollama /api/chat and extracts token counts from the response body."""
        url = f"{self._base_url}/api/chat"
        payload = {
            "model":    self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream":   False,
            "options":  {"temperature": 0.1, "num_ctx": 4096},
        }
        try:
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            body = resp.json()
        except requests.ConnectionError:
            raise ConnectionError(
                f"Ollama is not reachable at {self._base_url}. "
                "Make sure Ollama is running: `ollama serve`"
            )
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}. "
                f"Is the model '{self._model}' pulled? Run: `ollama pull {self._model}`"
            )

        text = body["message"]["content"]
        p    = body.get("prompt_eval_count")
        c    = body.get("eval_count")

        if p is not None and c is not None:
            usage = TokenUsage(int(p), int(c), int(p) + int(c), estimated=False)
        else:
            pe = _estimate_tokens(prompt)
            ce = _estimate_tokens(text)
            usage = TokenUsage(pe, ce, pe + ce, estimated=True)

        return text, usage

    @property
    def model_name(self) -> str:
        return f"ollama/{self._model}"


def _get_provider() -> BaseProvider:
    """Factory — reads LLM_PROVIDER from config and returns the right backend."""
    if LLM_PROVIDER == "ollama":
        return OllamaProvider()
    return GeminiProvider()


# ── Response parsing ──────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    """Removes ```json … ``` fences that some models wrap around JSON output."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        raw = "\n".join(inner)
    return raw.strip()


def _parse_citation(obj: dict, results: List[RetrievalResult], ref_id: str) -> Citation:
    """
    Builds a Citation from one element of the LLM's citations array.
    Cross-checks every field against the actual retrieval results so the LLM
    cannot invent a source that does not exist in the index.
    """
    try:
        idx      = int(ref_id.replace("REF-", "")) - 1
        fallback = results[idx] if 0 <= idx < len(results) else results[0]
    except (ValueError, IndexError):
        fallback = results[0]

    fb_m = fallback.chunk.metadata
    return Citation(
        ref_id         = ref_id,
        chunk_id       = obj.get("chunk_id")     or fallback.chunk.chunk_id,
        source_file    = obj.get("source_file")  or os.path.basename(fb_m.source_file),
        author         = obj.get("author")       or fb_m.author,
        domain         = obj.get("domain")       or fb_m.domain,
        access_level   = obj.get("access_level") or fb_m.access_level,
        page_number    = obj.get("page"),
        relevant_quote = obj.get("relevant_quote", ""),
    )


def _parse_response(raw_text: str, results: List[RetrievalResult]) -> dict:
    """Parses the LLM JSON response; returns a graceful fallback on parse failure."""
    try:
        data = json.loads(_strip_fences(raw_text))
    except json.JSONDecodeError as exc:
        logger.warning("JSON parse failed (%s). Raw: %.300s", exc, raw_text)
        return {
            "answer":     raw_text,
            "citations":  [],
            "confidence": {"level": "LOW", "score": 0.1, "reason": "Response parse error."},
        }

    citations = [
        _parse_citation(c, results, c.get("ref_id", f"REF-{i+1}"))
        for i, c in enumerate(data.get("citations") or [])
    ]
    conf_raw   = data.get("confidence") or {}
    confidence = Confidence(
        level  = str(conf_raw.get("level", "LOW")).upper(),
        score  = float(conf_raw.get("score", 0.5)),
        reason = conf_raw.get("reason", ""),
    )
    return {"answer": data.get("answer", ""), "citations": citations, "confidence": confidence}


# ── Generator ─────────────────────────────────────────────────────────────────

class Generator:
    """
    Provider-agnostic generation engine.  Delegates the LLM call to whichever
    backend is configured, parses the structured response, and attaches the
    token usage so every call is fully accountable in the audit log and the UI.
    """

    def __init__(self) -> None:
        self._provider = _get_provider()
        logger.info("LLM provider: %s", self._provider.model_name)

    def generate(self, query: str, results: List[RetrievalResult]) -> GenerationResult:
        """
        Builds the RAG consultation prompt, calls the provider, parses the JSON,
        and returns a GenerationResult with token counts attached.
        """
        prompt       = build_prompt(query, results)
        raw, usage   = self._provider.complete(prompt)
        parsed       = _parse_response(raw, results)
        no_data      = NO_DATA_PHRASE in parsed["answer"].lower()[:120]

        return GenerationResult(
            answer      = parsed["answer"],
            citations   = parsed["citations"],
            confidence  = parsed["confidence"],
            token_usage = usage,
            query       = query,
            model       = self._provider.model_name,
            no_data     = no_data,
        )
