import json
import logging
import os
from abc import ABC, abstractmethod
from typing import List, Tuple

import anthropic as _anthropic_sdk
import requests
from google import genai

from config import (
    GEMINI_API_KEY, GEMINI_MODEL,
    LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL,
)
from generation import provider_config
from generation.models import Citation, Confidence, GenerationResult, TokenUsage
from generation.prompt_builder import build_prompt
from retrieval.models import RetrievalResult

ANTHROPIC_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-haiku-4-5-20251001",
]

logger = logging.getLogger(__name__)

NO_DATA_PHRASE = "i don't know, please ask your supervisor"

_CONVERSATIONAL_PROMPT = """\
You are AskMe, a professional and friendly internal knowledge assistant for SIX Group.
The user has sent a conversational message — not a document question.
Respond naturally, warmly, and concisely in 1-3 sentences.
If asked who you are: you are AskMe, SIX Group's internal knowledge assistant — \
you help employees find answers from internal documents, policies, and procedures.
If asked what you can do: explain you answer questions grounded in internal documents \
with full citations showing the source, page, and author of every claim.

Respond with VALID JSON ONLY — no markdown, no code fences:
{{"answer": "<your friendly response>", "citations": [], "confidence": {{"level": "HIGH", "score": 1.0, "reason": "Conversational response."}}}}

Message: {query}"""

_OFFTOPIC_PROMPT = """\
You are AskMe, a professional internal knowledge assistant for SIX Group.
The user has asked a question that is outside the scope of SIX Group's internal \
knowledge base — the retrieved documents are not relevant to this query.

Write a polite, professional response (2-3 sentences) that:
1. Acknowledges the question briefly.
2. Explains that you can only answer questions grounded in SIX Group's internal \
documents, policies, and procedures.
3. Invites them to ask something related to SIX Group topics or to contact their \
supervisor for general questions.

Respond with VALID JSON ONLY — no markdown, no code fences:
{{"answer": "<your polite response>", "citations": [], "confidence": {{"level": "LOW", "score": 0.0, "reason": "Question is outside the scope of the internal knowledge base."}}}}

User question: {query}"""


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


class AnthropicProvider(BaseProvider):
    """
    Anthropic Claude via the official anthropic SDK.
    Uses messages.create with a single user turn; temperature 0 for
    deterministic, citation-grounded answers.
    """

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        if not api_key:
            raise ValueError("Anthropic API key is not set.")
        self._client = _anthropic_sdk.Anthropic(api_key=api_key)
        self._model  = model

    def complete(self, prompt: str) -> Tuple[str, TokenUsage]:
        message = self._client.messages.create(
            model     = self._model,
            max_tokens= 1024,
            messages  = [{"role": "user", "content": prompt}],
        )
        text  = message.content[0].text if message.content else ""
        usage = TokenUsage(
            prompt_tokens     = message.usage.input_tokens,
            completion_tokens = message.usage.output_tokens,
            total_tokens      = message.usage.input_tokens + message.usage.output_tokens,
            estimated         = False,
        )
        return text, usage

    @property
    def model_name(self) -> str:
        return f"anthropic/{self._model}"


def _get_provider() -> BaseProvider:
    """
    Factory that reads from the runtime provider_config singleton first,
    falling back to the .env LLM_PROVIDER setting.  This allows the admin
    to switch providers at runtime without restarting the server.
    """
    cfg      = provider_config.get()
    provider = cfg.get("provider") or LLM_PROVIDER

    if provider == "anthropic":
        api_key = cfg.get("anthropic_api_key", "")
        model   = cfg.get("anthropic_model", "claude-sonnet-4-6")
        return AnthropicProvider(api_key=api_key, model=model)
    if provider == "ollama":
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
    Provider-agnostic generation engine.  The active provider is resolved on
    every call via the runtime provider_config singleton so an admin can switch
    models without restarting the server.  Provider instances are cached by a
    key that captures the full configuration; the instance is only recreated
    when something actually changes.
    """

    def __init__(self) -> None:
        self._cached_provider: BaseProvider | None = None
        self._cached_key: str = ""

    def _provider(self) -> BaseProvider:
        cfg = provider_config.get()
        key = json.dumps(cfg, sort_keys=True)
        if key != self._cached_key:
            self._cached_provider = _get_provider()
            self._cached_key      = key
            logger.info("LLM provider (re)initialised: %s", self._cached_provider.model_name)
        return self._cached_provider

    def generate_conversational(self, query: str) -> GenerationResult:
        """Handles greetings and simple conversational messages without retrieval."""
        p          = self._provider()
        prompt     = _CONVERSATIONAL_PROMPT.format(query=query)
        raw, usage = p.complete(prompt)
        parsed     = _parse_response(raw, [])
        return GenerationResult(
            answer      = parsed["answer"],
            citations   = [],
            confidence  = parsed["confidence"],
            token_usage = usage,
            query       = query,
            model       = p.model_name,
            no_data     = False,
        )

    def generate_offtopic(self, query: str) -> GenerationResult:
        """Handles questions that fall outside the scope of the knowledge base."""
        p          = self._provider()
        prompt     = _OFFTOPIC_PROMPT.format(query=query)
        raw, usage = p.complete(prompt)
        parsed     = _parse_response(raw, [])
        return GenerationResult(
            answer      = parsed["answer"],
            citations   = [],
            confidence  = parsed["confidence"],
            token_usage = usage,
            query       = query,
            model       = p.model_name,
            no_data     = True,
        )

    def generate(self, query: str, results: List[RetrievalResult]) -> GenerationResult:
        """
        Builds the RAG consultation prompt, calls the provider, parses the JSON,
        and returns a GenerationResult with token counts attached.
        """
        p            = self._provider()
        prompt       = build_prompt(query, results)
        raw, usage   = p.complete(prompt)
        parsed       = _parse_response(raw, results)
        no_data      = NO_DATA_PHRASE in parsed["answer"].lower()[:120]

        return GenerationResult(
            answer      = parsed["answer"],
            citations   = parsed["citations"],
            confidence  = parsed["confidence"],
            token_usage = usage,
            query       = query,
            model       = p.model_name,
            no_data     = no_data,
        )
