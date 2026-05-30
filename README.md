# AskMe

**An enterprise RAG (Retrieval-Augmented Generation) knowledge assistant for SIX Group.**

AskMe lets employees ask natural-language questions against an internal knowledge
base of ingested documents (PDFs, Confluence pages, Teams meeting transcripts) and
receive **cited, consultant-style answers** — with role-based access control, an
LLM-driven relevance gate, and a full audit trail on every query.

It is provider-agnostic: it runs on the **Google Gemini** API by default, or fully
offline against a local **Ollama** model on your own GPU.

---

## Table of Contents

- [What It Does](#what-it-does)
- [How It Works (End-to-End)](#how-it-works-end-to-end)
- [Architecture](#architecture)
  - [Layer 1 — Ingestion](#layer-1--ingestion)
  - [Layer 2 — Retrieval](#layer-2--retrieval)
  - [Layer 3 — Generation](#layer-3--generation)
  - [Authentication & Roles](#authentication--roles)
  - [Frontend](#frontend)
- [Access Control Model](#access-control-model)
- [Project Layout](#project-layout)
- [Configuration](#configuration)
- [Getting Started](#getting-started)
- [API Reference](#api-reference)
- [Seed Users](#seed-users)

---

## What It Does

- **Ingests** documents from multiple enterprise sources and tags every chunk with
  rich provenance metadata (author, date, source system, business domain, access
  level, page number).
- **Auto-enriches** missing metadata — when a parser can't extract the author,
  date, or domain, an LLM fills the gap.
- **Retrieves** the most relevant passages using a **hybrid search** pipeline
  (semantic + keyword) followed by a cross-encoder re-ranker.
- **Generates** a synthesized, consultant-grade answer with inline `[REF-N]`
  citations, a confidence rating, and a "Key Takeaway" — or honestly says
  *"Nothing in my database would help me to assist in this matter"* when the
  retrieved evidence doesn't fit.
- **Enforces access control** so users only see content their clearance permits,
  and routes regular users to the relevant domain expert when confidential
  material is involved.
- **Audits everything** — every query and every ingestion is logged for admin
  review.

---

## How It Works (End-to-End)

A single question flows through the system like this:

```
                         ┌─────────────────────────────────────────────┐
   User asks a question  │  1. AUTH        Session + role checked        │
   in the browser  ─────▶│  2. RETRIEVE    Hybrid search + re-rank        │
                         │  3. GATE        Relevance assessed             │
                         │  4. GENERATE    LLM writes a cited answer      │
                         │  5. POST-PROCESS Role-aware confidential notice│
                         │  6. AUDIT       Query logged to disk           │
                         └─────────────────────────────────────────────┘
                                          │
                                          ▼
                         Cited answer + confidence + sources + tokens
```

1. **Authentication.** The request hits a `login_required` route. The user's role
   (`user` / `expert` / `admin`) determines what they can do downstream.
2. **Retrieval.** The query is embedded and run through hybrid search: a semantic
   vector search (FAISS) and a keyword search (BM25) each return candidates, which
   are merged by Reciprocal Rank Fusion and re-ranked by a cross-encoder to the
   final top-K passages. Access-level and domain filters are applied here.
3. **Relevance gate.** Before spending an LLM call, the top re-rank score is checked
   against a configurable threshold. The LLM prompt *also* performs its own
   relevance self-assessment as a second line of defense against hallucination.
4. **Generation.** The retrieved chunks, each labeled `[REF-N]` with full
   provenance, are assembled into a "senior consultant" prompt. The LLM returns
   strict JSON: a synthesized answer with inline citations, a confidence level, and
   structured citation objects.
5. **Grounding & post-processing.** Every citation the LLM produces is
   cross-checked against the actual retrieval results, so it cannot invent a source
   that wasn't retrieved. If a regular user's results touch confidential/restricted
   material, the response includes a notice pointing them to the responsible
   domain expert.
6. **Audit.** The full result (answer, citations, confidence, token usage) is
   written to `audit_log.jsonl` and returned to the browser.

---

## Architecture

AskMe is built as a **three-layer pipeline**, each layer cleanly separated so it
can be developed, tested, and swapped independently.

```
ingestion/   →   retrieval/   →   generation/
  Layer 1          Layer 2          Layer 3
 (build the      (find the       (answer with
  knowledge       relevant        cited LLM
  base)           evidence)       synthesis)
```

### Layer 1 — Ingestion

**Path:** `ingestion/` · **Orchestrator:** `IngestionPipeline`

Turns raw source files into fully-tagged, searchable chunks.

```
parser → MetadataEnricher (LLM) → chunker → List[DocumentChunk]
```

- **Parsers** (`ingestion/parsers/`) — one per source type:
  - `PDFParser` — extracts text **page-by-page** (via `pdfplumber`) so page numbers
    are preserved in metadata; reads Author/CreationDate from PDF metadata.
  - `ConfluenceHTMLParser` / `ConfluenceAPIParser` — a single exported HTML page,
    or every page in a live Confluence Cloud space via REST API.
  - `TeamsTranscriptParser` — `.vtt` / `.json` meeting transcripts, parsed into
    **speaker-attributed segments**.
  - All parsers return a common `ParsedDocument`, filling in as much metadata as
    they can and leaving the rest blank for the enricher.
- **`MetadataEnricher`** — calls the LLM **only for fields a parser left empty**
  (author, date, domain), using a 1,500-character sample to keep cost low. Domain
  is classified into a fixed set of known business domains. All LLM calls degrade
  gracefully on failure (e.g. domain falls back to `"Other"`).
- **Chunker** (`ingestion/chunker.py`) — strategy depends on what the parser
  produced:
  - PDF `pages` → page-aware chunking (page number set on every chunk)
  - Teams `segments` → speaker-aware chunking (chunk author = the speaker)
  - otherwise → flat text chunking
  - Default chunk size **512 chars**, overlap **64 chars**.
- **Output:** a flat `List[DocumentChunk]`, where each `DocumentChunk` carries
  `content`, a UUID `chunk_id`, and a `ChunkMetadata` record (author, date,
  source_system, access_level, domain, source_file, chunk_index, title,
  page_number, url).

### Layer 2 — Retrieval

**Path:** `retrieval/` · **Orchestrator:** `RetrievalPipeline`

Hybrid search that combines semantic understanding with exact keyword matching,
then sharpens the result with a cross-encoder.

```
query
  │
  ├─▶ BGE embed ─▶ FAISS vector search ─┐
  │                                     ├─▶ access/domain filter ─▶ RRF ─▶ cross-encoder re-rank ─▶ top-K
  └─▶ BM25 keyword search ──────────────┘
```

- **Embedder** (`embedder.py`) — `BAAI/bge-small-en-v1.5` (384-dim, L2-normalized).
  Queries get a BGE instruction prefix; documents don't — this asymmetry is
  intentional and improves recall.
- **Vector store** (`vector_store.py`) — FAISS `IndexFlatIP` (inner product ==
  cosine on normalized vectors). Persisted to `index/faiss.bin` + `index/chunks.pkl`.
- **BM25 index** (`bm25_index.py`) — classic keyword ranking for exact terms
  (ticker symbols, regulation codes, clause numbers) that semantics can bury.
  Persisted to `index/bm25_corpus.pkl`.
- **Reciprocal Rank Fusion** (`hybrid_search.py`) — merges the two ranked lists
  with `score(d) = Σ weightᵢ / (k + rankᵢ)`, `k = 60`, weighted **0.6 vector /
  0.4 BM25**. Documents ranked highly in *both* lists rise to the top.
- **Re-ranker** (`reranker.py`) — `cross-encoder/ms-marco-MiniLM-L-6-v2` jointly
  encodes each (query, passage) pair for far more accurate relevance than cosine
  alone. Runs only on the top-20 fused candidates to stay fast on CPU.
- **Filters** — access-level (hierarchical) and domain (exact match) are applied
  before fusion.
- All heavy models load **once at construction**; indexes load **once at startup**
  so a previously ingested corpus is instantly searchable.

### Layer 3 — Generation

**Path:** `generation/` · **Orchestrator:** `GenerationPipeline`

Turns retrieved evidence into a grounded, cited answer.

- **Provider abstraction** (`generator.py`) — a `BaseProvider` ABC with two
  backends:
  - `GeminiProvider` — Google Gemini via the `google-genai` SDK; reads exact token
    counts from `usage_metadata`.
  - `OllamaProvider` — a local Ollama server (`/api/chat`); reads token counts from
    the response body. Lets you run **fully offline on your own GPU**.
  - A factory (`_get_provider`) selects the backend from `LLM_PROVIDER`, so callers
    never branch on provider type.
- **Prompt builder** (`prompt_builder.py`) — frames the model as a *senior
  consultant advising SIX Group executives*, with a deliberate two-step structure:
  1. **Relevance gate** — assess whether the chunks genuinely answer the question;
     if not, return the exact *"nothing in my database"* JSON and stop.
  2. **Consultative response** — open with a direct answer, synthesize across
     chunks, cite every claim inline with `[REF-N]`, distinguish stated facts from
     inference, and close with a **Key Takeaway** + a confidence rating
     (HIGH / MEDIUM / LOW).
- **Grounded parsing** — the LLM must return strict JSON. Every citation is
  **cross-checked against the actual retrieval results**, so the model cannot cite
  a source that wasn't retrieved. Markdown code fences are stripped defensively,
  and a parse failure degrades to a safe LOW-confidence fallback.
- **Token accounting** — every call records prompt/completion/total tokens (exact
  when the provider supplies them, estimated otherwise) for display and auditing.
- **Audit logger** (`audit_logger.py`) — writes the full result of every query to
  `audit_log.jsonl`, readable by ID or as a recent feed.

### Authentication & Roles

**Path:** `auth/`

- `UserStore` — a JSON-file-backed store (`data/users.json`) that seeds itself with
  demo users on first run, so the app works out of the box with no database setup.
- Passwords are SHA-256 hashed (**dev only — not production-grade**) and follow a
  `firstname_1234` convention for seeded/created accounts.
- Three roles drive every access decision: `user`, `expert`, `admin`
  (see [Access Control Model](#access-control-model)).

### Frontend

**Path:** `templates/`, `static/`

A single-page app served by Flask:

- `templates/login.html` — login page.
- `templates/index.html` + `static/js/main.js` + `static/css/style.css` — the main
  app, with four role-gated tabs: **Ingest**, **Ask**, **Audit Log**, **Admin**.
- The header shows index status, the active LLM provider badge, and a token-usage
  counter. API routes return `401` with a `redirect` hint so the SPA can bounce to
  `/login` from inside a `fetch()` call.

---

## Access Control Model

Access levels are **hierarchical** — a user cleared at level *N* can see everything
at level *N and below*:

```
public  <  internal  <  confidential  <  restricted
```

Role capabilities:

| Role     | Query | Ingest                          | Admin Panel | Sees confidential content |
|----------|:-----:|---------------------------------|:-----------:|---------------------------|
| `user`   |  ✅   | ❌                              |     ❌      | ❌ — gets a notice + expert contact instead |
| `expert` |  ✅   | ✅ **own domain only**          |     ❌      | ✅ |
| `admin`  |  ✅   | ✅ any domain                   |     ✅      | ✅ |

- **Experts** can ingest documents only for their assigned domain; an upload tagged
  to a different domain is rejected with a message pointing to the right expert.
- When a **regular user's** answer draws on confidential/restricted material, the
  response carries a `confidential_notice` listing the relevant domain experts to
  contact for validation. Experts and admins see no such notice.

---

## Project Layout

```
AskMe/
├── app.py                      # Flask app — all HTTP routes
├── config.py                   # Central configuration & constants
├── requirements.txt
│
├── auth/                       # Authentication & user management
│   ├── models.py               # User dataclass
│   └── store.py                # UserStore (JSON-backed, seeded)
│
├── ingestion/                  # Layer 1 — build the knowledge base
│   ├── pipeline.py             # IngestionPipeline orchestrator
│   ├── metadata_enricher.py    # LLM-based metadata fill-in
│   ├── chunker.py              # Page / speaker / text chunking
│   ├── models.py               # ParsedDocument, DocumentChunk, ChunkMetadata
│   └── parsers/                # PDF, Confluence, Teams parsers
│
├── retrieval/                  # Layer 2 — find relevant evidence
│   ├── pipeline.py             # RetrievalPipeline orchestrator
│   ├── embedder.py             # BGE embeddings
│   ├── vector_store.py         # FAISS vector index
│   ├── bm25_index.py           # BM25 keyword index
│   ├── hybrid_search.py        # Reciprocal Rank Fusion
│   ├── reranker.py             # Cross-encoder re-ranker
│   └── models.py               # RetrievalResult
│
├── generation/                 # Layer 3 — answer with citations
│   ├── pipeline.py             # GenerationPipeline orchestrator
│   ├── generator.py            # Provider abstraction (Gemini / Ollama)
│   ├── prompt_builder.py       # Consultant RAG prompt
│   ├── audit_logger.py         # JSONL audit trail
│   └── models.py               # GenerationResult, Citation, Confidence, TokenUsage
│
├── templates/                  # login.html, index.html
├── static/                     # css/, js/
│
├── data/                       # users.json, ingest_log.jsonl
├── index/                      # Persisted FAISS + BM25 indexes
├── audit_log.jsonl             # Query audit trail
└── samples/                    # Example documents for testing
```

---

## Configuration

All configuration lives in `config.py` and is overridable via a `.env` file
(see `.env.example`).

| Setting               | Default                  | Purpose |
|-----------------------|--------------------------|---------|
| `LLM_PROVIDER`        | `gemini`                 | `gemini` (API) or `ollama` (local GPU) |
| `GEMINI_API_KEY`      | —                        | Required when using Gemini |
| `GEMINI_MODEL`        | *(set in `config.py`)*   | Gemini model name |
| `OLLAMA_BASE_URL`     | `http://localhost:11434` | Local Ollama server |
| `OLLAMA_MODEL`        | `llama3.1:8b`            | Local model to use |
| `CHUNK_SIZE`          | `512`                    | Characters per chunk |
| `CHUNK_OVERLAP`       | `64`                     | Overlap between chunks for context continuity |
| `RELEVANCE_THRESHOLD` | `-20.0`                  | Hard cross-encoder gate; `-20` ≈ disabled (the LLM decides) |
| `ACCESS_LEVELS`       | public → restricted      | The access-control hierarchy |
| `KNOWN_DOMAINS`       | Legal, Finance, HR, …    | Domains the enricher can assign |

> **Running offline:** set `LLM_PROVIDER=ollama` in `.env`, install
> [Ollama](https://ollama.com), and `ollama pull llama3.1:8b` (or another model).
> The entire pipeline then runs on your local GPU — no external API calls.

---

## Getting Started

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
#   then edit .env and set GEMINI_API_KEY (or switch LLM_PROVIDER=ollama)

# 4. Run
python app.py
#   → http://localhost:5000
```

On first launch the app seeds `data/users.json` with demo accounts and loads any
existing index from `index/`. Log in, open the **Ingest** tab (as an expert or
admin) to add documents, then use the **Ask** tab to query them. Sample documents
are provided in `samples/`.

---

## API Reference

All `/api/*` routes require authentication; admin routes additionally require the
`admin` role.

| Method | Endpoint                  | Role          | Description |
|--------|---------------------------|---------------|-------------|
| `POST` | `/api/auth/login`         | public        | Log in, start a session |
| `POST` | `/api/auth/logout`        | any           | Clear the session |
| `GET`  | `/api/auth/me`            | any           | Current user profile |
| `POST` | `/api/ingest`             | expert, admin | Ingest a PDF / Confluence HTML / Teams transcript |
| `POST` | `/api/ask`                | any           | Full RAG: retrieve → gate → generate cited answer |
| `POST` | `/api/search`             | any           | Retrieval only (no LLM) — inspect raw hits |
| `GET`  | `/api/experts`            | any           | List domain experts (for confidential notices) |
| `GET`  | `/api/audit`              | any           | Recent query audit entries |
| `GET`  | `/api/audit/<id>`         | any           | A single audit entry by ID |
| `GET`  | `/api/index/stats`        | any           | Total chunks in the index |
| `GET`  | `/api/config`             | any           | Active LLM provider + model |
| `GET`  | `/api/admin/users`        | admin         | List all users |
| `POST` | `/api/admin/users`        | admin         | Create a user |
| `PUT`  | `/api/admin/users/<id>`   | admin         | Update a user's role / domain |
| `GET`  | `/api/admin/activity`     | admin         | Per-user query + ingest activity summary |

---

## Seed Users

The app ships with four demo accounts (password convention: `firstname_1234`):

| Name           | Email                 | Role     | Domain     | Password         |
|----------------|-----------------------|----------|------------|------------------|
| Mohammed Saeed | mohammed_saeed@six.ch | admin    | —          | `mohammed_1234`  |
| Jacob SIX      | jacob_six@six.ch      | expert   | Legal      | `jacob_1234`     |
| Mirco SIX      | mirco_six@six.ch      | expert   | Marketing  | `mirco_1234`     |
| Steve John     | steve_john@six.ch     | user     | —          | `steve_1234`     |

> ⚠️ **Security note:** SHA-256 password hashing and the default `SECRET_KEY` are
> for demo/hackathon use only. Replace both before any production deployment.

---

*Built as a hackathon project for SIX Group — demonstrating enterprise RAG with
access control, auditability, and role-based knowledge management.*
