import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from functools import wraps

from flask import Flask, jsonify, request, session

from collections import Counter

from auth import UserStore
from config import GEMINI_MODEL, LLM_PROVIDER, OLLAMA_MODEL, RELEVANCE_THRESHOLD, SECRET_KEY
from generation import GenerationPipeline
from generation import provider_config as _provider_config
from generation.audit_logger import read_by_id, read_conversation, read_recent
from generation.generator import ANTHROPIC_MODELS
from generation.insight_engine import InsightEngine
from generation.ticket_store import TicketStore
from generation.training_store import TrainingStore
from generation.user_progress import UserProgressStore
from ingestion import IngestionPipeline
from retrieval import RetrievalPipeline

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.secret_key = SECRET_KEY


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"]  = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    return response

@app.route("/api/<path:path>", methods=["OPTIONS"])
def options_handler(path):
    return "", 204


# ── Singletons ───────────────────────────────────────────────────────────────
user_store          = UserStore()
ingest_pipeline     = IngestionPipeline()
retrieval_pipeline  = RetrievalPipeline()
_provider_config.load()          # restore admin-chosen provider before pipeline init
generation_pipeline = GenerationPipeline()
ticket_store        = TicketStore()
training_store      = TrainingStore()
progress_store      = UserProgressStore()
insight_engine      = InsightEngine()
retrieval_pipeline.load_index()

ALLOWED_EXTENSIONS = {".pdf", ".vtt", ".json", ".html", ".htm"}

# ── Conversational query detection ─────────────────────────────────────────────
_CONV_PHRASES = {
    "how are you", "how r u", "how are u", "hows it going", "how's it going",
    "whats up", "what's up", "what is up",
    "good morning", "good afternoon", "good evening", "good night",
    "nice to meet you", "pleased to meet you", "great to meet you",
    "who are you", "what are you", "what can you do", "what do you do",
    "thanks", "thank you", "thank u", "thx", "ty", "cheers", "many thanks",
    "appreciated", "much appreciated", "thanks a lot", "thank you so much",
    "thanks so much", "thanks very much", "thank you very much",
    "bye", "goodbye", "ciao", "see you", "see ya", "farewell", "take care",
    "good bye", "have a good day", "have a nice day", "talk later", "talk soon",
    "ok", "okay", "got it", "sounds good", "great", "awesome", "cool",
    "noted", "understood", "perfect", "wonderful", "excellent",
    "hi", "hello", "hey", "howdy", "hiya", "yo", "greetings", "sup",
}

# Single words that — when a message is short — flag it as conversational
_CONV_WORDS = {
    "hi", "hello", "hey", "howdy", "hiya", "yo", "greetings", "sup",
    "thanks", "thank", "thx", "ty", "cheers", "appreciated",
    "bye", "goodbye", "ciao", "farewell",
    "ok", "okay", "great", "awesome", "cool", "noted", "perfect",
    "wonderful", "excellent", "understood", "alright", "sure",
}

def _is_conversational(query: str) -> bool:
    q     = query.strip().lower().rstrip("!?.")
    words = q.split()
    if not words:
        return False
    # Exact phrase match
    if q in _CONV_PHRASES:
        return True
    # Short message (≤ 6 words) whose first meaningful word is conversational
    first = words[0].strip(",.!?;:")
    return first in _CONV_WORDS and len(words) <= 6
INGEST_LOG_PATH    = "data/ingest_log.jsonl"

# Roles that are allowed to ingest documents
INGEST_ROLES = {"expert", "admin"}

# Access levels that trigger the confidential notice for regular users
RESTRICTED_LEVELS = {"confidential", "restricted"}


# ── Auth helpers ──────────────────────────────────────────────────────────────

def get_current_user():
    """Returns the logged-in User object, or None if the session is empty."""
    uid = session.get("user_id")
    return user_store.find_by_id(uid) if uid else None


def login_required(f):
    """
    Decorator that enforces authentication on every route it wraps.
    API routes get a 401 JSON response so the frontend can redirect to /login
    without the browser following a server-side redirect inside a fetch() call.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required", "redirect": "/login"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Restricts a route to admin users only."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.role != "admin":
            return jsonify({"error": "Admin access required."}), 403
        return f(*args, **kwargs)
    return decorated


# ── Serialisers ───────────────────────────────────────────────────────────────

def _chunk_to_dict(chunk) -> dict:
    """Converts a DocumentChunk to a JSON-safe dict, stripping internal temp paths."""
    return {
        "chunk_id": chunk.chunk_id[:8],
        "content":  chunk.content,
        "metadata": {
            "author":        chunk.metadata.author,
            "date":          chunk.metadata.date,
            "source_system": chunk.metadata.source_system,
            "access_level":  chunk.metadata.access_level,
            "domain":        chunk.metadata.domain,
            "source_file":   os.path.basename(chunk.metadata.source_file),
            "chunk_index":   chunk.metadata.chunk_index,
            "title":         chunk.metadata.title or "",
            "page_number":   chunk.metadata.page_number,
            "url":           chunk.metadata.url or "",
        },
    }


def _result_to_dict(result) -> dict:
    return {
        "rank":         result.rank,
        "rerank_score": round(result.rerank_score, 4),
        "vector_score": round(result.vector_score, 4),
        "bm25_score":   round(result.bm25_score,   4),
        "rrf_score":    round(result.rrf_score,     6),
        "chunk":        _chunk_to_dict(result.chunk),
    }


def _citation_to_dict(c) -> dict:
    return {
        "ref_id":         c.ref_id,
        "chunk_id":       c.chunk_id,
        "source_file":    c.source_file,
        "author":         c.author,
        "domain":         c.domain,
        "access_level":   c.access_level,
        "page_number":    c.page_number,
        "relevant_quote": c.relevant_quote,
    }


def _build_confidential_notice(results, user) -> dict | None:
    """
    Checks whether any retrieved chunk is confidential or restricted and,
    if the requesting user is a regular user, returns a notice object with
    expert contact information so they know who to approach for validation.
    Experts and admins see confidential content without a notice.
    """
    if user.role != "user":
        return None

    restricted_domains = {
        r.chunk.metadata.domain
        for r in results
        if r.chunk.metadata.access_level in RESTRICTED_LEVELS
    }
    if not restricted_domains:
        return None

    contacts = []
    for domain in restricted_domains:
        expert = user_store.find_expert_for_domain(domain)
        if expert:
            contacts.append({
                "domain": domain,
                "name":   expert.name,
                "email":  expert.email,
            })

    return {
        "has_restricted": True,
        "domains":        list(restricted_domains),
        "contacts":       contacts,
    }


def _infer_domain(gen, results, domain_filter: str | None) -> str:
    """
    Determines the most likely domain for a ticket.
    Priority: explicit domain_filter > most common citation domain > top chunk domain.
    """
    if domain_filter:
        return domain_filter
    if gen.citations:
        domains = [c.domain for c in gen.citations if c.domain]
        if domains:
            return Counter(domains).most_common(1)[0][0]
    if results:
        return results[0].chunk.metadata.domain or "Unknown"
    return "Unknown"


def _write_ingest_log(user, filename: str, chunks: int, domain: str) -> None:
    """
    Appends one line to the ingest activity log so admins can see who uploaded
    what and when — mirroring the query audit trail for document ingestion.
    """
    os.makedirs("data", exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id":   user.user_id,
        "user_name": user.name,
        "role":      user.role,
        "filename":  filename,
        "chunks":    chunks,
        "domain":    domain,
    }
    with open(INGEST_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/login")
def login_page():
    return jsonify({"error": "Use the React frontend at http://localhost:5173"}), 404


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    """
    Validates credentials and starts a session.
    Returns the user's public profile so the frontend can populate
    the header and enforce role-based UI rules immediately on login.
    """
    body     = request.get_json(force=True) or {}
    email    = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    user = user_store.find_by_email(email)
    if not user or not user_store.verify_password(password, user.password_hash):
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"] = user.user_id
    session.permanent = True
    return jsonify(user.to_public_dict())


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    """Returns the current user's profile. 401 if not logged in."""
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated", "redirect": "/login"}), 401
    return jsonify(user.to_public_dict())


# ── Main page ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return jsonify({"service": "AskMe API", "frontend": "http://localhost:5173"})


# ── Ingest ────────────────────────────────────────────────────────────────────

@app.route("/api/ingest", methods=["POST"])
@login_required
def ingest():
    """
    Ingests a document into the knowledge base.
    Access rules:
      - Regular users cannot ingest (return 403).
      - Experts can only ingest documents for their own domain; uploading a
        document tagged to a different domain is blocked with a clear message.
      - Admins can ingest for any domain.
    """
    user = get_current_user()

    if user.role not in INGEST_ROLES:
        return jsonify({
            "error": "Uploading documents is restricted to experts and admins. "
                     "Please contact the relevant expert to add content.",
            "role_restricted": True,
        }), 403

    source_type  = request.form.get("source_type", "pdf")
    access_level = request.form.get("access_level", "internal")
    domain       = request.form.get("domain", "").strip()
    ticket_id    = request.form.get("ticket_id", "").strip()

    # Expert domain enforcement
    if user.role == "expert":
        if not domain:
            domain = user.domain  # auto-assign expert's domain when left blank
        elif domain != user.domain:
            return jsonify({
                "error": (
                    f"You are authorised to upload documents for the "
                    f"'{user.domain}' domain only. "
                    f"This document is labelled '{domain}'. "
                    f"Please contact the {domain} expert to handle this upload."
                ),
                "domain_mismatch": True,
                "your_domain":     user.domain,
                "attempted_domain": domain,
            }), 403

    if "file" not in request.files or not request.files["file"].filename:
        return jsonify({"error": "No file uploaded."}), 400

    file = request.files["file"]
    ext  = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"File type '{ext}' is not supported."}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        file.save(tmp_path)

    try:
        if source_type == "pdf":
            chunks = ingest_pipeline.ingest_pdf(tmp_path, access_level=access_level, domain=domain)
        elif source_type == "confluence_html":
            chunks = ingest_pipeline.ingest_confluence_html(tmp_path, access_level=access_level, domain=domain)
        elif source_type == "teams":
            chunks = ingest_pipeline.ingest_teams_transcript(
                tmp_path,
                meeting_organiser=request.form.get("meeting_organiser", ""),
                meeting_date=request.form.get("meeting_date", ""),
                meeting_title=request.form.get("meeting_title", ""),
                access_level=access_level,
                domain=domain,
            )
        else:
            return jsonify({"error": f"Unknown source type: {source_type}"}), 400

        added = retrieval_pipeline.index(chunks)
        _write_ingest_log(user, file.filename, added, domain)

        if ticket_id:
            ticket_store.update_status(ticket_id, "resolved")

        return jsonify({
            "success":       True,
            "total_chunks":  len(chunks),
            "newly_indexed": added,
            "index_size":    retrieval_pipeline.total_chunks,
            "chunks":        [_chunk_to_dict(c) for c in chunks],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    finally:
        os.unlink(tmp_path)


# ── Ask ───────────────────────────────────────────────────────────────────────

@app.route("/api/ask", methods=["POST"])
@login_required
def ask():
    """
    Full RAG pipeline with role-aware post-processing:
      - Regular users receive a confidential_notice when any retrieved chunk
        is tagged confidential/restricted, directing them to the expert.
      - Experts and admins see no notice.
    """
    user            = get_current_user()
    body            = request.get_json(force=True) or {}
    query           = (body.get("query") or "").strip()
    top_k           = int(body.get("top_k", 5))
    access_level    = body.get("access_level") or None
    domain          = (body.get("domain_filter") or "").strip() or None
    conversation_id = (body.get("conversation_id") or "").strip()

    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400

    if _is_conversational(query):
        try:
            gen = generation_pipeline.generate_conversational(
                query, conversation_id=conversation_id,
                user_id=user.user_id, user_name=user.name)
            tu  = gen.token_usage
            return jsonify({
                "query":    query,
                "no_data":  False,
                "answer":   gen.answer,
                "citations": [],
                "confidence": {"level": "HIGH", "score": 1.0, "reason": "Conversational response."},
                "token_usage": {
                    "prompt_tokens":     tu.prompt_tokens     if tu else 0,
                    "completion_tokens": tu.completion_tokens if tu else 0,
                    "total_tokens":      tu.total_tokens      if tu else 0,
                    "estimated":         tu.estimated         if tu else True,
                },
                "confidential_notice": None,
                "audit_id": gen.audit_id,
                "model":    gen.model,
                "results":  [],
            })
        except Exception as exc:
            return jsonify({"error": str(exc)}), 500

    if retrieval_pipeline.total_chunks == 0:
        return jsonify({"error": "Index is empty. Please contact an admin or expert."}), 400

    provider_label = f"ollama / {OLLAMA_MODEL}" if LLM_PROVIDER == "ollama" else "Gemini"

    try:
        results = retrieval_pipeline.search(query, top_k=top_k,
                                            user_access_level=access_level,
                                            domain_filter=domain)
        if not results:
            return jsonify({"error": "No relevant documents found."}), 404

        if results[0].rerank_score < RELEVANCE_THRESHOLD:
            gen = generation_pipeline.generate_offtopic(
                query, conversation_id=conversation_id,
                user_id=user.user_id, user_name=user.name)
            tu  = gen.token_usage
            return jsonify({
                "query":    query,
                "no_data":  True,
                "answer":   gen.answer,
                "citations": [],
                "confidence": {
                    "level":  gen.confidence.level,
                    "score":  gen.confidence.score,
                    "reason": gen.confidence.reason,
                },
                "token_usage": {
                    "prompt_tokens":     tu.prompt_tokens     if tu else 0,
                    "completion_tokens": tu.completion_tokens if tu else 0,
                    "total_tokens":      tu.total_tokens      if tu else 0,
                    "estimated":         tu.estimated         if tu else True,
                },
                "confidential_notice": None,
                "audit_id": gen.audit_id,
                "model":    gen.model,
                "results":  [_result_to_dict(r) for r in results],
            })

        gen = generation_pipeline.generate(
            query, results,
            conversation_id=conversation_id,
            user_id=user.user_id, user_name=user.name)
        tu  = gen.token_usage

        # Auto-create a ticket when confidence is LOW so experts can review gaps
        if gen.confidence.level == "LOW":
            ticket_store.create(
                query             = query,
                answer            = gen.answer,
                confidence_level  = gen.confidence.level,
                confidence_reason = gen.confidence.reason,
                domain            = _infer_domain(gen, results, domain),
                no_data           = gen.no_data,
                user_id           = user.user_id,
                user_name         = user.name,
                audit_id          = gen.audit_id,
            )

        return jsonify({
            "query":     query,
            "no_data":   gen.no_data,
            "answer":    gen.answer,
            "citations": [_citation_to_dict(c) for c in gen.citations],
            "confidence": {
                "level":  gen.confidence.level,
                "score":  gen.confidence.score,
                "reason": gen.confidence.reason,
            },
            "token_usage": {
                "prompt_tokens":     tu.prompt_tokens     if tu else 0,
                "completion_tokens": tu.completion_tokens if tu else 0,
                "total_tokens":      tu.total_tokens      if tu else 0,
                "estimated":         tu.estimated         if tu else True,
            },
            "confidential_notice": _build_confidential_notice(results, user),
            "audit_id":  gen.audit_id,
            "model":     gen.model,
            "results":   [_result_to_dict(r) for r in results],
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Experts directory (public) ────────────────────────────────────────────────

@app.route("/api/experts", methods=["GET"])
@login_required
def get_experts():
    """Returns the list of experts so the frontend can build confidential notices."""
    return jsonify([e.to_public_dict() for e in user_store.get_experts()])


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route("/api/admin/users", methods=["GET"])
@admin_required
def admin_list_users():
    """Returns all users for the admin management panel."""
    return jsonify([u.to_public_dict() for u in user_store.get_all()])


@app.route("/api/admin/users/<user_id>", methods=["PUT"])
@admin_required
def admin_update_user(user_id: str):
    """
    Admin-only: updates a user's role and domain.
    Clearing domain automatically when role is not 'expert' prevents stale
    domain data from bypassing access-control checks.
    """
    body   = request.get_json(force=True) or {}
    role   = body.get("role", "user")
    domain = body.get("domain", "")
    updated = user_store.update_user(user_id, role, domain)
    if not updated:
        return jsonify({"error": "User not found."}), 404
    return jsonify(updated.to_public_dict())


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    """Admin-only: creates a new user with the firstname_1234 password convention."""
    body   = request.get_json(force=True) or {}
    name   = (body.get("name") or "").strip()
    email  = (body.get("email") or "").strip()
    role   = body.get("role", "user")
    domain = body.get("domain", "")
    if not name or not email:
        return jsonify({"error": "Name and email are required."}), 400
    user = user_store.create_user(name, email, role, domain)
    return jsonify(user.to_public_dict()), 201


@app.route("/api/admin/activity", methods=["GET"])
@admin_required
def admin_activity():
    """
    Returns a merged activity summary: queries from audit_log.jsonl and
    ingestions from data/ingest_log.jsonl, grouped by user so the admin
    can see at a glance who is doing what.
    """
    users   = {u.user_id: u.to_public_dict() for u in user_store.get_all()}
    queries = _read_jsonl("audit_log.jsonl")
    ingests = _read_jsonl(INGEST_LOG_PATH)

    summary = {uid: {**udata, "queries": 0, "ingests": 0, "last_activity": ""}
               for uid, udata in users.items()}

    for entry in queries:
        uid = entry.get("user_id")
        if uid and uid in summary:
            summary[uid]["queries"] += 1
            ts = entry.get("timestamp", "")
            if ts > summary[uid]["last_activity"]:
                summary[uid]["last_activity"] = ts

    for entry in ingests:
        uid = entry.get("user_id")
        if uid and uid in summary:
            summary[uid]["ingests"] += 1
            ts = entry.get("timestamp", "")
            if ts > summary[uid]["last_activity"]:
                summary[uid]["last_activity"] = ts

    return jsonify(list(summary.values()))


def _read_jsonl(path: str) -> list:
    """Reads a JSONL file safely, skipping malformed lines."""
    if not os.path.exists(path):
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line.strip()))
            except json.JSONDecodeError:
                pass
    return entries


# ── Misc ──────────────────────────────────────────────────────────────────────

@app.route("/api/search", methods=["POST"])
@login_required
def search():
    body         = request.get_json(force=True) or {}
    query        = (body.get("query") or "").strip()
    top_k        = int(body.get("top_k", 5))
    access_level = body.get("access_level") or None
    domain       = (body.get("domain_filter") or "").strip() or None
    if not query:
        return jsonify({"error": "Query cannot be empty."}), 400
    if retrieval_pipeline.total_chunks == 0:
        return jsonify({"error": "Index is empty."}), 400
    try:
        results = retrieval_pipeline.search(query, top_k=top_k,
                                            user_access_level=access_level,
                                            domain_filter=domain)
        return jsonify({"query": query, "total_results": len(results),
                        "index_size": retrieval_pipeline.total_chunks,
                        "results": [_result_to_dict(r) for r in results]})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/audit", methods=["GET"])
@login_required
def audit_list():
    n = int(request.args.get("n", 20))
    return jsonify({"entries": read_recent(n)})



@app.route("/api/audit/<audit_id>", methods=["GET"])
@login_required
def audit_entry(audit_id: str):
    entry = read_by_id(audit_id)
    if not entry:
        return jsonify({"error": f"Audit entry '{audit_id}' not found."}), 404
    return jsonify(entry)


@app.route("/api/conversations/<conv_id>", methods=["GET"])
@login_required
def conversation_detail(conv_id: str):
    """Returns all audit entries for a conversation, oldest-first."""
    return jsonify({"entries": read_conversation(conv_id)})


@app.route("/api/index/stats", methods=["GET"])
@login_required
def index_stats():
    return jsonify({"total_chunks": retrieval_pipeline.total_chunks})


@app.route("/api/admin/kb/clear", methods=["POST"])
@admin_required
def admin_clear_kb():
    """Admin-only: wipes all indexed documents from memory and disk."""
    retrieval_pipeline.clear_index()
    ingest_log = INGEST_LOG_PATH
    if os.path.exists(ingest_log):
        os.remove(ingest_log)
    return jsonify({"success": True, "message": "Knowledge base cleared."})


@app.route("/api/kb/documents", methods=["GET"])
@login_required
def kb_documents():
    """Returns one entry per unique source document for the KB Explorer view."""
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(retrieval_pipeline.list_documents())


@app.route("/api/config", methods=["GET"])
@login_required
def get_config():
    cfg      = _provider_config.get()
    provider = cfg.get("provider") or LLM_PROVIDER
    if provider == "anthropic":
        model = cfg.get("anthropic_model", "claude-haiku-4-5-20251001")
        return jsonify({"provider": "anthropic", "model": model,
                        "label": f"Anthropic · {model}"})
    if provider == "ollama":
        return jsonify({"provider": "ollama", "model": OLLAMA_MODEL,
                        "label": f"Local · {OLLAMA_MODEL}"})
    return jsonify({"provider": "gemini", "model": GEMINI_MODEL,
                    "label": f"Gemini · {GEMINI_MODEL}"})


@app.route("/api/admin/model-config", methods=["GET"])
@admin_required
def get_model_config():
    """Returns the active provider config. API key is masked — never returned."""
    cfg      = _provider_config.get()
    provider = cfg.get("provider") or LLM_PROVIDER
    return jsonify({
        "provider":         provider,
        "anthropic_model":  cfg.get("anthropic_model", "claude-haiku-4-5-20251001"),
        "anthropic_key_set": bool(cfg.get("anthropic_api_key", "").strip()),
        "available_models": ANTHROPIC_MODELS,
    })


@app.route("/api/admin/model-config", methods=["POST"])
@admin_required
def set_model_config():
    """Admin-only: switch LLM provider at runtime. API key stored only on disk (gitignored)."""
    body     = request.get_json(force=True) or {}
    provider = (body.get("provider") or "").strip().lower()

    if provider not in ("ollama", "gemini", "anthropic"):
        return jsonify({"error": "provider must be 'ollama', 'gemini', or 'anthropic'."}), 400

    if provider == "anthropic":
        api_key = (body.get("anthropic_api_key") or "").strip()
        model   = (body.get("anthropic_model") or "claude-haiku-4-5-20251001").strip()
        if model not in ANTHROPIC_MODELS:
            return jsonify({"error": f"Unknown Anthropic model '{model}'."}), 400

        # If no new key supplied, keep the existing one
        existing_key = _provider_config.get().get("anthropic_api_key", "")
        if not api_key:
            api_key = existing_key
        if not api_key:
            return jsonify({"error": "An Anthropic API key is required."}), 400

        _provider_config.save(provider="anthropic",
                              anthropic_api_key=api_key,
                              anthropic_model=model)
    else:
        # Keep any existing Anthropic key so it isn't wiped when switching back
        existing_key = _provider_config.get().get("anthropic_api_key", "")
        existing_model = _provider_config.get().get("anthropic_model", "claude-haiku-4-5-20251001")
        _provider_config.save(provider=provider,
                              anthropic_api_key=existing_key,
                              anthropic_model=existing_model)

    cfg = _provider_config.get()
    return jsonify({
        "success":          True,
        "provider":         cfg.get("provider"),
        "anthropic_model":  cfg.get("anthropic_model"),
        "anthropic_key_set": bool(cfg.get("anthropic_api_key", "").strip()),
    })


# ── Ingest from raw text ─────────────────────────────────────────────────────

@app.route("/api/ingest/text", methods=["POST"])
@login_required
def ingest_text():
    """
    Ingests a plain-text answer directly into the knowledge base without a file.
    Used by experts and admins when resolving a ticket by typing the answer.
    Optionally marks a ticket as resolved when ticket_id is supplied.
    Domain enforcement mirrors the file-ingest route: experts are locked to
    their own domain, admins can specify any domain.
    """
    user = get_current_user()
    if user.role not in INGEST_ROLES:
        return jsonify({"error": "Uploading content is restricted to experts and admins."}), 403

    body         = request.get_json(force=True) or {}
    text         = (body.get("text") or "").strip()
    title        = (body.get("title") or "Manual Entry").strip()
    access_level = (body.get("access_level") or "internal").strip()
    domain       = (body.get("domain") or "").strip()
    ticket_id    = (body.get("ticket_id") or "").strip()

    if not text:
        return jsonify({"error": "Text content cannot be empty."}), 400

    if user.role == "expert":
        if not domain:
            domain = user.domain
        elif domain != user.domain:
            return jsonify({"error": f"You are authorised to upload for '{user.domain}' only."}), 403

    try:
        chunks = ingest_pipeline.ingest_text(text, title=title,
                                             access_level=access_level, domain=domain)
        added  = retrieval_pipeline.index(chunks)
        _write_ingest_log(user, title, added, domain)

        if ticket_id:
            ticket_store.update_status(ticket_id, "resolved")

        return jsonify({
            "success":       True,
            "total_chunks":  len(chunks),
            "newly_indexed": added,
            "index_size":    retrieval_pipeline.total_chunks,
        })
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ── Tickets ───────────────────────────────────────────────────────────────────

@app.route("/api/tickets", methods=["GET"])
@login_required
def get_tickets():
    """
    Returns knowledge-gap tickets scoped by role:
      - expert : only tickets whose domain matches the expert's own domain
      - admin  : all tickets; accepts optional ?domain= query param to filter
    Regular users cannot access tickets (403).
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403

    if user.role == "expert":
        tickets = ticket_store.get_all(domain=user.domain)
    else:
        domain_filter = request.args.get("domain", "").strip() or None
        tickets = ticket_store.get_all(domain=domain_filter)

    return jsonify([vars(t) for t in tickets])


@app.route("/api/tickets/<ticket_id>", methods=["PUT"])
@login_required
def update_ticket(ticket_id: str):
    """Experts and admins can flip a ticket's status between open and resolved."""
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403

    body   = request.get_json(force=True) or {}
    status = body.get("status", "").strip()
    if status not in ("open", "resolved"):
        return jsonify({"error": "status must be 'open' or 'resolved'."}), 400

    ticket = ticket_store.update_status(ticket_id, status)
    if not ticket:
        return jsonify({"error": f"Ticket '{ticket_id}' not found."}), 404
    return jsonify(vars(ticket))


# ── Insights ──────────────────────────────────────────────────────────────────

@app.route("/api/insights", methods=["GET"])
@login_required
def get_insights():
    """
    Returns confidence distribution and per-domain breakdown computed from the
    audit log.  No LLM call — safe to call on every tab load.
    Visible to experts and admins only.
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(insight_engine.confidence_distribution())


@app.route("/api/insights/report", methods=["POST"])
@login_required
def get_gap_report():
    """
    Triggers the LLM gap-report generation.  Separated from /api/insights so
    the LLM is only called when the user explicitly requests it, not on every
    page load.  Visible to experts and admins only.
    """
    user = get_current_user()
    if user.role not in ("expert", "admin"):
        return jsonify({"error": "Access restricted to experts and admins."}), 403
    return jsonify(insight_engine.generate_gap_report())


# ── Training ─────────────────────────────────────────────────────────────────

@app.route("/api/training/questions", methods=["GET"])
@login_required
def training_list_questions():
    """
    Lists training questions.
    - Users (quiz mode): all questions across domains; expected_answer hidden.
    - Experts (quiz mode): all questions; expected_answer hidden.
    - Experts (manage=1): only their domain; expected_answer shown.
    - Admins (manage=1): all questions; expected_answer shown.
    """
    user    = get_current_user()
    manage  = request.args.get("manage", "0") == "1"

    if manage and user.role in ("expert", "admin"):
        # Expert sees only their own domain in manage mode
        domain_filter = user.domain if user.role == "expert" else None
        questions = training_store.get_all(domain=domain_filter)
        # Include expected_answer in manage mode
        return jsonify({"questions": questions})
    else:
        # Quiz mode: all questions, hide expected_answer
        questions = training_store.get_all()
        sanitised = [{k: v for k, v in q.items() if k != "expected_answer"} for q in questions]
        return jsonify({"questions": sanitised})


@app.route("/api/training/questions", methods=["POST"])
@login_required
def training_create_question():
    """Creates a new training question. Admin only."""
    user = get_current_user()
    if user.role != "admin":
        return jsonify({"error": "Creating training questions is restricted to admins."}), 403

    body       = request.get_json(force=True) or {}
    domain     = (body.get("domain") or "").strip()
    situation  = (body.get("situation") or "").strip()
    expected   = (body.get("expected_answer") or "").strip()
    difficulty = (body.get("difficulty") or "medium").strip()

    if not domain or not situation or not expected:
        return jsonify({"error": "domain, situation, and expected_answer are required."}), 400

    question = training_store.create(
        domain          = domain,
        situation       = situation,
        expected_answer = expected,
        created_by      = user.user_id,
        created_by_name = user.name,
        difficulty      = difficulty,
    )
    return jsonify(question), 201


@app.route("/api/training/questions/<qid>", methods=["DELETE"])
@login_required
def training_delete_question(qid: str):
    """Deletes a training question. Admin only."""
    user = get_current_user()
    if user.role != "admin":
        return jsonify({"error": "Deleting training questions is restricted to admins."}), 403

    question = training_store.find_by_id(qid)
    if not question:
        return jsonify({"error": f"Question '{qid}' not found."}), 404

    # Expert domain enforcement
    if user.role == "expert" and question.get("domain") != user.domain:
        return jsonify({"error": "You can only delete questions in your own domain."}), 403

    training_store.delete(qid)
    return jsonify({"success": True})


@app.route("/api/training/evaluate", methods=["POST"])
@login_required
def training_evaluate():
    """
    Evaluates a user's answer to a training question via LLM,
    records the attempt, and returns score/feedback plus progress info.
    """
    user = get_current_user()
    body = request.get_json(force=True) or {}

    question_id = (body.get("question_id") or "").strip()
    user_answer = (body.get("user_answer") or "").strip()

    if not question_id or not user_answer:
        return jsonify({"error": "question_id and user_answer are required."}), 400

    question = training_store.find_by_id(question_id)
    if not question:
        return jsonify({"error": f"Question '{question_id}' not found."}), 404

    try:
        result = generation_pipeline.evaluate(
            situation       = question["situation"],
            expected_answer = question["expected_answer"],
            user_answer     = user_answer,
        )
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    # Record the attempt
    points_earned = max(1, result["score"] // 10)
    progress_store.record(
        user_id      = user.user_id,
        question_id  = question_id,
        domain       = question["domain"],
        score        = result["score"],
        feedback     = result["feedback"],
        strengths    = result["strengths"],
        improvements = result["improvements"],
    )

    stats = progress_store.get_user_stats(user.user_id)

    return jsonify({
        "score":           result["score"],
        "feedback":        result["feedback"],
        "strengths":       result["strengths"],
        "improvements":    result["improvements"],
        "points_earned":   points_earned,
        "expected_answer": question["expected_answer"],
        "level":           stats["level"],
        "total_points":    stats["total_points"],
    })


@app.route("/api/training/progress", methods=["GET"])
@login_required
def training_progress():
    """Returns the current user's training stats and last 10 attempts."""
    user    = get_current_user()
    stats   = progress_store.get_user_stats(user.user_id)
    history = progress_store.get_user_history(user.user_id)[:10]
    return jsonify({"stats": stats, "history": history})


if __name__ == "__main__":
    # use_debugger=False disables the DebuggedApplication WSGI middleware whose
    # cross-origin check blocks every proxied request from the Vite dev server.
    # Auto-reload and debug logging are kept via debug=True + use_reloader=True.
    app.run(debug=True, use_debugger=False, use_reloader=True, port=5001)
